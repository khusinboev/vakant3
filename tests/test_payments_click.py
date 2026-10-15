"""Click top-ups (webapp/payments) against the REAL app (tests/b3_support harness).

Nothing reaches Click: the Merchant API goes through ``merchant._send`` (stubbed
per test) and the Shop API callbacks are built and md5-signed here exactly as
Click (or SlaydX's forwarder, which relays Click's raw body) sends them.
Credentials are fake values set on ``get_settings()``; ids are synthetic.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import date

import pytest

from tests import b3_support
from tests.b3_support import ADMIN, USER, USER2, VIEWER
from webapp.core.config import get_settings
from webapp.payments import config as pay_config
from webapp.payments import merchant, shop

harness = b3_support.harness

SERVICE_ID = "77001"
MERCHANT_ID = "55001"
SECRET = "test-click-secret-not-real"
MERCHANT_USER_ID = "33001"


@pytest.fixture
def click_on(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "CLICK_SERVICE_ID", SERVICE_ID, raising=False)
    monkeypatch.setattr(settings, "CLICK_MERCHANT_ID", MERCHANT_ID, raising=False)
    monkeypatch.setattr(settings, "CLICK_SECRET_KEY", SECRET, raising=False)
    monkeypatch.setattr(settings, "CLICK_MERCHANT_USER_ID", MERCHANT_USER_ID, raising=False)


class ClickStub:
    """Stand-in for ``merchant._send``: records calls, answers per path."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.answers: dict[str, tuple[int, dict | str] | Exception] = {
            "/card_token/request": (200, {"error_code": 0, "card_token": "TOK-1", "phone_number": "99890***4567"}),
            "/card_token/verify": (200, {"error_code": 0, "card_number": "8600 **** **** 1234"}),
            "/card_token/payment": (200, {"error_code": 0, "payment_id": 4242, "payment_status": 1}),
            "/invoice/create": (200, {"error_code": 0, "invoice_id": 7777}),
        }

    async def send(self, method, url, headers, body):
        path = url.replace(merchant.CLICK_MERCHANT_BASE, "")
        self.calls.append({"method": method, "path": path, "headers": dict(headers), "body": body})
        answer = self.answers[path]
        if isinstance(answer, Exception):
            raise answer
        status, data = answer
        return status, data if isinstance(data, str) else json.dumps(data)

    def paths(self) -> list[str]:
        return [c["path"] for c in self.calls]


@pytest.fixture
def click_api(monkeypatch):
    stub = ClickStub()
    monkeypatch.setattr(merchant, "_send", stub.send)
    return stub


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def sign(p: dict, secret: str = SECRET) -> str:
    parts = [p.get("click_trans_id", ""), p.get("service_id", ""), secret, p.get("merchant_trans_id", "")]
    if p.get("action") == "1":
        parts.append(p.get("merchant_prepare_id", ""))
    parts += [p.get("amount", ""), p.get("action", ""), p.get("sign_time", "")]
    return hashlib.md5("".join(str(x) for x in parts).encode()).hexdigest()


def click_form(order_id: str, *, action: str, amount="10000", txn="910001", prepare_id=None,
               error=None, service_id=SERVICE_ID, secret=SECRET, ref=None, bad_sign=False) -> dict:
    p = {
        "click_trans_id": txn,
        "service_id": service_id,
        "click_paydoc_id": "1",
        "merchant_trans_id": ref if ref is not None else f"vk-{order_id}",
        "amount": str(amount),
        "action": action,
        "error": "0" if error is None else str(error),
        "error_note": "Success",
        "sign_time": "2026-10-16 12:00:00",
    }
    if prepare_id is not None:
        p["merchant_prepare_id"] = str(prepare_id)
    p["sign_string"] = "0" * 32 if bad_sign else sign(p, secret)
    return p


async def post_click(h, form: dict, headers: dict | None = None) -> dict:
    response = await h.http.post("/api/payments/click", data=form, headers=headers or {})
    assert response.status_code == 200, response.text
    return response.json()


async def make_order(h, user_id=USER, amount=10_000, method="app") -> dict:
    response = await h.http.post(
        "/api/payments/orders", json={"amount": amount, "method": method}, headers=await h.session(user_id)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def prepare(h, order_id: str, **kw) -> int:
    out = await post_click(h, click_form(order_id, action="0", **kw))
    assert out["error"] == 0, out
    assert isinstance(out["merchant_prepare_id"], int)
    return out["merchant_prepare_id"]


async def order_row(h, order_id: str) -> dict:
    rows = await h.query("SELECT * FROM payment_orders WHERE id = ?", (order_id,))
    return rows[0]


async def credits(h, user_id: int, kind: str) -> list[dict]:
    return await h.query(
        "SELECT amount, reference FROM wallet_transactions WHERE user_id = ? AND kind = ? ORDER BY id",
        (user_id, kind),
    )


async def set_bonus(h, percent: int) -> None:
    await h.execute("UPDATE webapp_admin_settings SET payment_bonus_percent = ?", (percent,))


# ---------------------------------------------------------------------------
# Signature (pure)
# ---------------------------------------------------------------------------


def test_signature_valid_case_insensitive_and_prepare_id_only_in_complete():
    oid = str(uuid.uuid4())
    prep = click_form(oid, action="0")
    assert shop.click_signature_valid(prep, SECRET)
    assert shop.click_signature_valid({**prep, "sign_string": prep["sign_string"].upper()}, SECRET)
    assert not shop.click_signature_valid(prep, "other-secret")
    assert not shop.click_signature_valid(prep, "")
    assert not shop.click_signature_valid({**prep, "amount": "10001"}, SECRET)

    done = click_form(oid, action="1", prepare_id=5)
    assert shop.click_signature_valid(done, SECRET)
    # Complete signed WITHOUT the prepare id is rejected; Prepare ignores it.
    unsigned = dict(done)
    unsigned["sign_string"] = sign({k: v for k, v in done.items() if k != "merchant_prepare_id"})
    assert not shop.click_signature_valid(unsigned, SECRET)
    assert shop.click_signature_valid({**prep, "merchant_prepare_id": "99"}, SECRET)


def test_order_ref_prefix_rules():
    oid = str(uuid.uuid4())
    assert pay_config.click_order_ref(oid) == f"vk-{oid}"
    assert pay_config.order_id_from_ref(f"vk-{oid}") == oid
    assert pay_config.order_id_from_ref(oid) is None
    assert pay_config.order_id_from_ref(f"sx-{oid}") is None
    assert pay_config.order_id_from_ref("vk-12345") is None


def test_merchant_auth_header_format():
    assert merchant.click_auth_digest("s3cret", 1700000000) == hashlib.sha1(b"1700000000s3cret").hexdigest()
    header = merchant.click_auth_header("33001", "s3cret", now=1700000000.9)
    assert header == f"33001:{hashlib.sha1(b'1700000000s3cret').hexdigest()}:1700000000"


def test_bonus_and_input_rules():
    assert pay_config.payment_bonus_amount(10_000, 0) == 0
    assert pay_config.payment_bonus_amount(10_000, 10) == 1_000
    assert pay_config.payment_bonus_amount(10_005, 10) == 1_000
    assert pay_config.payment_bonus_amount(10_000, 51) == 0
    assert pay_config.normalize_card_number("8600 1234 5678 9012") == "8600123456789012"
    assert pay_config.normalize_card_number("8600 1234 5678 901") is None
    assert pay_config.parse_expiry("12/27", date(2026, 10, 1)) == ("1227", None)
    assert pay_config.parse_expiry("10/26", date(2026, 10, 31)) == ("1026", None)
    assert pay_config.parse_expiry("09/26", date(2026, 10, 1)) == (None, "expired")
    assert pay_config.parse_expiry("13/27", date(2026, 10, 1)) == (None, "month")
    assert pay_config.normalize_phone("90 123 45 67") == "998901234567"
    assert pay_config.normalize_phone("+998 90 123 45 67") == "998901234567"
    assert pay_config.normalize_phone("12345") is None
    assert pay_config.normalize_sms_code("123") is None
    assert pay_config.normalize_sms_code("123456") == "123456"


# ---------------------------------------------------------------------------
# Shop API callback
# ---------------------------------------------------------------------------


async def test_prepare_complete_credits_once_fractional_amount(harness, click_on):
    h = harness
    order = (await make_order(h))["order"]
    oid = order["id"]
    pid = await prepare(h, oid, amount="10000.00")
    again = await post_click(h, click_form(oid, action="0"))
    assert again["merchant_prepare_id"] == pid, "a Prepare retry returns the same prepare id"

    done = await post_click(h, click_form(oid, action="1", prepare_id=pid, amount="10000.00"))
    assert done == {
        "click_trans_id": 910001,
        "merchant_trans_id": f"vk-{oid}",
        "error": 0,
        "error_note": "Success",
        "merchant_confirm_id": pid,
        "merchant_prepare_id": pid,
    }
    assert await h.balance(USER) == 10_000
    assert await credits(h, USER, "topup") == [{"amount": 10_000, "reference": "click:910001"}]
    row = await order_row(h, oid)
    assert row["state"] == "paid" and row["perform_time"] > 0 and row["provider_txn"] == "910001"


async def test_repeated_complete_is_already_paid_and_bonus_paid_once(harness, click_on):
    h = harness
    await set_bonus(h, 10)
    oid = (await make_order(h, amount=100_000))["order"]["id"]
    pid = await prepare(h, oid, amount="100000")
    first = await post_click(h, click_form(oid, action="1", prepare_id=pid, amount="100000"))
    assert first["error"] == 0
    for _ in range(3):
        again = await post_click(h, click_form(oid, action="1", prepare_id=pid, amount="100000"))
        assert again["error"] == -4
    assert await h.balance(USER) == 110_000
    assert await credits(h, USER, "topup") == [{"amount": 100_000, "reference": "click:910001"}]
    assert await credits(h, USER, "topup_bonus") == [{"amount": 10_000, "reference": f"payment-bonus:{oid}"}]
    row = await order_row(h, oid)
    assert (row["bonus_percent"], row["bonus_amount"]) == (10, 10_000)


async def test_bonus_zero_writes_no_bonus_row(harness, click_on):
    h = harness
    await set_bonus(h, 0)
    oid = (await make_order(h))["order"]["id"]
    pid = await prepare(h, oid)
    assert (await post_click(h, click_form(oid, action="1", prepare_id=pid)))["error"] == 0
    assert await h.balance(USER) == 10_000
    assert await credits(h, USER, "topup_bonus") == []


async def test_concurrent_completes_credit_exactly_once(harness, click_on):
    h = harness
    await set_bonus(h, 10)
    oid = (await make_order(h))["order"]["id"]
    pid = await prepare(h, oid)
    form = click_form(oid, action="1", prepare_id=pid)
    results = await asyncio.gather(*(h.http.post("/api/payments/click", data=form) for _ in range(8)))
    codes = sorted(r.json()["error"] for r in results)
    assert codes.count(0) == 1, codes
    assert all(c in (0, -4, -7) for c in codes), codes
    assert await h.balance(USER) == 11_000
    assert len(await credits(h, USER, "topup")) == 1
    assert len(await credits(h, USER, "topup_bonus")) == 1


async def test_sign_errors_minus_1(harness, click_on):
    h = harness
    oid = (await make_order(h))["order"]["id"]
    assert (await post_click(h, click_form(oid, action="0", bad_sign=True)))["error"] == -1
    assert (await post_click(h, click_form(oid, action="0", secret="not-the-secret")))["error"] == -1
    wrong_service = click_form(oid, action="0", service_id="77002")
    assert (await post_click(h, wrong_service))["error"] == -1
    pid = await prepare(h, oid)
    assert (await post_click(h, click_form(oid, action="1", prepare_id=pid, bad_sign=True)))["error"] == -1
    assert (await order_row(h, oid))["state"] == "pending"
    assert await h.balance(USER) == 0
    # Rejected signatures leave no trail row (only signed requests are recorded).
    assert await h.scalar("SELECT COUNT(*) FROM payment_events WHERE response_code = -1") == 0


async def test_amount_mismatch_minus_2(harness, click_on):
    h = harness
    oid = (await make_order(h))["order"]["id"]
    assert (await post_click(h, click_form(oid, action="0", amount="9999")))["error"] == -2
    pid = await prepare(h, oid)
    assert (await post_click(h, click_form(oid, action="1", prepare_id=pid, amount="10001")))["error"] == -2
    assert (await post_click(h, click_form(oid, action="1", prepare_id=pid, amount="abc")))["error"] == -2
    assert await h.balance(USER) == 0
    assert (await order_row(h, oid))["state"] == "pending"


async def test_unknown_action_minus_3(harness, click_on):
    h = harness
    oid = (await make_order(h))["order"]["id"]
    for action in ("2", "", "x"):
        assert (await post_click(h, click_form(oid, action=action)))["error"] == -3
    assert (await order_row(h, oid))["state"] == "created"


async def test_prepare_after_paid_minus_4(harness, click_on):
    h = harness
    oid = (await make_order(h))["order"]["id"]
    pid = await prepare(h, oid, txn="910050")
    assert (await post_click(h, click_form(oid, action="1", prepare_id=pid, txn="910050")))["error"] == 0
    assert (await post_click(h, click_form(oid, action="0", txn="910050")))["error"] == -4
    assert (await post_click(h, click_form(oid, action="0", txn="910051")))["error"] == -4
    assert (await order_row(h, oid))["provider_txn"] == "910050"
    assert await h.balance(USER) == 10_000


async def test_unknown_or_foreign_order_minus_5(harness, click_on):
    h = harness
    oid = (await make_order(h))["order"]["id"]
    missing = str(uuid.uuid4())
    assert (await post_click(h, click_form(missing, action="0")))["error"] == -5
    # A SlaydX order (no vk- prefix) is not ours even with a valid signature.
    assert (await post_click(h, click_form(oid, action="0", ref=oid)))["error"] == -5
    assert (await post_click(h, click_form(oid, action="0", ref=f"sx-{oid}")))["error"] == -5
    assert (await post_click(h, click_form(oid, action="0", ref="vk-12345")))["error"] == -5
    assert (await order_row(h, oid))["provider_txn"] is None


async def test_complete_without_prepare_minus_6_then_pays_properly(harness, click_on):
    h = harness
    oid = (await make_order(h))["order"]["id"]
    for pid in ("1", "0", "999999"):
        assert (await post_click(h, click_form(oid, action="1", prepare_id=pid)))["error"] == -6
    assert (await post_click(h, click_form(oid, action="1")))["error"] == -6
    row = await order_row(h, oid)
    assert row["state"] == "created" and row["provider_txn"] is None
    assert await h.balance(USER) == 0
    pid = await prepare(h, oid)
    assert (await post_click(h, click_form(oid, action="1", prepare_id=pid)))["error"] == 0
    assert await h.balance(USER) == 10_000


async def test_wrong_prepare_id_or_trans_id_minus_6(harness, click_on):
    h = harness
    oid = (await make_order(h))["order"]["id"]
    other = (await make_order(h, user_id=USER2))["order"]["id"]
    pid = await prepare(h, oid)
    other_pid = await prepare(h, other, txn="910099")
    assert pid != other_pid
    for bad in ("", str(pid + 1), "abc", str(other_pid), "٣"):
        assert (await post_click(h, click_form(oid, action="1", prepare_id=bad)))["error"] == -6, bad
    assert (await post_click(h, click_form(oid, action="1", prepare_id=pid, txn="999999")))["error"] == -6
    assert (await order_row(h, oid))["state"] == "pending"
    assert await h.balance(USER) == 0
    rows = await h.query(
        "SELECT method, response_code, payload FROM payment_events WHERE order_id = ? AND response_code = -6",
        (f"vk-{oid}",),
    )
    assert rows and all(r["method"] == "complete" for r in rows)
    assert all(json.loads(r["payload"])["sign_string"] == "[REDACTED]" for r in rows)


async def test_click_error_cancels_and_paid_stays_paid(harness, click_on):
    h = harness
    oid = (await make_order(h))["order"]["id"]
    pid = await prepare(h, oid)
    assert (await post_click(h, click_form(oid, action="1", prepare_id=pid, error="-5017")))["error"] == -9
    assert (await order_row(h, oid))["state"] == "cancelled"
    assert (await post_click(h, click_form(oid, action="1", prepare_id=pid)))["error"] == -9
    assert (await post_click(h, click_form(oid, action="0")))["error"] == -9
    assert await h.balance(USER) == 0

    o2 = (await make_order(h, user_id=USER2))["order"]["id"]
    p2 = await prepare(h, o2, txn="920001")
    assert (await post_click(h, click_form(o2, action="1", prepare_id=p2, txn="920001")))["error"] == 0
    assert (await post_click(h, click_form(o2, action="1", prepare_id=p2, txn="920001", error="-1")))["error"] == -4
    assert (await order_row(h, o2))["state"] == "paid"
    assert await h.balance(USER2) == 10_000


async def test_click_error_on_unprepared_order_minus_9_untouched(harness, click_on):
    h = harness
    oid = (await make_order(h))["order"]["id"]
    assert (await post_click(h, click_form(oid, action="1", prepare_id="5", error="-5017")))["error"] == -9
    assert (await order_row(h, oid))["state"] == "created"


async def test_not_configured_and_incomplete_minus_8(harness, click_on, monkeypatch):
    h = harness
    oid = (await make_order(h))["order"]["id"]
    form = click_form(oid, action="0")
    incomplete = {k: v for k, v in form.items() if k != "sign_string"}
    assert (await post_click(h, incomplete))["error"] == -8
    monkeypatch.setattr(get_settings(), "CLICK_SECRET_KEY", "", raising=False)
    out = await post_click(h, form)
    assert out["error"] == -8 and out["click_trans_id"] == 0
    assert (await order_row(h, oid))["state"] == "created"


async def test_forwarder_form_and_json_bodies(harness, click_on):
    """SlaydX relays Click's raw body + Content-Type, adding X-Forwarded-By (not trusted)."""
    h = harness
    oid = (await make_order(h))["order"]["id"]
    form = click_form(oid, action="0")
    from urllib.parse import urlencode

    response = await h.http.post(
        "/api/payments/click",
        content=urlencode(form),
        headers={"Content-Type": "application/x-www-form-urlencoded", "X-Forwarded-By": "slaydx"},
    )
    assert response.status_code == 200
    pid = response.json()["merchant_prepare_id"]
    assert response.json()["error"] == 0

    done = click_form(oid, action="1", prepare_id=pid)
    done_json = {**done, "click_trans_id": int(done["click_trans_id"]), "amount": 10000}
    response = await h.http.post(
        "/api/payments/click",
        content=json.dumps(done_json),
        headers={"Content-Type": "application/json", "X-Forwarded-By": "slaydx"},
    )
    assert response.status_code == 200
    assert response.json()["error"] == 0, response.json()
    assert await h.balance(USER) == 10_000

    # The header is informational: it never replaces the signature.
    forged = {**click_form(oid, action="0"), "sign_string": "f" * 32}
    response = await h.http.post("/api/payments/click", data=forged, headers={"X-Forwarded-By": "slaydx"})
    assert response.status_code == 200 and response.json()["error"] == -1
    # Junk body: still HTTP 200 + Click JSON.
    response = await h.http.post(
        "/api/payments/click", content="{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 200 and response.json()["error"] == -8


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------


async def test_disabled_mode(harness):
    h = harness
    headers = await h.session(USER)
    cfg = await h.http.get("/api/payments/config", headers=headers)
    assert cfg.status_code == 200 and cfg.json()["enabled"] is False
    response = await h.http.post("/api/payments/orders", json={"amount": 10_000}, headers=headers)
    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "PAYMENTS_DISABLED"}
    response = await h.http.post(
        "/api/payments/click/invoice", json={"order_id": str(uuid.uuid4()), "phone": "901234567"}, headers=headers
    )
    assert response.json()["detail"] == {"code": "PAYMENTS_DISABLED"}
    assert await h.scalar("SELECT COUNT(*) FROM payment_orders") == 0


async def test_one_missing_env_disables(harness, click_on, monkeypatch):
    monkeypatch.setattr(get_settings(), "CLICK_MERCHANT_USER_ID", "", raising=False)
    response = await harness.http.post(
        "/api/payments/orders", json={"amount": 10_000}, headers=await harness.session(USER)
    )
    assert response.status_code == 503 and response.json()["detail"]["code"] == "PAYMENTS_DISABLED"


async def test_amount_limits_and_checkout_url(harness, click_on):
    h = harness
    headers = await h.session(USER)
    for bad in (999, 10_000_001, 0, -5):
        response = await h.http.post("/api/payments/orders", json={"amount": bad}, headers=headers)
        assert response.status_code == 400, bad
        assert response.json()["detail"] == {"code": "TOPUP_AMOUNT_INVALID", "min": 1000, "max": 10_000_000}
    low = await make_order(h, amount=1_000)
    high = await make_order(h, amount=10_000_000)
    assert low["order"]["amount"] == 1_000 and high["order"]["amount"] == 10_000_000
    url = low["checkout_url"]
    assert url.startswith("https://my.click.uz/services/pay?")
    assert f"transaction_param=vk-{low['order']['id']}" in url
    assert f"service_id={SERVICE_ID}" in url and f"merchant_id={MERCHANT_ID}" in url
    assert "amount=1000.00" in url
    cfg = (await h.http.get("/api/payments/config", headers=headers)).json()
    assert cfg == {"enabled": True, "min_amount": 1000, "max_amount": 10_000_000, "bonus_percent": 0}


async def test_order_create_cap_10_per_5_min(harness, click_on):
    h = harness
    headers = await h.session(USER)
    for _ in range(10):
        assert (await h.http.post("/api/payments/orders", json={"amount": 5000}, headers=headers)).status_code == 201
    response = await h.http.post("/api/payments/orders", json={"amount": 5000}, headers=headers)
    assert response.status_code == 429 and response.json()["detail"]["code"] == "RATE_LIMITED"


async def test_entry_gate_and_ownership(harness, click_on):
    h = harness
    await h.add_user(900_000_000_030, started_at=None)
    response = await h.http.get("/api/payments/orders", headers=await h.session(900_000_000_030))
    assert response.status_code == 403 and response.json()["detail"]["code"] == "BOT_START_REQUIRED"

    oid = (await make_order(h))["order"]["id"]
    other = await h.session(USER2)
    assert (await h.http.get(f"/api/payments/orders/{oid}", headers=other)).status_code == 404
    response = await h.http.post(
        "/api/payments/click/card",
        json={"order_id": oid, "card_number": "8600123456789012", "expire_date": "12/30"},
        headers=other,
    )
    assert response.status_code == 404 and response.json()["detail"] == {"code": "NOT_FOUND", "resource": "order"}
    mine = (await h.http.get(f"/api/payments/orders/{oid}", headers=await h.session(USER))).json()["order"]
    assert mine["state"] == "created" and "click_card_token" not in mine
    listed = (await h.http.get("/api/payments/orders", headers=await h.session(USER))).json()
    assert [o["id"] for o in listed["orders"]] == [oid] and listed["enabled"] is True


async def test_card_flow_happy_path_then_shop_api_settles(harness, click_on, click_api, caplog):
    h = harness
    caplog.set_level(logging.DEBUG, logger="webapp")
    headers = await h.session(USER)
    oid = (await make_order(h, method="card"))["order"]["id"]
    card = "8600123456789012"
    response = await h.http.post(
        "/api/payments/click/card",
        json={"order_id": oid, "card_number": "8600 1234 5678 9012", "expire_date": "12/30"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"phone_masked": "99890***4567"}
    request_call = click_api.calls[0]
    assert request_call["body"] == {
        "service_id": int(SERVICE_ID), "card_number": card, "expire_date": "1230", "temporary": 1
    }
    user_id, digest, ts = request_call["headers"]["Auth"].split(":")
    assert user_id == MERCHANT_USER_ID and digest == merchant.click_auth_digest(SECRET, ts) and len(ts) == 10
    assert (await order_row(h, oid))["click_card_token"] == "TOK-1"

    response = await h.http.post(
        "/api/payments/click/card/verify", json={"order_id": oid, "sms_code": "123456"}, headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "pending"}
    assert click_api.paths() == ["/card_token/request", "/card_token/verify", "/card_token/payment"]
    pay = click_api.calls[2]["body"]
    assert pay == {
        "service_id": int(SERVICE_ID), "card_token": "TOK-1", "amount": 10_000, "transaction_parameter": f"vk-{oid}"
    }
    row = await order_row(h, oid)
    assert row["click_card_token"] is None and row["click_payment_id"] == 4242
    assert await h.balance(USER) == 0, "the Merchant API never credits"

    pid = await prepare(h, oid)
    assert (await post_click(h, click_form(oid, action="1", prepare_id=pid)))["error"] == 0
    assert await h.balance(USER) == 10_000
    state = (await h.http.get(f"/api/payments/orders/{oid}", headers=headers)).json()["order"]["state"]
    assert state == "paid"

    dump = json.dumps(await h.query("SELECT * FROM payment_orders")) + json.dumps(
        await h.query("SELECT * FROM payment_events")
    )
    # Our own loggers only (aiosqlite's DEBUG trace of SQL parameters is off in production).
    logs = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("webapp"))
    assert "[click-direct] SMS sent" in logs
    for secret_value in (card, "8600 1234 5678 9012", "1230", "123456", "TOK-1"):
        assert secret_value not in dump
        assert secret_value not in logs


async def test_card_declined_wrong_sms_and_no_token(harness, click_on, click_api):
    h = harness
    headers = await h.session(USER)
    oid = (await make_order(h, method="card"))["order"]["id"]
    response = await h.http.post(
        "/api/payments/click/card/verify", json={"order_id": oid, "sms_code": "123456"}, headers=headers
    )
    assert response.status_code == 409 and response.json()["detail"] == {"code": "CARD_TOKEN_MISSING"}
    assert click_api.calls == []

    click_api.answers["/card_token/request"] = (200, {"error_code": -5001, "error_note": "Card not found"})
    response = await h.http.post(
        "/api/payments/click/card",
        json={"order_id": oid, "card_number": "8600123456789012", "expire_date": "12/30"},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "CLICK_DECLINED", "stage": "card_request", "reason": "card_not_found"}
    assert (await order_row(h, oid))["click_card_token"] is None

    click_api.answers["/card_token/request"] = (200, {"error_code": 0, "card_token": "TOK-2", "phone_number": ""})
    await h.http.post(
        "/api/payments/click/card",
        json={"order_id": oid, "card_number": "8600123456789012", "expire_date": "12/30"},
        headers=headers,
    )
    click_api.answers["/card_token/verify"] = (200, {"error_code": -5, "error_note": "wrong sms code"})
    response = await h.http.post(
        "/api/payments/click/card/verify", json={"order_id": oid, "sms_code": "000000"}, headers=headers
    )
    assert response.status_code == 422 and response.json()["detail"]["code"] == "CLICK_DECLINED"
    assert (await order_row(h, oid))["click_card_token"] == "TOK-2", "a wrong code keeps the token"
    assert "/card_token/payment" not in click_api.paths()

    response = await h.http.post(
        "/api/payments/click/card",
        json={"order_id": oid, "card_number": "8600", "expire_date": "12/30"},
        headers=headers,
    )
    assert response.status_code == 400 and response.json()["detail"] == {"code": "VALIDATION_ERROR", "field": "card_number"}
    response = await h.http.post(
        "/api/payments/click/card",
        json={"order_id": oid, "card_number": "8600123456789012", "expire_date": "01/20"},
        headers=headers,
    )
    assert response.json()["detail"] == {"code": "VALIDATION_ERROR", "field": "expire_date", "reason": "expired"}


async def test_card_payment_outcome_unknown_is_pending_not_failed(harness, click_on, click_api):
    h = harness
    headers = await h.session(USER)
    oid = (await make_order(h, method="card"))["order"]["id"]
    await h.http.post(
        "/api/payments/click/card",
        json={"order_id": oid, "card_number": "8600123456789012", "expire_date": "12/30"},
        headers=headers,
    )
    click_api.answers["/card_token/payment"] = (502, "bad gateway")
    response = await h.http.post(
        "/api/payments/click/card/verify", json={"order_id": oid, "sms_code": "123456"}, headers=headers
    )
    assert response.status_code == 200 and response.json() == {"status": "pending"}


async def test_card_request_cap_3_per_order(harness, click_on, click_api):
    h = harness
    headers = await h.session(USER)
    oid = (await make_order(h, method="card"))["order"]["id"]
    body = {"order_id": oid, "card_number": "8600123456789012", "expire_date": "12/30"}
    for _ in range(3):
        assert (await h.http.post("/api/payments/click/card", json=body, headers=headers)).status_code == 200
    response = await h.http.post("/api/payments/click/card", json=body, headers=headers)
    assert response.status_code == 429 and response.json()["detail"]["code"] == "RATE_LIMITED"
    assert click_api.paths().count("/card_token/request") == 3


async def test_paid_order_refuses_direct_methods(harness, click_on, click_api):
    h = harness
    headers = await h.session(USER)
    oid = (await make_order(h))["order"]["id"]
    pid = await prepare(h, oid)
    await post_click(h, click_form(oid, action="1", prepare_id=pid))
    response = await h.http.post(
        "/api/payments/click/invoice", json={"order_id": oid, "phone": "901234567"}, headers=headers
    )
    assert response.status_code == 409 and response.json()["detail"] == {"code": "ORDER_ALREADY_PAID"}
    assert click_api.calls == []


async def test_invoice_flow_happy_and_failed(harness, click_on, click_api):
    h = harness
    headers = await h.session(USER)
    oid = (await make_order(h, method="phone", amount=25_000))["order"]["id"]
    response = await h.http.post(
        "/api/payments/click/invoice", json={"order_id": oid, "phone": "+998 90 123 45 67"}, headers=headers
    )
    assert response.status_code == 200 and response.json() == {"status": "sent"}
    assert click_api.calls[0]["body"] == {
        "service_id": int(SERVICE_ID), "amount": 25_000, "phone_number": "998901234567", "merchant_trans_id": f"vk-{oid}"
    }
    row = await order_row(h, oid)
    assert row["click_invoice_id"] == 7777 and row["click_method"] == "phone"
    assert await h.balance(USER) == 0

    click_api.answers["/invoice/create"] = (200, {"error_code": -5013, "error_note": "Subscriber not found"})
    response = await h.http.post(
        "/api/payments/click/invoice", json={"order_id": oid, "phone": "901234568"}, headers=headers
    )
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "CLICK_DECLINED", "stage": "invoice_create", "reason": "phone_not_registered"
    }
    click_api.answers["/invoice/create"] = (503, "down")
    response = await h.http.post(
        "/api/payments/click/invoice", json={"order_id": oid, "phone": "901234569"}, headers=headers
    )
    assert response.status_code == 503 and response.json()["detail"] == {"code": "CLICK_UNAVAILABLE", "stage": "invoice_create"}
    response = await h.http.post(
        "/api/payments/click/invoice", json={"order_id": oid, "phone": "12"}, headers=headers
    )
    assert response.status_code == 400 and response.json()["detail"] == {"code": "VALIDATION_ERROR", "field": "phone"}

    # The invoice is paid in the Click app -> Shop API -> credited once.
    pid = await prepare(h, oid, amount="25000")
    assert (await post_click(h, click_form(oid, action="1", prepare_id=pid, amount="25000")))["error"] == 0
    assert await h.balance(USER) == 25_000


async def test_merchant_network_failure_and_401(harness, click_on, click_api):
    h = harness
    headers = await h.session(USER)
    oid = (await make_order(h, method="phone"))["order"]["id"]
    click_api.answers["/invoice/create"] = RuntimeError("connection reset")
    response = await h.http.post(
        "/api/payments/click/invoice", json={"order_id": oid, "phone": "901234567"}, headers=headers
    )
    assert response.status_code == 503 and response.json()["detail"]["code"] == "CLICK_UNAVAILABLE"
    click_api.answers["/invoice/create"] = (401, {"error_code": -1})
    response = await h.http.post(
        "/api/payments/click/invoice", json={"order_id": oid, "phone": "901234560"}, headers=headers
    )
    assert response.status_code == 503 and response.json()["detail"]["code"] == "CLICK_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


async def test_admin_payments_list_filters_and_pagination(harness, click_on):
    h = harness
    paid = (await make_order(h))["order"]["id"]
    pid = await prepare(h, paid)
    await post_click(h, click_form(paid, action="1", prepare_id=pid))
    for _ in range(3):
        await make_order(h, user_id=USER2, method="card", amount=2_000)

    viewer = await h.session(VIEWER)
    response = await h.http.get("/api/admin/finance/payments", headers=viewer)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 4 and len(body["items"]) == 4

    only_paid = (await h.http.get("/api/admin/finance/payments?status=paid", headers=viewer)).json()
    assert [i["id"] for i in only_paid["items"]] == [paid]
    assert only_paid["items"][0]["paid_at"] is not None and only_paid["items"][0]["provider_txn"] == "910001"
    cards = (await h.http.get("/api/admin/finance/payments?method=card", headers=viewer)).json()
    assert cards["total"] == 3 and {i["user_id"] for i in cards["items"]} == {USER2}

    page1 = (await h.http.get("/api/admin/finance/payments?limit=2", headers=viewer)).json()
    page2 = (
        await h.http.get(f"/api/admin/finance/payments?limit=2&cursor={page1['next_cursor']}", headers=viewer)
    ).json()
    ids = [i["id"] for i in page1["items"] + page2["items"]]
    assert len(set(ids)) == 4

    future = int(time.time()) + 3600
    assert (await h.http.get(f"/api/admin/finance/payments?from={future}", headers=viewer)).json()["total"] == 0
    bad = await h.http.get("/api/admin/finance/payments?status=bogus", headers=viewer)
    assert bad.status_code == 400 and bad.json()["detail"] == {"code": "VALIDATION_ERROR", "field": "status"}
    denied = await h.http.get("/api/admin/finance/payments", headers=await h.session(USER))
    assert denied.status_code == 403 and denied.json()["detail"]["code"] == "ADMIN_REQUIRED"

    summary = (await h.http.get("/api/admin/finance/summary", headers=viewer)).json()
    assert summary["totals"]["topups"] == 10_000
    kinds = (await h.http.get("/api/admin/finance/transactions?kind=topup", headers=viewer)).json()
    assert [i["amount"] for i in kinds["items"]] == [10_000]


async def test_admin_bonus_setting_bounds_version_and_audit(harness):
    h = harness
    # init_db (not run by the harness) adds this column in production.
    await h.execute("ALTER TABLE webapp_admin_settings ADD COLUMN channel_lang TEXT NOT NULL DEFAULT 'uz'")
    headers = await h.session(ADMIN)
    state = (await h.http.get("/api/admin/state", headers=headers)).json()
    assert state["payment_bonus_percent"] == 0
    version = state["version"]
    response = await h.http.patch(
        "/api/admin/state", json={"payment_bonus_percent": 10, "expected_version": version}, headers=headers
    )
    assert response.status_code == 200 and response.json()["payment_bonus_percent"] == 10
    stale = await h.http.patch(
        "/api/admin/state", json={"payment_bonus_percent": 20, "expected_version": version}, headers=headers
    )
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "SETTINGS_CONFLICT"
    for bad in (51, -1):
        assert (await h.http.patch("/api/admin/state", json={"payment_bonus_percent": bad}, headers=headers)).status_code == 422
    viewer = await h.http.patch("/api/admin/state", json={"payment_bonus_percent": 5}, headers=await h.session(VIEWER))
    assert viewer.status_code == 403
    assert await h.scalar("SELECT payment_bonus_percent FROM webapp_admin_settings") == 10
    audit = await h.audit("settings.patch")
    assert json.loads(audit[-1]["payload_json"])["diff"] == {"payment_bonus_percent": [0, 10]}


# ---------------------------------------------------------------------------
# Migration m020
# ---------------------------------------------------------------------------


async def test_m020_rebuilds_ledger_keeping_rows_and_is_idempotent(tmp_path):
    import sqlite3

    import aiosqlite

    from src.db.migrations import m004_wallet_transactions, m020_click_payments

    path = tmp_path / "m020.sqlite3"
    insert = (
        "INSERT INTO wallet_transactions (user_id, kind, amount, balance_after, created_at) "
        "VALUES (?, ?, ?, ?, ?)"
    )
    async with aiosqlite.connect(path) as conn:
        await m004_wallet_transactions.apply(conn)
        for i, kind in enumerate(("admin_credit", "pro_activation", "referral_reward"), start=1):
            await conn.execute(insert, (900_000_000_100 + i, kind, 100 * i, 100 * i, 1_700_000_000 + i))
        await conn.execute("DELETE FROM wallet_transactions WHERE id = 3")  # high-water mark stays 3
        await conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            await conn.execute(insert, (1, "topup", 1, 1, 1))
        await conn.rollback()

        await m020_click_payments.apply(conn)
        await m020_click_payments.apply(conn)  # re-applied: no-op
        await conn.commit()

        rows = await (await conn.execute("SELECT id, kind, amount FROM wallet_transactions ORDER BY id")).fetchall()
        assert [tuple(r) for r in rows] == [(1, "admin_credit", 100), (2, "pro_activation", 200)]
        with_ref = (
            "INSERT INTO wallet_transactions (user_id, kind, amount, balance_after, created_at, reference) "
            "VALUES (1, 'topup', 5, 5, 1, 'click:1')"
        )
        await conn.execute(with_ref)
        new_id = (await (await conn.execute("SELECT MAX(id) FROM wallet_transactions")).fetchone())[0]
        assert new_id == 4, "a deleted id is never reused"
        with pytest.raises(sqlite3.IntegrityError):
            await conn.execute(with_ref)
        with pytest.raises(sqlite3.IntegrityError):
            await conn.execute(insert, (1, "bogus", 1, 1, 1))
        listed = await (await conn.execute("PRAGMA index_list(wallet_transactions)")).fetchall()
        names = {r[1] for r in listed}
        assert {"idx_wallet_tx_user_created", "idx_wallet_tx_kind_created", "idx_wallet_tx_kind_reference"} <= names
