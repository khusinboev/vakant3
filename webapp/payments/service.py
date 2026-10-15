"""Payment orders and turning them into balance (port of SlaydX ``lib/server/payments.ts``,
``payment-bonus.ts``, ``payment-events.ts``, ``click-direct.ts``, ``checkout-url.ts``).

Idempotency is vital: Click repeats callbacks. SlaydX locks the order row
(``SELECT ... FOR UPDATE``); SQLite has no row locks, so every state change
here is ONE conditional ``UPDATE payment_orders ... WHERE state IN (...)`` and
it is the FIRST write of its transaction (the ledger's write-first rule:
the database write lock then serializes concurrent callers, and the loser's
UPDATE matches zero rows). Only the caller whose UPDATE flipped the order to
``paid`` credits the balance, in the same transaction, through
``ledger.apply_balance_change`` with the unique reference
``click:<click_trans_id>`` (and ``payment-bonus:<order id>`` for the bonus) as
the second guard.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from webapp.core import errors, ledger
from webapp.core.admin_settings import get_admin_settings
from webapp.core.config import get_settings
from webapp.payments import merchant
from webapp.payments.config import (
    MAX_TOPUP_SOUM,
    MIN_TOPUP_SOUM,
    UUID_RE,
    click_config,
    click_order_ref,
    normalize_card_number,
    normalize_phone,
    normalize_sms_code,
    parse_expiry,
    payment_bonus_amount,
    topup_amount_valid,
)

_log = logging.getLogger(__name__)

COLS = (
    "seq, id, user_id, provider, purpose, amount_soum, state, provider_txn, prepare_id, "
    "create_time, perform_time, cancel_time, cancel_reason, click_method, click_invoice_id, "
    "click_card_token, click_payment_id, bonus_percent, bonus_amount, created_at, updated_at"
)


@dataclass
class Order:
    seq: int
    id: str
    user_id: int
    provider: str
    purpose: str
    amount_soum: int
    state: str
    provider_txn: str | None
    prepare_id: int | None
    create_time: int
    perform_time: int
    cancel_time: int
    cancel_reason: int | None
    click_method: str | None
    click_invoice_id: int | None
    click_card_token: str | None
    click_payment_id: int | None
    bonus_percent: int
    bonus_amount: int
    created_at: int
    updated_at: int

    def public(self) -> dict[str, Any]:
        """What the user's own client may see (never the card token)."""
        return {
            "id": self.id,
            "provider": self.provider,
            "purpose": self.purpose,
            "amount": self.amount_soum,
            "state": self.state,
            "method": self.click_method,
            "bonus_amount": self.bonus_amount,
            "created_at": self.created_at,
            "paid_at": self.perform_time // 1000 if self.perform_time else None,
        }


def _order(row) -> Order:
    return Order(
        seq=int(row["seq"]),
        id=str(row["id"]),
        user_id=int(row["user_id"]),
        provider=str(row["provider"]),
        purpose=str(row["purpose"]),
        amount_soum=int(row["amount_soum"]),
        state=str(row["state"]),
        provider_txn=None if row["provider_txn"] is None else str(row["provider_txn"]),
        prepare_id=None if row["prepare_id"] is None else int(row["prepare_id"]),
        create_time=int(row["create_time"] or 0),
        perform_time=int(row["perform_time"] or 0),
        cancel_time=int(row["cancel_time"] or 0),
        cancel_reason=None if row["cancel_reason"] is None else int(row["cancel_reason"]),
        click_method=row["click_method"],
        click_invoice_id=row["click_invoice_id"],
        click_card_token=row["click_card_token"],
        click_payment_id=row["click_payment_id"],
        bonus_percent=int(row["bonus_percent"] or 0),
        bonus_amount=int(row["bonus_amount"] or 0),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


async def create_order(db, *, user_id: int, amount: Any, method: str | None) -> Order:
    """A new ``created`` top-up order. Caller has checked that payments are enabled."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        value = float("nan")
    if value != value or value in (float("inf"), float("-inf")):
        raise errors.api_error(400, errors.TOPUP_AMOUNT_INVALID, min=MIN_TOPUP_SOUM, max=MAX_TOPUP_SOUM)
    rounded = int(value + 0.5) if value >= 0 else -int(-value + 0.5)
    if not topup_amount_valid(rounded):
        raise errors.api_error(400, errors.TOPUP_AMOUNT_INVALID, min=MIN_TOPUP_SOUM, max=MAX_TOPUP_SOUM)
    order_id = str(uuid.uuid4())
    now = int(time.time())
    await db.execute(
        "INSERT INTO payment_orders (id, user_id, provider, purpose, amount_soum, click_method, "
        "created_at, updated_at) VALUES (?, ?, 'click', 'topup', ?, ?, ?, ?)",
        (order_id, int(user_id), rounded, method, now, now),
    )
    await db.commit()
    _log.info("[payments] order created order=%s user=%s amount=%s method=%s", order_id, user_id, rounded, method)
    order = await find_order(db, order_id)
    assert order is not None
    return order


async def find_order(db, order_id: str) -> Order | None:
    if not UUID_RE.match(str(order_id or "")):
        return None
    cursor = await db.execute(f"SELECT {COLS} FROM payment_orders WHERE id = ?", (str(order_id).lower(),))
    row = await cursor.fetchone()
    return _order(row) if row else None


async def find_user_order(db, user_id: int, order_id: str) -> Order | None:
    """Ownership is enforced in SQL: a foreign order reads exactly like a missing one."""
    if not UUID_RE.match(str(order_id or "")):
        return None
    cursor = await db.execute(
        f"SELECT {COLS} FROM payment_orders WHERE id = ? AND user_id = ?",
        (str(order_id).lower(), int(user_id)),
    )
    row = await cursor.fetchone()
    return _order(row) if row else None


async def list_orders(db, user_id: int, limit: int = 20) -> list[Order]:
    cursor = await db.execute(
        f"SELECT {COLS} FROM payment_orders WHERE user_id = ? ORDER BY created_at DESC, seq DESC LIMIT ?",
        (int(user_id), max(1, min(int(limit), 100))),
    )
    return [_order(row) for row in await cursor.fetchall()]


def checkout_url(order: Order) -> str:
    """``https://my.click.uz/services/pay`` — the Click app deeplink and the page fallback."""
    cfg = click_config()
    if cfg is None:
        raise errors.api_error(503, errors.PAYMENTS_DISABLED)
    bot = (get_settings().BOT_USERNAME or "").strip().lstrip("@")
    params = {
        "service_id": cfg.service_id,
        "merchant_id": cfg.merchant_id,
        "amount": f"{order.amount_soum:.2f}",
        "transaction_param": click_order_ref(order.id),
    }
    if bot:
        # Back to the bot chat in Telegram (the Mini App opens from there).
        params["return_url"] = f"https://t.me/{bot}"
    return f"https://my.click.uz/services/pay?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Shop API state machine
# ---------------------------------------------------------------------------


async def attach_transaction(db, order_id: str, txn: str, create_time: int) -> bool:
    """Binds the order to Click's ``click_trans_id`` (Prepare). False = busy / foreign txn."""
    now = int(time.time())
    try:
        cursor = await db.execute(
            """
            UPDATE payment_orders
               SET provider_txn = ?, state = 'pending', create_time = ?,
                   prepare_id = COALESCE(prepare_id, seq), updated_at = ?
             WHERE id = ? AND state IN ('created', 'pending')
               AND (provider_txn IS NULL OR provider_txn = ?)
            """,
            (txn, int(create_time), now, order_id, txn),
        )
        changed = int(cursor.rowcount or 0)
        await db.commit()
    except sqlite3.IntegrityError:
        # The same click_trans_id is already bound to ANOTHER order.
        await db.rollback()
        return False
    if changed:
        return True
    order = await find_order(db, order_id)
    if order is None:
        return False
    if order.state in ("paid", "cancelled"):
        return order.provider_txn == txn
    return False


def check_click_complete(order: Order, params: dict[str, str]) -> str | None:
    """None when Complete matches the Prepare, else the ``error_note`` for -6."""
    if not order.provider_txn or order.prepare_id is None:
        return "Prepare qilinmagan"
    sent = str(params.get("merchant_prepare_id") or "").strip()
    if not sent.isdigit() or not sent.isascii() or int(sent) != order.prepare_id:
        return "prepare_id mos emas"
    if order.provider_txn != str(params.get("click_trans_id") or ""):
        return "click_trans_id mos emas"
    return None


async def settle_order(db, order_id: str, perform_time: int) -> tuple[str, Order | None]:
    """Credit the order once. Returns (paid | already_paid | cancelled | not_found, order)."""
    now = int(time.time())
    try:
        cursor = await db.execute(
            """
            UPDATE payment_orders
               SET state = 'paid', click_card_token = NULL, perform_time = ?,
                   create_time = CASE WHEN create_time = 0 THEN ? ELSE create_time END,
                   updated_at = ?
             WHERE id = ? AND state IN ('created', 'pending')
            """,
            (int(perform_time), int(perform_time), now, order_id),
        )
        if not cursor.rowcount:
            await db.rollback()
            order = await find_order(db, order_id)
            if order is None:
                return "not_found", None
            return ("cancelled" if order.state == "cancelled" else "already_paid"), order

        order = await find_order(db, order_id)
        assert order is not None
        await ledger.apply_balance_change(
            db,
            user_id=order.user_id,
            amount=order.amount_soum,
            kind="topup",
            note="click",
            reference=f"click:{order.provider_txn or order.id}",
        )
        # The percent in force when the order SETTLES, read inside this transaction.
        percent = int((await get_admin_settings(db)).get("payment_bonus_percent") or 0)
        bonus = payment_bonus_amount(order.amount_soum, percent)
        paid_bonus = 0
        if bonus > 0:
            await db.execute("SAVEPOINT payment_bonus")
            try:
                await ledger.apply_balance_change(
                    db,
                    user_id=order.user_id,
                    amount=bonus,
                    kind="topup_bonus",
                    note=f"{percent}%",
                    reference=f"payment-bonus:{order.id}",
                )
                await db.execute("RELEASE SAVEPOINT payment_bonus")
                paid_bonus = bonus
            except sqlite3.IntegrityError:
                # Already written by another path: drop only the bonus, keep the top-up.
                await db.execute("ROLLBACK TO SAVEPOINT payment_bonus")
                await db.execute("RELEASE SAVEPOINT payment_bonus")
                _log.info("[payment-bonus] already written order=%s", order.id)
        await db.execute(
            "UPDATE payment_orders SET bonus_percent = ?, bonus_amount = ? WHERE id = ?",
            (percent if paid_bonus else 0, paid_bonus, order.id),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    order = await find_order(db, order_id)
    _log.info(
        "[payments] settle: paid order=%s user=%s amount=%s bonus=%s",
        order_id,
        order.user_id if order else None,
        order.amount_soum if order else None,
        paid_bonus,
    )
    return "paid", order


async def cancel_order(db, order_id: str, cancel_time: int, reason: int | None) -> tuple[str, Order | None]:
    """Cancel an unpaid order (paid stays paid). (cancelled | already_cancelled | paid | not_found)."""
    cursor = await db.execute(
        """
        UPDATE payment_orders
           SET state = 'cancelled', cancel_time = ?, cancel_reason = ?, click_card_token = NULL,
               updated_at = ?
         WHERE id = ? AND state IN ('created', 'pending')
        """,
        (int(cancel_time), reason, int(time.time()), order_id),
    )
    changed = int(cursor.rowcount or 0)
    await db.commit()
    order = await find_order(db, order_id)
    if order is None:
        return "not_found", None
    if changed:
        _log.info("[payments] cancel: cancelled order=%s reason=%s", order_id, reason)
        return "cancelled", order
    return ("paid" if order.state == "paid" else "already_cancelled"), order


# ---------------------------------------------------------------------------
# Webhook trail (SlaydX payment-events.ts)
# ---------------------------------------------------------------------------

_SECRET_KEYS = {
    "sign_string", "sign", "signature", "password", "passwd", "secret", "secret_key", "key",
    "api_key", "token", "access_token", "authorization",
}
MAX_PAYLOAD_CHARS = 16_000
MAX_FIELD_CHARS = 200


def redact_payload(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "[DEPTH]"
    if isinstance(value, list):
        return [redact_payload(v, depth + 1) for v in value[:100]]
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if str(k).lower() in _SECRET_KEYS else redact_payload(v, depth + 1)
            for k, v in value.items()
        }
    return value


def _clip(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)[:MAX_FIELD_CHARS]


async def record_payment_event(
    db, *, method: str, order_id: Any, provider_txn: Any, payload: Any, response_code: int | None
) -> None:
    """Never raises: the answer to Click must not depend on the audit insert."""
    try:
        text = json.dumps(redact_payload(payload), ensure_ascii=False, default=str)
        if len(text) > MAX_PAYLOAD_CHARS:
            text = json.dumps({"truncated": True, "head": text[:MAX_PAYLOAD_CHARS]})
        await db.execute(
            "INSERT INTO payment_events (provider, method, order_id, provider_txn, payload, "
            "response_code, received_at) VALUES ('click', ?, ?, ?, ?, ?, ?)",
            (_clip(method) or "?", _clip(order_id), _clip(provider_txn), text, response_code, int(time.time())),
        )
        await db.commit()
    except Exception as exc:
        _log.error("[payments] click event not recorded: %s", type(exc).__name__)
        try:
            await db.rollback()
        except Exception:  # pragma: no cover - connection gone
            pass


# ---------------------------------------------------------------------------
# Abuse limits (DB fixed windows, shared by all workers)
# ---------------------------------------------------------------------------


async def hit_limit(db, bucket: str, limit: int, window_seconds: int) -> None:
    """Count one hit; 429 RATE_LIMITED{retry_after} past ``limit`` in the window."""
    now = int(time.time())
    window_start = now - now % int(window_seconds)
    await db.execute(
        "INSERT INTO payment_rate_limits (bucket, window_start, hits) VALUES (?, ?, 1) "
        "ON CONFLICT(bucket, window_start) DO UPDATE SET hits = hits + 1",
        (bucket, window_start),
    )
    cursor = await db.execute(
        "SELECT hits FROM payment_rate_limits WHERE bucket = ? AND window_start = ?",
        (bucket, window_start),
    )
    row = await cursor.fetchone()
    await db.commit()
    if row is not None and int(row[0]) > int(limit):
        raise errors.api_error(
            429, errors.RATE_LIMITED, retry_after=window_start + int(window_seconds) - now
        )


def _phone_key(phone: str) -> str:
    # Keyed: a plain hash of a phone number is reversible by brute force.
    secret = (get_settings().WEBAPP_SECRET or "").encode()
    return hmac.new(secret, f"click-phone:{phone}".encode(), hashlib.sha256).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Direct methods (SlaydX click-direct.ts). Nothing here credits a balance.
# ---------------------------------------------------------------------------

ORDER_STATUS = {"paid": "paid", "cancelled": "cancelled"}


def assert_payments_enabled() -> None:
    if click_config() is None:
        raise errors.api_error(503, errors.PAYMENTS_DISABLED)


async def _load_payable_order(db, user_id: int, order_id: str) -> Order:
    order = await find_user_order(db, user_id, order_id)
    if order is None:
        raise errors.not_found("order")
    if order.state == "paid":
        raise errors.api_error(409, errors.ORDER_ALREADY_PAID)
    if order.state == "cancelled":
        raise errors.api_error(409, errors.ORDER_CANCELLED)
    return order


def _merchant_error(exc: merchant.ClickMerchantError):
    down = exc.failure in ("unavailable", "config")
    if down:
        return errors.api_error(503, errors.CLICK_UNAVAILABLE, stage=exc.stage)
    return errors.api_error(422, errors.CLICK_DECLINED, stage=exc.stage, reason=exc.reason)


async def _state_of(db, user_id: int, order_id: str) -> str:
    order = await find_user_order(db, user_id, order_id)
    return ORDER_STATUS.get(order.state, "pending") if order else "pending"


async def start_card_payment(db, *, user_id: int, order_id: str, card_number: str, expire_date: str) -> dict:
    """Step 1 of "Karta": a ONE-TIME card token; Click texts a code to the card owner."""
    assert_payments_enabled()
    card = normalize_card_number(card_number)
    if not card:
        raise errors.validation_error("card_number")
    mmyy, reason = parse_expiry(expire_date)
    if not mmyy:
        raise errors.api_error(400, errors.VALIDATION_ERROR, field="expire_date", reason=reason)

    await hit_limit(db, f"click-card:u:{int(user_id)}", 6, 3600)
    order = await _load_payable_order(db, user_id, order_id)
    await hit_limit(db, f"click-card:o:{order.id}", 3, 900)

    try:
        token = await merchant.request_card_token(card, mmyy, {"order_id": order.id, "method": "card"})
    except merchant.ClickMerchantError as exc:
        raise _merchant_error(exc) from None
    cursor = await db.execute(
        "UPDATE payment_orders SET click_method = 'card', click_card_token = ?, updated_at = ? "
        "WHERE id = ? AND user_id = ? AND state IN ('created', 'pending')",
        (token["card_token"], int(time.time()), order.id, int(user_id)),
    )
    saved = int(cursor.rowcount or 0)
    await db.commit()
    if not saved:
        raise errors.api_error(409, errors.ORDER_STATE_CHANGED)
    _log.info("[click-direct] SMS sent order=%s", order.id)
    return {"phone_masked": token["phone_masked"]}


async def confirm_card_payment(db, *, user_id: int, order_id: str, sms_code: str) -> dict:
    """Step 2: the SMS code, then the payment. The credit arrives via the Shop API."""
    assert_payments_enabled()
    code = normalize_sms_code(sms_code)
    if not code:
        raise errors.validation_error("sms_code")

    await hit_limit(db, f"click-verify:u:{int(user_id)}", 15, 900)
    order = await _load_payable_order(db, user_id, order_id)
    if not order.click_card_token:
        raise errors.api_error(409, errors.CARD_TOKEN_MISSING)
    await hit_limit(db, f"click-verify:o:{order.id}", 5, 900)
    card_token = order.click_card_token
    ctx = {"order_id": order.id, "method": "card"}

    try:
        await merchant.verify_card_token(card_token, code, ctx)
    except merchant.ClickMerchantError as exc:
        raise _merchant_error(exc) from None

    # Claim the token: only ONE concurrent confirm submits the payment.
    cursor = await db.execute(
        "UPDATE payment_orders SET click_card_token = NULL, updated_at = ? "
        "WHERE id = ? AND user_id = ? AND click_card_token = ? AND state IN ('created', 'pending')",
        (int(time.time()), order.id, int(user_id), card_token),
    )
    claimed = int(cursor.rowcount or 0)
    await db.commit()
    if not claimed:
        return {"status": await _state_of(db, user_id, order.id)}

    try:
        paid = await merchant.pay_with_card_token(
            card_token, order.amount_soum, click_order_ref(order.id), ctx
        )
    except merchant.ClickMerchantError as exc:
        if exc.outcome_unknown:
            # The charge may have gone through: do not say "failed"; the client keeps polling.
            _log.warning("[click-direct] payment outcome unknown order=%s code=%s", order.id, exc.error_code)
            return {"status": await _state_of(db, user_id, order.id)}
        raise _merchant_error(exc) from None
    try:
        await db.execute(
            "UPDATE payment_orders SET click_payment_id = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (int(paid["payment_id"]), int(time.time()), order.id, int(user_id)),
        )
        await db.commit()
    except Exception as exc:
        # Bookkeeping only: the charge already went through.
        _log.warning("[click-direct] click_payment_id not saved order=%s (%s)", order.id, type(exc).__name__)
        await db.rollback()
    return {"status": await _state_of(db, user_id, order.id)}


async def send_click_invoice(db, *, user_id: int, order_id: str, phone: str) -> dict:
    """"Telefon raqam": an invoice to the Click app registered on ``phone``."""
    assert_payments_enabled()
    normalized = normalize_phone(phone)
    if not normalized:
        raise errors.validation_error("phone")

    await hit_limit(db, f"click-invoice:u:{int(user_id)}", 5, 3600)
    order = await _load_payable_order(db, user_id, order_id)
    await hit_limit(db, f"click-invoice:o:{order.id}", 3, 900)
    await hit_limit(db, f"click-invoice:p:{_phone_key(normalized)}", 5, 86_400)

    try:
        invoice = await merchant.create_invoice(
            normalized, order.amount_soum, click_order_ref(order.id), {"order_id": order.id, "method": "phone"}
        )
    except merchant.ClickMerchantError as exc:
        raise _merchant_error(exc) from None
    cursor = await db.execute(
        "UPDATE payment_orders SET click_method = 'phone', click_invoice_id = ?, updated_at = ? "
        "WHERE id = ? AND user_id = ? AND state IN ('created', 'pending')",
        (int(invoice["invoice_id"]), int(time.time()), order.id, int(user_id)),
    )
    saved = int(cursor.rowcount or 0)
    await db.commit()
    if not saved:
        # The invoice already exists at Click; a state change meanwhile is harmless.
        _log.warning("[click-direct] invoice sent but order no longer payable order=%s", order.id)
    _log.info("[click-direct] invoice sent order=%s", order.id)
    return {"status": "sent"}
