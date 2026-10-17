"""Click Shop API callback: Prepare (``action=0``) and Complete (``action=1``).

Port of SlaydX ``app/api/payments/click/route.ts`` + ``clickSignatureValid``.
Click calls SlaydX (the service owner); SlaydX forwards every request whose
``merchant_trans_id`` starts with ``vk-`` to ``POST /api/payments/click`` with
the raw body and Content-Type unchanged and relays our HTTP 200 JSON body back
to Click. So:

* the md5 signature is the ONLY authentication (no IP check, no trust in
  ``X-Forwarded-By``);
* every answer is HTTP 200 with Click's JSON shape, errors included;
* a ``merchant_trans_id`` without the ``vk-`` prefix is not ours: -5.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

from webapp.payments import service
from webapp.payments.config import order_id_from_ref, shop_credentials

_log = logging.getLogger(__name__)

CLICK_OK = 0
CLICK_SIGN = -1
CLICK_AMOUNT = -2
CLICK_ACTION = -3
CLICK_ALREADY_PAID = -4
CLICK_NO_USER = -5
CLICK_NO_TXN = -6
CLICK_UPDATE_FAILED = -7
CLICK_BAD_REQUEST = -8
CLICK_CANCELLED = -9

SIGNED_FIELDS = (
    "click_trans_id",
    "service_id",
    "merchant_trans_id",
    "merchant_prepare_id",
    "amount",
    "action",
    "sign_time",
    "sign_string",
)


def click_signature_valid(p: dict[str, str], secret_key: str) -> bool:
    """md5(click_trans_id + service_id + SECRET + merchant_trans_id +
    [merchant_prepare_id, Complete only] + amount + action + sign_time)."""
    if not secret_key:
        return False
    parts = [
        p.get("click_trans_id") or "",
        p.get("service_id") or "",
        secret_key,
        p.get("merchant_trans_id") or "",
    ]
    if p.get("action") == "1":
        parts.append(p.get("merchant_prepare_id") or "")
    parts += [p.get("amount") or "", p.get("action") or "", p.get("sign_time") or ""]
    expected = hashlib.md5("".join(parts).encode("utf-8")).hexdigest()
    return hmac.compare_digest(expected, str(p.get("sign_string") or "").lower())


def _js_number(value: Any) -> float:
    """``Number(x)`` as JavaScript reads a form field ("" -> 0, junk -> NaN)."""
    text = str(value if value is not None else "").strip()
    if text == "":
        return 0.0
    try:
        return float(text)
    except ValueError:
        return float("nan")


def reply(p: dict[str, str], error: int, note: str, **extra: Any) -> dict[str, Any]:
    trans = _js_number(p.get("click_trans_id") or 0)
    return {
        "click_trans_id": int(trans) if trans == trans and abs(trans) != float("inf") else 0,
        "merchant_trans_id": p.get("merchant_trans_id") or "",
        "error": error,
        "error_note": note,
        **extra,
    }


def normalize_params(raw: Any) -> dict[str, str] | None:
    """Form or JSON values as strings (a JSON integer 10000 reads as "10000")."""
    if not isinstance(raw, dict):
        return None
    out: dict[str, str] = {}
    for key, value in raw.items():
        if value is None:
            continue
        if isinstance(value, bool):
            out[str(key)] = "true" if value else "false"
        elif isinstance(value, float) and value.is_integer():
            out[str(key)] = str(int(value))
        else:
            out[str(key)] = str(value)
    return out


async def _handle(db, p: dict[str, str]) -> dict[str, Any]:
    """Business logic of a request whose signature already checked out."""
    order_id = order_id_from_ref(p.get("merchant_trans_id") or "")
    order = await service.find_order(db, order_id) if order_id else None
    if order is None or order.provider != "click":
        return reply(p, CLICK_NO_USER, "Buyurtma topilmadi")

    # Click sends so'm, possibly as N.NN.
    amount = _js_number(p.get("amount"))
    if amount != amount or abs(amount) == float("inf") or int(amount + 0.5) != order.amount_soum:
        return reply(p, CLICK_AMOUNT, "Summa mos emas")
    if order.state == "cancelled":
        return reply(p, CLICK_CANCELLED, "Bekor qilingan")

    action = p.get("action")
    click_error = _js_number(p.get("error") or 0)
    if action == "0":
        if order.state == "paid":
            return reply(p, CLICK_ALREADY_PAID, "Allaqachon to'langan")
        ok = await service.attach_transaction(db, order.id, str(p.get("click_trans_id")), int(time.time() * 1000))
        if not ok:
            return reply(p, CLICK_UPDATE_FAILED, "Buyurtma band")
        prepared = await service.find_order(db, order.id)
        if prepared is None or not prepared.prepare_id:
            return reply(p, CLICK_UPDATE_FAILED, "prepare_id yaratilmadi")
        return reply(p, CLICK_OK, "Success", merchant_prepare_id=prepared.prepare_id)

    if action == "1":
        # Click's own error on an order that was never prepared: -9, nothing to cancel.
        if click_error < 0 and not order.provider_txn:
            return reply(p, CLICK_CANCELLED, "Click tomonda bekor qilindi")
        mismatch = service.check_click_complete(order, p)
        if mismatch:
            return reply(p, CLICK_NO_TXN, mismatch)
        if click_error < 0:
            status, _ = await service.cancel_order(db, order.id, int(time.time() * 1000), int(click_error))
            if status == "paid":
                return reply(p, CLICK_ALREADY_PAID, "Allaqachon to'langan")
            return reply(p, CLICK_CANCELLED, "Click tomonda bekor qilindi")
        status, _ = await service.settle_order(db, order.id, order.perform_time or int(time.time() * 1000))
        if status == "cancelled":
            return reply(p, CLICK_CANCELLED, "Bekor qilingan")
        if status == "already_paid":
            return reply(p, CLICK_ALREADY_PAID, "Allaqachon to'langan")
        if status == "not_found":
            return reply(p, CLICK_NO_USER, "Buyurtma topilmadi")
        return reply(
            p,
            CLICK_OK,
            "Success",
            merchant_confirm_id=order.prepare_id,
            merchant_prepare_id=order.prepare_id,
        )

    return reply(p, CLICK_ACTION, "Action topilmadi")


async def handle_click(db, raw: Any) -> dict[str, Any]:
    """The whole callback: config, required fields, service id, signature, logic, trail."""
    creds = shop_credentials()
    if creds is None:
        return reply({}, CLICK_BAD_REQUEST, "Click sozlanmagan")
    service_id, secret = creds

    p = normalize_params(raw)
    if not p or not p.get("click_trans_id") or not p.get("merchant_trans_id") or not p.get("sign_string"):
        return reply(p or {}, CLICK_BAD_REQUEST, "So'rov to'liq emas")
    if p.get("service_id") != service_id:
        return reply(p, CLICK_SIGN, "service_id mos emas")
    if not click_signature_valid(p, secret):
        return reply(p, CLICK_SIGN, "SIGN CHECK FAILED")

    try:
        out = await _handle(db, p)
    except Exception:
        _log.exception(
            "[click] webhook error order=%s txn=%s action=%s",
            p.get("merchant_trans_id"),
            p.get("click_trans_id"),
            p.get("action"),
        )
        try:
            await db.rollback()
        except Exception:  # pragma: no cover - connection gone
            pass
        out = reply(p, CLICK_UPDATE_FAILED, "Ichki xatolik")

    action = p.get("action")
    method = "prepare" if action == "0" else "complete" if action == "1" else f"action:{action or ''}"
    await service.record_payment_event(
        db,
        method=method,
        order_id=p.get("merchant_trans_id"),
        provider_txn=p.get("click_trans_id"),
        payload=p,
        response_code=int(out["error"]),
    )
    return out
