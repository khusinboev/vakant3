"""Click Merchant API client (port of SlaydX ``lib/server/click-merchant.ts``).

Base ``https://api.click.uz/v2/merchant``, JSON in / JSON out, every request
carries ``Auth: <merchant_user_id>:<sha1(timestamp + secret_key)>:<timestamp>``
(10-digit unix seconds). Used ONLY to start a payment (invoice by phone,
one-time card token + SMS, payment by token); nothing here touches a balance.

Sensitive data: the card number, expiry, SMS code and card token exist only in
the arguments and the outgoing body. They are never logged, never put into an
exception and never returned. Logs carry stage, order id, method, HTTP status
and Click's ``error_code`` only (plus a scrubbed note for unknown codes).

Errors: every failure is a :class:`ClickMerchantError` with a ``reason`` key
(not prose — the Mini App translates ``payments.reason.<reason>``). Mapping as
in SlaydX: the documented Shop API code table, keyword rules on
``error_note``, then a per-stage fallback.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Any

import httpx

from webapp.payments.config import UUID_RE, click_config

_log = logging.getLogger(__name__)

CLICK_MERCHANT_BASE = "https://api.click.uz/v2/merchant"
CLICK_TIMEOUT_SECONDS = 15.0

STAGES = (
    "card_request",
    "card_verify",
    "card_payment",
    "invoice_create",
    "invoice_status",
    "payment_status",
)


class ClickMerchantError(Exception):
    """``failure``: declined (Click said no) | unavailable | config | unknown."""

    def __init__(
        self,
        stage: str,
        failure: str,
        reason: str,
        error_code: int | None = None,
        outcome_unknown: bool = False,
    ) -> None:
        # Deliberately free of any request/response content.
        suffix = "" if error_code is None else f" (error_code {error_code})"
        super().__init__(f"click {stage}: {failure}{suffix}")
        self.stage = stage
        self.failure = failure
        self.reason = reason
        self.error_code = error_code
        #: The request may have reached Click and succeeded (timeout, reset, 5xx).
        self.outcome_unknown = outcome_unknown


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def click_auth_digest(secret_key: str, timestamp: int | str) -> str:
    """``sha1(timestamp + secret_key)`` as lowercase hex."""
    return hashlib.sha1(f"{timestamp}{secret_key}".encode()).hexdigest()


def click_auth_header(merchant_user_id: str, secret_key: str, now: float | None = None) -> str:
    timestamp = int(time.time() if now is None else now)
    return f"{merchant_user_id}:{click_auth_digest(secret_key, timestamp)}:{timestamp}"


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------

STAGE_FALLBACK = {
    "card_request": "card_rejected",
    "card_verify": "sms_invalid",
    "card_payment": "payment_failed",
    "invoice_create": "invoice_failed",
    "invoice_status": "generic",
    "payment_status": "generic",
}

#: The documented public table (docs.click.uz > Shop API > Errors).
BY_CODE = {
    -1: "config",
    -2: "amount",
    -4: "already_paid",
    -5: "order_not_found",
    -6: "payment_not_found",
    -9: "cancelled",
}

#: Keyword rules on Click's (English / Russian) ``error_note``; first match wins.
NOTE_RULES: list[tuple[re.Pattern[str], tuple[str, ...] | None, str]] = [
    (re.compile(r"insufficient|not enough|недостаточно|не хватает", re.I), None, "insufficient_funds"),
    (re.compile(r"limit|лимит", re.I), None, "card_limit"),
    (re.compile(r"expire|expired|срок", re.I), ("card_request", "card_payment"), "card_expired"),
    (re.compile(r"sms|otp|confirm|код|code", re.I), ("card_verify",), "sms_invalid"),
    (
        re.compile(r"not support|unsupported|не поддерж|не обслужива|not allowed|запрещ", re.I),
        ("card_request", "card_payment"),
        "card_unsupported",
    ),
    (
        re.compile(
            r"(card|карт\S*).*(not found|not exist|block|invalid|не найден|не существует|заблок)"
            r"|(not found|invalid|blocked).*(card|карт)",
            re.I,
        ),
        ("card_request", "card_payment"),
        "card_not_found",
    ),
    (
        re.compile(r"phone|абонент|телефон|номер|subscriber|not found|не найден", re.I),
        ("invoice_create",),
        "phone_not_registered",
    ),
]


def click_error_reason(stage: str, code: int | None, note: str) -> tuple[str, bool]:
    """(reason, known) for a Click ``error_code`` / ``error_note``."""
    if code is not None and code in BY_CODE:
        return BY_CODE[code], True
    text = str(note or "")
    for pattern, stages, reason in NOTE_RULES:
        if stages and stage not in stages:
            continue
        if pattern.search(text):
            return reason, True
    return STAGE_FALLBACK[stage], False


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


async def _send(
    method: str, url: str, headers: dict[str, str], body: dict[str, Any] | None
) -> tuple[int, str]:
    """The single HTTP seam (tests replace it). Returns (status, text)."""
    async with httpx.AsyncClient(timeout=CLICK_TIMEOUT_SECONDS) as client:
        response = await client.request(
            method,
            url,
            headers=headers,
            content=None if body is None else json.dumps(body),
        )
        return response.status_code, response.text


def _scrub(text: str, body: dict[str, Any] | None) -> str:
    """Remove every sensitive value of THIS request from a text Click sent back."""
    out = text
    for key in ("card_number", "expire_date", "sms_code", "card_token"):
        value = (body or {}).get(key)
        if isinstance(value, str) and value:
            out = out.replace(value, "[REDACTED]")
    return out


async def _call(
    stage: str,
    method: str,
    path: str,
    ctx: dict[str, Any],
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = click_config()
    if cfg is None:
        raise ClickMerchantError(stage, "config", "config")
    fields = {"stage": stage, "order_id": ctx.get("order_id"), "method": ctx.get("method")}
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Auth": click_auth_header(cfg.merchant_user_id, cfg.secret_key),
    }
    try:
        status, text = await _send(method, f"{CLICK_MERCHANT_BASE}{path}", headers, body)
    except Exception as exc:
        # Only the failure KIND is logged, never the exception (it may echo the request).
        kind = "timeout" if isinstance(exc, httpx.TimeoutException) else "network"
        _log.warning("[click-merchant] request failed %s reason=%s", fields, kind)
        raise ClickMerchantError(stage, "unavailable", "unavailable", None, True) from None

    data: dict[str, Any] | None = None
    try:
        parsed = json.loads(text) if text else None
        if isinstance(parsed, dict):
            data = parsed
    except ValueError:
        data = None

    raw_code = (data or {}).get("error_code")
    code: int | None = None
    if isinstance(raw_code, bool):
        code = None
    elif isinstance(raw_code, int):
        code = raw_code
    elif isinstance(raw_code, str) and re.fullmatch(r"-?\d+", raw_code):
        code = int(raw_code)

    if status in (401, 403):
        _log.error("[click-merchant] credentials rejected %s http=%s", fields, status)
        raise ClickMerchantError(stage, "config", "config", code)
    if status >= 500:
        _log.warning("[click-merchant] Click server error %s http=%s", fields, status)
        raise ClickMerchantError(stage, "unavailable", "unavailable", code, True)
    if data is None or code is None:
        _log.warning("[click-merchant] unreadable answer %s http=%s", fields, status)
        raise ClickMerchantError(stage, "unknown", STAGE_FALLBACK[stage], None, 200 <= status < 300)
    if code != 0:
        note = data.get("error_note")
        note = _scrub(note[:160], body) if isinstance(note, str) else ""
        reason, known = click_error_reason(stage, code, note)
        if code == -1:
            _log.error("[click-merchant] credentials rejected %s http=%s code=%s", fields, status, code)
            raise ClickMerchantError(stage, "config", "config", code)
        if known:
            _log.info("[click-merchant] declined %s http=%s code=%s", fields, status, code)
        else:
            # Unknown codes carry the note so the table can be completed from real traffic.
            _log.info("[click-merchant] declined %s http=%s code=%s note=%r", fields, status, code, note)
        raise ClickMerchantError(stage, "declined" if known else "unknown", reason, code)
    _log.info("[click-merchant] ok %s http=%s", fields, status)
    return data


def _service_id() -> int:
    cfg = click_config()
    return int(cfg.service_id) if cfg and cfg.service_id.isdigit() else 0


def _id_of(stage: str, value: Any) -> str:
    text = str(value) if isinstance(value, (int, str)) and not isinstance(value, bool) else ""
    if not re.fullmatch(r"\d{1,19}", text):
        raise ClickMerchantError(stage, "unknown", STAGE_FALLBACK[stage], None, True)
    return text


# ---------------------------------------------------------------------------
# Typed calls
# ---------------------------------------------------------------------------


async def request_card_token(card_number: str, expire_date: str, ctx: dict[str, Any]) -> dict[str, str]:
    """``POST /card_token/request`` (one-time token, ``temporary: 1``); Click texts a code."""
    data = await _call(
        "card_request",
        "POST",
        "/card_token/request",
        ctx,
        {
            "service_id": _service_id(),
            "card_number": card_number,
            "expire_date": expire_date,
            "temporary": 1,
        },
    )
    token = data.get("card_token")
    if not isinstance(token, str) or not token:
        raise ClickMerchantError("card_request", "unknown", STAGE_FALLBACK["card_request"])
    phone = data.get("phone_number")
    return {"card_token": token, "phone_masked": phone if isinstance(phone, str) else ""}


async def verify_card_token(card_token: str, sms_code: str, ctx: dict[str, Any]) -> dict[str, str]:
    """``POST /card_token/verify``; returns the MASKED card number only."""
    data = await _call(
        "card_verify",
        "POST",
        "/card_token/verify",
        ctx,
        {"service_id": _service_id(), "card_token": card_token, "sms_code": sms_code},
    )
    masked = data.get("card_number")
    return {"card_masked": masked if isinstance(masked, str) else ""}


async def pay_with_card_token(
    card_token: str, amount_soum: int, transaction_parameter: str, ctx: dict[str, Any]
) -> dict[str, Any]:
    """``POST /card_token/payment``; ``transaction_parameter`` = ``vk-<order id>``."""
    data = await _call(
        "card_payment",
        "POST",
        "/card_token/payment",
        ctx,
        {
            "service_id": _service_id(),
            "card_token": card_token,
            "amount": int(amount_soum),
            "transaction_parameter": transaction_parameter,
        },
    )
    raw_status = data.get("payment_status")
    try:
        payment_status = float(raw_status)
    except (TypeError, ValueError):
        payment_status = float("nan")
    if payment_status == payment_status and payment_status < 0:
        _log.info("[click-merchant] payment declined order=%s status=%s", ctx.get("order_id"), raw_status)
        raise ClickMerchantError("card_payment", "declined", STAGE_FALLBACK["card_payment"], int(payment_status))
    return {
        "payment_id": _id_of("card_payment", data.get("payment_id")),
        "payment_status": int(payment_status) if payment_status == payment_status else 1,
    }


async def create_invoice(
    phone: str, amount_soum: int, merchant_trans_id: str, ctx: dict[str, Any]
) -> dict[str, str]:
    """``POST /invoice/create``: an invoice to the Click app of ``phone`` (``998XXXXXXXXX``)."""
    data = await _call(
        "invoice_create",
        "POST",
        "/invoice/create",
        ctx,
        {
            "service_id": _service_id(),
            "amount": int(amount_soum),
            "phone_number": phone,
            "merchant_trans_id": merchant_trans_id,
        },
    )
    return {"invoice_id": _id_of("invoice_create", data.get("invoice_id"))}


async def invoice_status(invoice_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """``GET /invoice/status/:service_id/:invoice_id``."""
    iid = _id_of("invoice_status", invoice_id)
    data = await _call("invoice_status", "GET", f"/invoice/status/{_service_id()}/{iid}", ctx)
    note = data.get("invoice_status_note")
    return {"invoice_status": data.get("invoice_status"), "note": note if isinstance(note, str) else ""}


async def payment_status(payment_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """``GET /payment/status/:service_id/:payment_id``."""
    pid = _id_of("payment_status", payment_id)
    data = await _call("payment_status", "GET", f"/payment/status/{_service_id()}/{pid}", ctx)
    return {"payment_status": data.get("payment_status")}


async def payment_status_by_order(order_id: str, day: str, ctx: dict[str, Any]) -> dict[str, str]:
    """``GET /payment/status_by_mti/:service_id/vk-<order id>/YYYY-MM-DD``."""
    if not UUID_RE.match(order_id) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ClickMerchantError("payment_status", "unknown", "generic")
    data = await _call(
        "payment_status",
        "GET",
        f"/payment/status_by_mti/{_service_id()}/vk-{order_id}/{day}",
        {**ctx, "order_id": order_id},
    )
    return {"payment_id": _id_of("payment_status", data.get("payment_id"))}
