"""Paynet (UZPAYNET) provider endpoint: ``POST /api/payments/paynet``, JSON-RPC 2.0.

Paynet and SlaydX share ONE Paynet service. Paynet calls SlaydX; when the payer
id starts with ``vk-`` (or ``vk_``) SlaydX relays the request here unchanged
(body, Content-Type, ``Authorization: Basic ...``, plus ``X-Forwarded-By``) and
hands our JSON reply back to Paynet verbatim. So this module only implements
the provider side of the protocol:

* HTTP 200 + a JSON-RPC body for everything, except bad / missing credentials:
  HTTP 401 + ``WWW-Authenticate`` (error 412). The Basic credentials are the ONLY
  authentication (no IP filter; ``X-Forwarded-By`` can be forged).
* Methods: ``GetInformation``, ``PerformTransaction``, ``CheckTransaction``,
  ``CancelTransaction`` (never cancels: payments are final), ``GetStatement``.
* Amounts arrive in tiyin and are credited in so'm (``amount / 100``); the
  balances we report are so'm too.
* A top-up is a ``payment_orders`` row (provider ``paynet``, state ``paid``,
  ``provider_txn`` = Paynet's ``transactionId``) written in ONE ``BEGIN
  IMMEDIATE`` transaction together with the wallet credit, the ledger row
  (``paynet:<transactionId>``) and the payment bonus, through the same
  :func:`webapp.payments.service.credit_topup` Click uses. A repeated
  ``transactionId`` is error 201 and never credits twice, also under
  concurrency (the write lock serializes callers; the unique index
  ``(provider, provider_txn)`` and the unique ledger reference are the guards).
* Our ``providerTrnId`` is ``PAYNET_TRN_OFFSET + seq``: unique, never reused and
  clear of SlaydX's small integers (Paynet sees both statements merged).

Nothing here makes an outbound call and the credentials, the ``Authorization``
header and request bodies are never logged.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import math
import re
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from webapp.payments import service
from webapp.payments.config import (
    MAX_TOPUP_SOUM,
    MIN_TOPUP_SOUM,
    PAYNET_PAYER_PREFIXES,
    PAYNET_TRN_OFFSET,
    PaynetConfig,
    paynet_config,
)

_log = logging.getLogger(__name__)

MAX_BODY_BYTES = 64 * 1024
#: Statement rows we are willing to build; more means the range is too wide.
STATEMENT_MAX_ROWS = 100_000
#: Largest integer a JSON client (Paynet is JavaScript-side) represents exactly.
MAX_SAFE_INTEGER = 2**53 - 1
#: GMT+5 all year (Asia/Tashkent has no DST).
TASHKENT = timezone(timedelta(hours=5))

# Envelope errors
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
METHOD_NOT_ALLOWED = -32300
# Provider errors
CANNOT_CANCEL = 77
TRANSACTION_EXISTS = 201
TRANSACTION_NOT_FOUND = 203
CLIENT_NOT_FOUND = 302
SERVICE_NOT_FOUND = 305
CLIENT_FORMAT = 401
CLIENT_MISSING = 411
BAD_CREDENTIALS = 412
BAD_AMOUNT = 413
BAD_DATE = 414
AMOUNT_TOO_LARGE = 415
CLIENT_BLOCKED = 501

MESSAGES = {
    PARSE_ERROR: "Parse error",
    INVALID_REQUEST: "Invalid Request",
    METHOD_NOT_FOUND: "Method not found",
    INVALID_PARAMS: "Invalid params",
    INTERNAL_ERROR: "Internal error",
    METHOD_NOT_ALLOWED: "Method not allowed",
    CANNOT_CANCEL: "Невозможно отменить транзакцию",
    TRANSACTION_EXISTS: "Транзакция уже существует",
    TRANSACTION_NOT_FOUND: "Транзакция не найдена",
    CLIENT_NOT_FOUND: "Клиент не найден",
    SERVICE_NOT_FOUND: "Услуга не найдена",
    CLIENT_FORMAT: "Неверный формат идентификатора клиента",
    CLIENT_MISSING: "Не указан идентификатор клиента",
    BAD_CREDENTIALS: "Неверный логин или пароль",
    BAD_AMOUNT: "Неверная сумма",
    BAD_DATE: "Неверный формат даты",
    AMOUNT_TOO_LARGE: "Сумма превышает максимальную",
    CLIENT_BLOCKED: "Клиент заблокирован",
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


class RpcError(Exception):
    """A JSON-RPC error reply (HTTP stays 200)."""

    def __init__(self, code: int) -> None:
        super().__init__(f"paynet error {code}")
        self.code = code


# ---------------------------------------------------------------------------
# Envelope helpers
# ---------------------------------------------------------------------------


def _ok(rpc_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def _err(rpc_id: Any, code: int) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": MESSAGES[code]}}


def _valid_id(value: Any) -> bool:
    return isinstance(value, (str, int, float)) and not isinstance(value, bool)


def _reject_constant(_: str) -> None:
    raise ValueError("NaN / Infinity are not JSON")


def format_time(ms: int) -> str:
    """``YYYY-MM-DD HH:mm:ss`` in GMT+5 for a unix-millisecond time."""
    return datetime.fromtimestamp(int(ms) // 1000, TASHKENT).strftime("%Y-%m-%d %H:%M:%S")


def parse_time(value: Any) -> int:
    """Unix seconds for a strict ``YYYY-MM-DD HH:mm:ss`` (GMT+5) string, else error 414."""
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise RpcError(BAD_DATE)
    try:
        return int(datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TASHKENT).timestamp())
    except (ValueError, OverflowError, OSError):
        raise RpcError(BAD_DATE) from None


def _now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def _digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def authorized(header: str | None, cfg: PaynetConfig) -> bool:
    """HTTP Basic against ``PAYNET_USERNAME`` / ``PAYNET_PASSWORD``, in constant time.

    Both halves are always compared (bitwise ``&``, no short circuit) on sha256
    digests, so neither the length nor a matching prefix of either secret leaks.
    """
    if not header:
        return False
    scheme, _, encoded = header.strip().partition(" ")
    if scheme.lower() != "basic" or not encoded.strip():
        return False
    try:
        decoded = base64.b64decode(encoded.strip(), validate=True).decode("utf-8")
    except (binascii.Error, ValueError):
        return False
    username, sep, password = decoded.partition(":")
    if not sep:
        return False
    user_ok = hmac.compare_digest(_digest(username), _digest(cfg.username))
    pass_ok = hmac.compare_digest(_digest(password), _digest(cfg.password))
    return user_ok & pass_ok


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content=_err(None, BAD_CREDENTIALS),
        headers={"WWW-Authenticate": 'Basic realm="paynet"'},
    )


# ---------------------------------------------------------------------------
# Parameter rules
# ---------------------------------------------------------------------------


def _require(params: dict[str, Any], *names: str) -> None:
    for name in names:
        if name not in params:
            raise RpcError(INVALID_PARAMS)


def _check_service(cfg: PaynetConfig, value: Any, ctx: dict[str, Any]) -> None:
    """``serviceId`` must be an integer listed in ``PAYNET_SERVICE_IDS`` (else 305)."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise RpcError(INVALID_PARAMS)
    text = str(value).strip()
    if not (text.isascii() and text.isdigit()) or len(text) > 18:
        raise RpcError(SERVICE_NOT_FOUND)
    ctx["service"] = text
    if int(text) not in cfg.service_ids:
        raise RpcError(SERVICE_NOT_FOUND)


def _fields(params: dict[str, Any]) -> dict[str, Any]:
    fields = params["fields"]
    if not isinstance(fields, dict):
        raise RpcError(INVALID_PARAMS)
    return fields


def parse_payer(fields: dict[str, Any], param: str) -> tuple[int, str]:
    """``(user id, the id as sent)`` from ``fields[param]`` = ``vk-<digits>``.

    Absent -> 411, malformed -> 401. Case-sensitive; the digits are ASCII only.
    """
    raw = fields.get(param)
    if raw is None or raw == "":
        raise RpcError(CLIENT_MISSING)
    if not isinstance(raw, str):
        raise RpcError(CLIENT_FORMAT)
    for prefix in PAYNET_PAYER_PREFIXES:
        if raw.startswith(prefix):
            digits = raw[len(prefix):]
            break
    else:
        raise RpcError(CLIENT_FORMAT)
    if not (digits.isascii() and digits.isdigit()) or len(digits) > 18:
        raise RpcError(CLIENT_FORMAT)
    return int(digits), raw


def parse_transaction_id(value: Any) -> int:
    """A positive safe integer (a digit string is canonicalised: ``"000123"`` == ``123``)."""
    if isinstance(value, bool):
        raise RpcError(INVALID_PARAMS)
    if isinstance(value, str):
        if not (value.isascii() and value.isdigit()) or len(value) > 40:
            raise RpcError(INVALID_PARAMS)
        number = int(value)
    elif isinstance(value, int):
        number = value
    else:
        raise RpcError(INVALID_PARAMS)
    if number < 1 or number > MAX_SAFE_INTEGER:
        raise RpcError(INVALID_PARAMS)
    return number


def parse_amount_soum(value: Any) -> int:
    """Tiyin (positive integer, multiple of 100) -> so'm inside the top-up limits.

    Anything that is not such a number is 413; below the Click minimum 413, above
    the Click maximum 415.
    """
    if isinstance(value, bool) or value is None:
        raise RpcError(BAD_AMOUNT)
    if isinstance(value, int):
        tiyin = value
    elif isinstance(value, float):
        if not math.isfinite(value) or value != math.floor(value):
            raise RpcError(BAD_AMOUNT)
        tiyin = int(value)
    elif isinstance(value, str):
        if not (value.isascii() and value.isdigit()) or len(value) > 40:
            raise RpcError(BAD_AMOUNT)
        tiyin = int(value)
    else:
        raise RpcError(BAD_AMOUNT)
    if tiyin <= 0 or tiyin % 100:
        raise RpcError(BAD_AMOUNT)
    soum = tiyin // 100
    if soum < MIN_TOPUP_SOUM:
        raise RpcError(BAD_AMOUNT)
    if soum > MAX_TOPUP_SOUM:
        raise RpcError(AMOUNT_TOO_LARGE)
    return soum


def mask_name(first_name: Any) -> str:
    """``Adham B.`` for ``Adham Bek``; a single token as is; nothing -> ``Bandlik``."""
    tokens = str(first_name or "").split()
    if not tokens:
        return "Bandlik"
    if len(tokens) == 1:
        return tokens[0][:40]
    return f"{tokens[0][:40]} {tokens[1][0].upper()}."


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------


async def _load_payer(db, user_id: int):
    cursor = await db.execute(
        "SELECT user_id, first_name, COALESCE(user_balance, 0) AS balance, "
        "COALESCE(banned, 0) AS banned FROM users WHERE user_id = ?",
        (user_id,),
    )
    return await cursor.fetchone()


async def _payer_or_error(db, user_id: int):
    row = await _load_payer(db, user_id)
    if row is None:
        raise RpcError(CLIENT_NOT_FOUND)
    if int(row["banned"]):
        raise RpcError(CLIENT_BLOCKED)
    return row


async def _find_paid(db, transaction_id: int):
    cursor = await db.execute(
        "SELECT id, seq, amount_soum, perform_time FROM payment_orders "
        "WHERE provider = 'paynet' AND provider_txn = ? AND state = 'paid'",
        (str(transaction_id),),
    )
    return await cursor.fetchone()


def _provider_trn_id(seq: int) -> int:
    return PAYNET_TRN_OFFSET + int(seq)


# ---------------------------------------------------------------------------
# Methods
# ---------------------------------------------------------------------------


async def get_information(db, cfg: PaynetConfig, params: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    _require(params, "serviceId", "fields")
    fields = _fields(params)
    _check_service(cfg, params["serviceId"], ctx)
    user_id, _ = parse_payer(fields, cfg.client_param)
    row = await _payer_or_error(db, user_id)
    return {
        "status": "0",
        "timestamp": format_time(_now_ms()),
        "fields": {"name": mask_name(row["first_name"]), "balance": int(row["balance"])},
    }


async def perform_transaction(db, cfg: PaynetConfig, params: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    _require(params, "amount", "serviceId", "transactionId", "fields")
    fields = _fields(params)
    _check_service(cfg, params["serviceId"], ctx)
    transaction_id = parse_transaction_id(params["transactionId"])
    ctx["txn"] = str(transaction_id)
    user_id, payer_as_sent = parse_payer(fields, cfg.client_param)
    amount_soum = parse_amount_soum(params["amount"])

    order_id = str(uuid.uuid4())
    now_ms = _now_ms()
    now = now_ms // 1000
    await db.execute("BEGIN IMMEDIATE")
    try:
        if await _find_paid(db, transaction_id) is not None:
            raise RpcError(TRANSACTION_EXISTS)
        await _payer_or_error(db, user_id)
        await db.execute(
            "INSERT INTO payment_orders (id, user_id, provider, purpose, amount_soum, state, "
            "provider_txn, create_time, perform_time, click_method, created_at, updated_at) "
            "VALUES (?, ?, 'paynet', 'topup', ?, 'paid', ?, ?, ?, 'paynet', ?, ?)",
            (order_id, user_id, amount_soum, str(transaction_id), now_ms, now_ms, now, now),
        )
        order = await service.find_order(db, order_id)
        assert order is not None
        bonus, balance = await service.credit_topup(
            db, order, reference=f"paynet:{transaction_id}", note="paynet"
        )
        provider_trn_id = _provider_trn_id(order.seq)
        await db.commit()
    except sqlite3.IntegrityError:
        # A concurrent twin won between our check and insert (unique indexes).
        await db.rollback()
        if await _find_paid(db, transaction_id) is not None:
            raise RpcError(TRANSACTION_EXISTS) from None
        raise
    except BaseException:
        await db.rollback()
        raise
    ctx["order_id"] = order_id
    _log.info(
        "[paynet] credited order=%s user=%s amount=%s bonus=%s", order_id, user_id, amount_soum, bonus
    )
    return {
        "timestamp": format_time(now_ms),
        "providerTrnId": provider_trn_id,
        "fields": {cfg.client_param: payer_as_sent, "balance": balance},
    }


async def check_transaction(db, cfg: PaynetConfig, params: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    _require(params, "serviceId", "transactionId", "timestamp")
    _check_service(cfg, params["serviceId"], ctx)
    transaction_id = parse_transaction_id(params["transactionId"])
    ctx["txn"] = str(transaction_id)
    parse_time(params["timestamp"])
    row = await _find_paid(db, transaction_id)
    if row is None:
        return {"transactionState": 3, "providerTrnId": 0, "timestamp": format_time(_now_ms())}
    ctx["order_id"] = str(row["id"])
    return {
        "transactionState": 1,
        "providerTrnId": _provider_trn_id(row["seq"]),
        "timestamp": format_time(int(row["perform_time"])),
    }


async def cancel_transaction(db, cfg: PaynetConfig, params: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Payments are final (owner policy): never cancels, never changes anything."""
    _require(params, "serviceId", "transactionId", "timestamp")
    _check_service(cfg, params["serviceId"], ctx)
    transaction_id = parse_transaction_id(params["transactionId"])
    ctx["txn"] = str(transaction_id)
    parse_time(params["timestamp"])
    row = await _find_paid(db, transaction_id)
    if row is None:
        raise RpcError(TRANSACTION_NOT_FOUND)
    ctx["order_id"] = str(row["id"])
    raise RpcError(CANNOT_CANCEL)


async def get_statement(db, cfg: PaynetConfig, params: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    _require(params, "serviceId", "dateFrom", "dateTo")
    _check_service(cfg, params["serviceId"], ctx)
    start = parse_time(params["dateFrom"])
    end = parse_time(params["dateTo"])
    if start > end:
        raise RpcError(BAD_DATE)
    cursor = await db.execute(
        "SELECT seq, provider_txn, amount_soum, perform_time FROM payment_orders "
        "WHERE provider = 'paynet' AND state = 'paid' AND perform_time BETWEEN ? AND ? "
        "ORDER BY perform_time, CAST(provider_txn AS INTEGER) LIMIT ?",
        (start * 1000, end * 1000 + 999, STATEMENT_MAX_ROWS + 1),
    )
    rows = await cursor.fetchall()
    if len(rows) > STATEMENT_MAX_ROWS:
        _log.error("[paynet] statement range too wide (> %s rows)", STATEMENT_MAX_ROWS)
        raise RuntimeError("statement too large")
    statements = []
    seen: set[int] = set()
    for row in rows:
        # SlaydX fails the WHOLE statement on one bad row: refuse to send a bad one.
        transaction_id = int(row["provider_txn"])
        provider_trn_id = _provider_trn_id(row["seq"])
        amount_tiyin = int(row["amount_soum"]) * 100
        if transaction_id < 1 or transaction_id in seen or amount_tiyin <= 0 or provider_trn_id <= 0:
            raise RuntimeError("malformed statement row")
        seen.add(transaction_id)
        statements.append(
            {
                "amount": amount_tiyin,
                "transactionId": transaction_id,
                "providerTrnId": provider_trn_id,
                "timestamp": format_time(int(row["perform_time"])),
            }
        )
    return {"statements": statements}


METHODS = {
    "GetInformation": get_information,
    "PerformTransaction": perform_transaction,
    "CheckTransaction": check_transaction,
    "CancelTransaction": cancel_transaction,
    "GetStatement": get_statement,
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _read_body(request: Request) -> bytes | None:
    """The body, or None when it is larger than :data:`MAX_BODY_BYTES`."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return None
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BODY_BYTES:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


async def _dispatch(db, cfg: PaynetConfig, request: Request, ctx: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """``(id to echo, result)``; raises :class:`RpcError` (with ``rpc_id`` set once known)."""
    raw = await _read_body(request)
    if raw is None:
        raise RpcError(INVALID_REQUEST)
    try:
        doc = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        raise RpcError(PARSE_ERROR) from None

    rpc_id = doc.get("id") if isinstance(doc, dict) and _valid_id(doc.get("id")) else None
    ctx["rpc_id"] = rpc_id
    if (
        not isinstance(doc, dict)
        or doc.get("jsonrpc") != "2.0"
        or not isinstance(doc.get("method"), str)
        or rpc_id is None
        or not isinstance(doc.get("params"), dict)
    ):
        raise RpcError(INVALID_REQUEST)
    params = doc["params"]
    ctx["payload"] = params
    handler = METHODS.get(doc["method"])
    if handler is None:
        raise RpcError(METHOD_NOT_FOUND)
    ctx["method"] = doc["method"]
    return rpc_id, await handler(db, cfg, params, ctx)


async def handle_request(request: Request, db) -> JSONResponse:
    started = time.monotonic()
    if request.method != "POST":
        return JSONResponse(status_code=200, content=_err(None, METHOD_NOT_ALLOWED))
    cfg = paynet_config()
    if cfg is None or not authorized(request.headers.get("authorization"), cfg):
        return _unauthorized()

    ctx: dict[str, Any] = {"method": "invalid", "payload": {}, "rpc_id": None}
    try:
        rpc_id, result = await _dispatch(db, cfg, request, ctx)
        body, code = _ok(rpc_id, result), 0
    except RpcError as exc:
        body, code = _err(ctx["rpc_id"], exc.code), exc.code
    except Exception:
        # Never leak details to the caller; the traceback goes to the journal.
        _log.exception("[paynet] internal error method=%s", ctx["method"])
        try:
            await db.rollback()
        except Exception:  # pragma: no cover - connection gone
            pass
        body, code = _err(ctx["rpc_id"], INTERNAL_ERROR), INTERNAL_ERROR

    await service.record_payment_event(
        db,
        provider="paynet",
        method=ctx["method"],
        order_id=ctx.get("order_id"),
        provider_txn=ctx.get("txn"),
        payload=ctx["payload"],
        response_code=code,
    )
    _log.info(
        "[paynet] method=%s service=%s code=%s ms=%d",
        ctx["method"],
        ctx.get("service", "-"),
        code,
        (time.monotonic() - started) * 1000,
    )
    return JSONResponse(status_code=200, content=body)
