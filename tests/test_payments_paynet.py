"""Paynet provider endpoint (webapp/payments/paynet.py) against the REAL app.

The requests are built exactly as SlaydX relays them (raw JSON-RPC body, the
caller's own ``Authorization: Basic`` header). Credentials are fake values set
on ``get_settings()``; user ids are synthetic (tests/b3_support).
"""

from __future__ import annotations

import asyncio
import base64
import hmac
import json
import logging
import time
from datetime import datetime, timedelta, timezone

import pytest

from tests import b3_support
from tests.b3_support import USER, USER2, VIEWER
from webapp.core import ledger
from webapp.core.config import get_settings
from webapp.payments import paynet, service

harness = b3_support.harness

USERNAME = "pn-user-not-real"
PASSWORD = "pn:pass/with:colon-not-real"
SERVICE = 9001
OFFSET = 1_000_000_000
TASHKENT = timezone(timedelta(hours=5))


@pytest.fixture
def paynet_on(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "PAYNET_USERNAME", USERNAME, raising=False)
    monkeypatch.setattr(settings, "PAYNET_PASSWORD", PASSWORD, raising=False)
    monkeypatch.setattr(settings, "PAYNET_SERVICE_IDS", f"{SERVICE}, 9002", raising=False)
    monkeypatch.setattr(settings, "PAYNET_CLIENT_PARAM", "client_id", raising=False)
    monkeypatch.setattr(settings, "PAYNET_APP_URL", "", raising=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def basic(user: str = USERNAME, password: str = PASSWORD) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def payer(user_id: int = USER) -> dict:
    return {"client_id": f"vk-{user_id}"}


async def post_raw(h, content, headers: dict | None = None):
    return await h.http.post(
        "/api/payments/paynet",
        content=content,
        headers={"Content-Type": "application/json", **(basic() if headers is None else headers)},
    )


async def rpc(h, method: str, params: dict, *, rpc_id=1, headers: dict | None = None) -> dict:
    body = {"jsonrpc": "2.0", "method": method, "id": rpc_id, "params": params}
    response = await post_raw(h, json.dumps(body), headers)
    assert response.status_code == 200, response.text
    return response.json()


def err_code(out: dict) -> int:
    assert "result" not in out, out
    return out["error"]["code"]


async def perform(h, transaction_id=1001, user_id=USER, amount=100_000, **over):
    params = {
        "serviceId": SERVICE,
        "transactionId": transaction_id,
        "amount": amount,
        "fields": payer(user_id),
        **over,
    }
    return await rpc(h, "PerformTransaction", params)


async def check(h, transaction_id=1001, timestamp="2026-10-30 12:00:00", **over):
    params = {"serviceId": SERVICE, "transactionId": transaction_id, "timestamp": timestamp, **over}
    return await rpc(h, "CheckTransaction", params)


async def orders(h) -> list[dict]:
    return await h.query("SELECT * FROM payment_orders WHERE provider = 'paynet' ORDER BY seq")


async def ledger_of(h, user_id: int, kind: str) -> list[dict]:
    return await h.query(
        "SELECT amount, balance_after, reference, note FROM wallet_transactions "
        "WHERE user_id = ? AND kind = ? ORDER BY id",
        (user_id, kind),
    )


async def set_bonus(h, percent: int) -> None:
    await h.execute("UPDATE webapp_admin_settings SET payment_bonus_percent = ?", (percent,))


def ms(text: str, extra_ms: int = 0) -> int:
    dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TASHKENT)
    return int(dt.timestamp()) * 1000 + extra_ms


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "headers",
    [
        {},
        basic("wrong-user"),
        basic(USERNAME, "wrong-pass"),
        basic(USERNAME, ""),
        basic("", ""),
        {"Authorization": "Bearer abc"},
        {"Authorization": "Basic !!!not-base64!!!"},
        {"Authorization": "Basic " + base64.b64encode(b"no-colon").decode()},
        {"Authorization": "Basic"},
        {"Authorization": "Basic " + base64.b64encode(b"\xff\xfe:x").decode()},
    ],
)
async def test_bad_credentials_are_http_401_and_do_nothing(harness, paynet_on, headers):
    h = harness
    response = await post_raw(
        h,
        json.dumps({"jsonrpc": "2.0", "method": "GetInformation", "id": 7, "params": {}}),
        headers,
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="paynet"'
    assert response.json() == {
        "jsonrpc": "2.0",
        "id": None,
        "error": {"code": 412, "message": "Неверный логин или пароль"},
    }
    assert await h.query("SELECT 1 FROM payment_events WHERE provider = 'paynet'") == []


@pytest.mark.parametrize("missing", ["PAYNET_USERNAME", "PAYNET_PASSWORD", "PAYNET_SERVICE_IDS"])
async def test_unconfigured_means_every_call_is_401(harness, paynet_on, monkeypatch, missing):
    monkeypatch.setattr(get_settings(), missing, "", raising=False)
    response = await post_raw(harness, json.dumps({"jsonrpc": "2.0", "method": "X", "id": 1, "params": {}}))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == 412


async def test_password_with_colon_and_both_halves_compared_in_constant_time(harness, paynet_on, monkeypatch):
    calls: list[tuple[bytes, bytes]] = []
    real = hmac.compare_digest

    def spy(a, b):
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr(paynet.hmac, "compare_digest", spy)
    out = await rpc(harness, "GetInformation", {"serviceId": SERVICE, "fields": payer()})
    assert "result" in out  # PASSWORD contains ':' and still authenticates
    assert len(calls) == 2

    calls.clear()
    # A wrong username must not short-circuit the password comparison.
    response = await post_raw(harness, "{}", basic("nope", "nope"))
    assert response.status_code == 401
    assert len(calls) == 2
    assert all(len(a) == 32 and len(b) == 32 for a, b in calls), "digests, not the raw secrets"


async def test_non_post_is_minus_32300(harness, paynet_on):
    for verb in ("get", "put", "patch", "delete"):
        response = await getattr(harness.http, verb)("/api/payments/paynet", headers=basic())
        assert response.status_code == 200
        assert response.json()["error"]["code"] == -32300
        assert response.json()["id"] is None


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


async def test_parse_errors_and_invalid_requests(harness, paynet_on):
    h = harness
    for body in ("{not json", "", "NaN", '{"jsonrpc":"2.0","method":"GetInformation","id":NaN,"params":{}}'):
        out = (await post_raw(h, body)).json()
        assert out["error"]["code"] == -32700 and out["id"] is None, body

    good = {"jsonrpc": "2.0", "method": "GetInformation", "id": 5, "params": {}}
    bad_shapes = [
        [good],  # batch
        "text",
        None,
        {**good, "jsonrpc": "1.0"},
        {k: v for k, v in good.items() if k != "jsonrpc"},
        {**good, "method": 5},
        {k: v for k, v in good.items() if k != "method"},
        {k: v for k, v in good.items() if k != "id"},
        {**good, "id": None},
        {**good, "id": True},
        {**good, "id": {"a": 1}},
        {**good, "params": []},
        {**good, "params": "x"},
        {k: v for k, v in good.items() if k != "params"},
    ]
    for shape in bad_shapes:
        out = (await post_raw(h, json.dumps(shape))).json()
        assert out["error"]["code"] == -32600, shape

    # The id is echoed whenever it is itself valid.
    out = (await post_raw(h, json.dumps({**good, "params": []}))).json()
    assert out["id"] == 5
    out = (await post_raw(h, json.dumps({**good, "method": 5, "id": "abc"}))).json()
    assert out["id"] == "abc"


async def test_unknown_method_and_change_password(harness, paynet_on):
    for method in ("ChangePassword", "getinformation", "Nope", ""):
        out = await rpc(harness, method, {})
        assert err_code(out) == -32601, method


async def test_body_cap_64kb(harness, paynet_on):
    assert paynet.MAX_BODY_BYTES == 64 * 1024
    padding = "x" * (64 * 1024 + 10)  # literal: the cap itself must not be edited away unnoticed
    out = (await post_raw(harness, json.dumps({"jsonrpc": "2.0", "method": "GetInformation", "id": 1, "params": {"p": padding}}))).json()
    assert out["error"]["code"] == -32600
    # Just under the cap still parses.
    small = json.dumps({"jsonrpc": "2.0", "method": "GetInformation", "id": 1, "params": {"p": "x" * 60_000}})
    assert len(small) < 64 * 1024
    out = (await post_raw(harness, small)).json()
    assert out["error"]["code"] == -32602  # parsed; GetInformation lacks its params


async def test_id_echo_string_and_number(harness, paynet_on):
    for rpc_id in ("req-1", 42, 0, 1.5):
        out = await rpc(harness, "GetInformation", {"serviceId": SERVICE, "fields": payer()}, rpc_id=rpc_id)
        assert out["id"] == rpc_id and out["jsonrpc"] == "2.0"
    out = await rpc(harness, "GetInformation", {"serviceId": SERVICE, "fields": payer()}, rpc_id="")
    assert out["id"] == ""
    err = await rpc(harness, "GetInformation", {"serviceId": SERVICE, "fields": payer(999_999_999_999)}, rpc_id="e-9")
    assert err["id"] == "e-9"


# ---------------------------------------------------------------------------
# Payer id / service id / GetInformation
# ---------------------------------------------------------------------------


async def test_get_information_masks_name_and_reports_soum_balance(harness, paynet_on):
    h = harness
    await h.execute("UPDATE users SET first_name = 'Adham Bek', user_balance = 12345 WHERE user_id = ?", (USER,))
    out = await rpc(h, "GetInformation", {"serviceId": SERVICE, "fields": payer()})
    assert out["result"]["status"] == "0"
    assert out["result"]["fields"] == {"name": "Adham B.", "balance": 12345}
    assert isinstance(out["result"]["fields"]["balance"], int)
    assert datetime.strptime(out["result"]["timestamp"], "%Y-%m-%d %H:%M:%S")

    for stored, shown in (("Adham", "Adham"), ("  Adham   bek  Xon ", "Adham B."), ("", "Bandlik"), (None, "Bandlik")):
        await h.execute("UPDATE users SET first_name = ? WHERE user_id = ?", (stored, USER))
        out = await rpc(h, "GetInformation", {"serviceId": SERVICE, "fields": payer()})
        assert out["result"]["fields"]["name"] == shown


async def test_payer_rules_411_401_302_501(harness, paynet_on):
    h = harness
    await h.add_user(900_000_000_090, banned=1)

    def info(fields):
        return rpc(h, "GetInformation", {"serviceId": SERVICE, "fields": fields})

    assert err_code(await info({})) == 411
    assert err_code(await info({"client_id": ""})) == 411
    assert err_code(await info({"client_id": None})) == 411
    assert err_code(await info({"other": "vk-1"})) == 411
    for malformed in ("vk-", "vk_", "vk-12a", "VK-1", "Vk-1", "xx-1", "1", "vk--1", "vk- 1", "vk-1 ", "vk-1.0",
                      "vk-１２", "vk-²", "vk-" + "9" * 19, 12345, ["vk-1"], {"a": 1}, True):
        assert err_code(await info({"client_id": malformed})) == 401, malformed
    assert err_code(await info(payer(999_999_999_999))) == 302
    assert err_code(await info({"client_id": "vk-0"})) == 302
    assert err_code(await info(payer(900_000_000_090))) == 501
    # `vk_` is accepted as the same prefix; case of the digits is irrelevant, the prefix is case-sensitive.
    assert (await info({"client_id": f"vk_{USER}"}))["result"]["status"] == "0"
    assert (await info({"client_id": f"vk-{USER}"}))["result"]["status"] == "0"


async def test_client_param_name_is_configurable(harness, paynet_on, monkeypatch):
    h = harness
    monkeypatch.setattr(get_settings(), "PAYNET_CLIENT_PARAM", "account", raising=False)
    assert err_code(await rpc(h, "GetInformation", {"serviceId": SERVICE, "fields": payer()})) == 411
    out = await rpc(h, "GetInformation", {"serviceId": SERVICE, "fields": {"account": f"vk-{USER}"}})
    assert out["result"]["status"] == "0"
    done = await perform(h, 5, fields={"account": f"vk-{USER}"})
    assert done["result"]["fields"]["account"] == f"vk-{USER}"
    assert "client_id" not in done["result"]["fields"]


async def test_service_id_rules_305_and_params_32602(harness, paynet_on):
    h = harness
    fields = payer()
    for bad in (1, 0, -9001, "9003", "abc", "", " ", "9001x"):
        assert err_code(await rpc(h, "GetInformation", {"serviceId": bad, "fields": fields})) == 305, bad
    for wrong_type in (None, True, 9001.0, [9001], {"a": 1}):
        assert err_code(await rpc(h, "GetInformation", {"serviceId": wrong_type, "fields": fields})) == -32602, wrong_type
    assert (await rpc(h, "GetInformation", {"serviceId": "9001", "fields": fields}))["result"]["status"] == "0"
    assert (await rpc(h, "GetInformation", {"serviceId": 9002, "fields": fields}))["result"]["status"] == "0"
    assert err_code(await rpc(h, "GetInformation", {"fields": fields})) == -32602
    assert err_code(await rpc(h, "GetInformation", {"serviceId": SERVICE})) == -32602
    assert err_code(await rpc(h, "GetInformation", {"serviceId": SERVICE, "fields": "vk-1"})) == -32602
    # Every method checks the service id.
    assert err_code(await perform(h, serviceId=1)) == 305
    assert err_code(await check(h, serviceId=1)) == 305
    assert err_code(await rpc(h, "CancelTransaction", {"serviceId": 1, "transactionId": 1, "timestamp": "2026-10-30 12:00:00"})) == 305
    assert err_code(await rpc(h, "GetStatement", {"serviceId": 1, "dateFrom": "2026-10-30 00:00:00", "dateTo": "2026-10-30 23:59:59"})) == 305
    assert await orders(h) == []


# ---------------------------------------------------------------------------
# PerformTransaction
# ---------------------------------------------------------------------------


async def test_perform_credits_wallet_ledger_order_and_event(harness, paynet_on):
    h = harness
    await h.execute("UPDATE users SET user_balance = 500 WHERE user_id = ?", (USER,))
    before = int(time.time() * 1000)
    out = await perform(h, 1001, amount=25_000_000)  # 250 000 so'm
    after = int(time.time() * 1000)
    result = out["result"]
    assert result["fields"] == {"client_id": f"vk-{USER}", "balance": 250_500}
    assert datetime.strptime(result["timestamp"], "%Y-%m-%d %H:%M:%S")

    assert await h.balance(USER) == 250_500
    rows = await orders(h)
    assert len(rows) == 1
    row = rows[0]
    assert (row["user_id"], row["provider"], row["purpose"], row["amount_soum"], row["state"]) == (
        USER, "paynet", "topup", 250_000, "paid",
    )
    assert row["provider_txn"] == "1001" and row["click_method"] == "paynet"
    assert before <= row["perform_time"] <= after and row["create_time"] == row["perform_time"]
    assert row["prepare_id"] is None
    assert result["providerTrnId"] == OFFSET + row["seq"] > 0

    tx = await ledger_of(h, USER, "topup")
    assert tx == [{"amount": 250_000, "balance_after": 250_500, "reference": "paynet:1001", "note": "paynet"}]
    assert await ledger_of(h, USER, "topup_bonus") == []

    events = await h.query("SELECT * FROM payment_events WHERE provider = 'paynet'")
    assert len(events) == 1
    event = events[0]
    assert (event["method"], event["order_id"], event["provider_txn"], event["response_code"]) == (
        "PerformTransaction", row["id"], "1001", 0,
    )
    payload = json.loads(event["payload"])
    assert payload["amount"] == 25_000_000 and payload["fields"] == {"client_id": f"vk-{USER}"}


async def test_perform_pays_the_payment_bonus_like_click(harness, paynet_on):
    h = harness
    await set_bonus(h, 10)
    out = await perform(h, 2002, amount=10_000_000)  # 100 000 so'm -> +10 000 bonus
    assert out["result"]["fields"]["balance"] == 110_000
    assert await h.balance(USER) == 110_000
    assert [r["amount"] for r in await ledger_of(h, USER, "topup")] == [100_000]
    bonus = await ledger_of(h, USER, "topup_bonus")
    assert [(r["amount"], r["note"]) for r in bonus] == [(10_000, "10%")]
    row = (await orders(h))[0]
    assert bonus[0]["reference"] == f"payment-bonus:{row['id']}"
    assert (row["bonus_percent"], row["bonus_amount"]) == (10, 10_000)

    # A duplicate neither re-credits nor re-pays the bonus.
    assert err_code(await perform(h, 2002, amount=10_000_000)) == 201
    assert await h.balance(USER) == 110_000
    assert len(await ledger_of(h, USER, "topup_bonus")) == 1


async def test_bonus_zero_writes_no_bonus_row(harness, paynet_on):
    await perform(harness, 3003)
    assert await ledger_of(harness, USER, "topup_bonus") == []
    row = (await orders(harness))[0]
    assert (row["bonus_percent"], row["bonus_amount"]) == (0, 0)


@pytest.mark.parametrize(
    "amount,code",
    [
        (1, 413),  # the tester's "wrong amount"
        (0, 413),
        (-100_000, 413),
        (-1, 413),
        (100_050, 413),  # not a multiple of 100
        (100_001, 413),
        (99_900, 413),  # 999 so'm: under the minimum
        ("abc", 413),
        ("", 413),
        ("-100000", 413),
        ("100000.0", 413),
        (" 100000", 413),
        (None, 413),
        (True, 413),
        (False, 413),
        (100_000.5, 413),
        (1e400, 413),  # serialised as Infinity -> sent as 1e999 -> inf
        ([100_000], 413),
        ({"a": 1}, 413),
        (1_000_000_100, 415),  # 10 000 001 so'm: over the maximum
        (10**30, 415),
        (1e20, 415),
        (1e30, 413),  # a float this large is not an exact multiple of 100
        ("1" + "0" * 15, 415),
        (10**45, 415),
    ],
)
async def test_amount_rules(harness, paynet_on, amount, code):
    h = harness
    body = json.dumps(
        {"jsonrpc": "2.0", "method": "PerformTransaction", "id": 1,
         "params": {"serviceId": SERVICE, "transactionId": 77, "amount": amount, "fields": payer()}}
    ).replace("Infinity", "1e999")
    out = (await post_raw(h, body)).json()
    assert err_code(out) == code, out
    assert await orders(h) == [] and await h.balance(USER) == 0


async def test_amount_accepted_forms_and_limits(harness, paynet_on):
    h = harness
    assert (await perform(h, 1, amount=100_000))["result"]["fields"]["balance"] == 1_000  # exactly the minimum
    assert (await perform(h, 2, amount="200000"))["result"]["fields"]["balance"] == 3_000  # digit string
    assert (await perform(h, 3, amount=100_000.0))["result"]["fields"]["balance"] == 4_000  # integral float
    top = await perform(h, 4, user_id=USER2, amount=1_000_000_000)  # exactly 10 000 000 so'm
    assert top["result"]["fields"]["balance"] == 10_000_000


async def test_missing_params_are_32602_and_change_nothing(harness, paynet_on):
    h = harness
    full = {"serviceId": SERVICE, "transactionId": 5, "amount": 100_000, "fields": payer()}
    for drop in full:
        params = {k: v for k, v in full.items() if k != drop}
        assert err_code(await rpc(h, "PerformTransaction", params)) == -32602, drop
    assert err_code(await rpc(h, "PerformTransaction", {**full, "fields": "x"})) == -32602
    assert await orders(h) == []


@pytest.mark.parametrize("bad", [0, -1, "abc", "", "-5", "1.5", 1.5, 123.0, True, None, [1], {"a": 1}, 2**53, "9" * 41, "１"])
async def test_transaction_id_must_be_a_positive_safe_integer(harness, paynet_on, bad):
    assert err_code(await perform(harness, bad)) == -32602
    assert await orders(harness) == []


async def test_transaction_id_is_canonicalised(harness, paynet_on):
    h = harness
    assert "result" in await perform(h, "000123")
    assert err_code(await perform(h, 123)) == 201
    assert err_code(await perform(h, "123")) == 201
    assert err_code(await perform(h, "0123")) == 201
    row = (await orders(h))[0]
    assert row["provider_txn"] == "123"
    assert await h.balance(USER) == 1_000
    assert "result" in await perform(h, 2**53 - 1)  # largest safe integer
    assert (await check(h, "123"))["result"]["transactionState"] == 1
    assert (await check(h, 123))["result"]["transactionState"] == 1


async def test_duplicate_transaction_is_201_with_exactly_one_credit(harness, paynet_on):
    h = harness
    first = await perform(h, 4004)
    assert "result" in first
    for _ in range(3):
        assert err_code(await perform(h, 4004)) == 201
    # A different amount or another user under the same transactionId is still the same transaction.
    assert err_code(await perform(h, 4004, amount=900_000)) == 201
    assert err_code(await perform(h, 4004, user_id=USER2)) == 201
    assert await h.balance(USER) == 1_000 and await h.balance(USER2) == 0
    assert len(await orders(h)) == 1 and len(await ledger_of(h, USER, "topup")) == 1
    # A retry after the payer got banned is still "already exists", never "blocked".
    await h.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (USER,))
    assert err_code(await perform(h, 4004)) == 201


async def test_concurrent_burst_of_the_same_transaction_credits_once(harness, paynet_on):
    h = harness
    outs = await asyncio.gather(*(perform(h, 5005, amount=300_000) for _ in range(12)))
    wins = [o for o in outs if "result" in o]
    dupes = [o for o in outs if "error" in o]
    assert len(wins) == 1 and len(dupes) == 11
    assert {o["error"]["code"] for o in dupes} == {201}
    assert await h.balance(USER) == 3_000
    assert len(await orders(h)) == 1
    assert len(await ledger_of(h, USER, "topup")) == 1
    # Distinct ids in a burst all land, each exactly once.
    outs = await asyncio.gather(*(perform(h, 6000 + i) for i in range(10)))
    assert all("result" in o for o in outs)
    assert await h.balance(USER) == 3_000 + 10_000
    ids = [o["result"]["providerTrnId"] for o in outs]
    assert len(set(ids)) == 10 and all(i > OFFSET for i in ids)


async def test_perform_failures_leave_no_order_and_no_credit(harness, paynet_on, monkeypatch):
    h = harness
    await set_bonus(h, 10)
    real = ledger.apply_balance_change

    # 1) fails right after the order insert + wallet credit
    async def fail_after_credit(db, **kw):
        out = await real(db, **kw)
        if kw["kind"] == "topup":
            raise RuntimeError("boom after credit")
        return out

    monkeypatch.setattr(ledger, "apply_balance_change", fail_after_credit)
    assert err_code(await perform(h, 7007)) == -32603
    # 2) fails while paying the bonus
    async def fail_on_bonus(db, **kw):
        if kw["kind"] == "topup_bonus":
            raise RuntimeError("boom on bonus")
        return await real(db, **kw)

    monkeypatch.setattr(ledger, "apply_balance_change", fail_on_bonus)
    assert err_code(await perform(h, 7007)) == -32603
    assert await orders(h) == []
    assert await h.balance(USER) == 0
    assert await h.ledger_rows(USER) == []

    monkeypatch.setattr(ledger, "apply_balance_change", real)
    out = await perform(h, 7007)  # the retry succeeds: nothing was left half-done
    assert out["result"]["fields"]["balance"] == 1_100
    assert len(await orders(h)) == 1


async def test_internal_errors_never_leak_details(harness, paynet_on, monkeypatch, caplog):
    async def boom(*a, **kw):
        raise RuntimeError("secret-internal-detail /home/x")

    monkeypatch.setattr(service, "credit_topup", boom)
    with caplog.at_level(logging.ERROR):
        response = await post_raw(
            harness,
            json.dumps({"jsonrpc": "2.0", "method": "PerformTransaction", "id": 3, "params": {
                "serviceId": SERVICE, "transactionId": 8, "amount": 100_000, "fields": payer()}}),
        )
    assert response.status_code == 200
    assert response.json() == {"jsonrpc": "2.0", "id": 3, "error": {"code": -32603, "message": "Internal error"}}
    assert "secret-internal-detail" not in response.text
    assert await orders(harness) == []


async def test_perform_payer_errors_create_nothing(harness, paynet_on):
    h = harness
    await h.add_user(900_000_000_091, banned=1)
    assert err_code(await perform(h, 11, fields={})) == 411
    assert err_code(await perform(h, 12, fields={"client_id": "vk-x"})) == 401
    assert err_code(await perform(h, 13, user_id=999_999_999_999)) == 302
    assert err_code(await perform(h, 14, user_id=900_000_000_091)) == 501
    assert await orders(h) == []
    assert await h.query("SELECT 1 FROM wallet_transactions WHERE kind = 'topup'") == []
    # The failed ids are not burned: they can still be paid later.
    assert "result" in await perform(h, 13, user_id=USER)


# ---------------------------------------------------------------------------
# CheckTransaction / CancelTransaction
# ---------------------------------------------------------------------------


async def test_check_found_and_unknown(harness, paynet_on):
    h = harness
    done = await perform(h, 9009)
    out = await check(h, 9009)
    row = (await orders(h))[0]
    assert done["result"]["providerTrnId"] == OFFSET + row["seq"]
    assert out["result"] == {
        "transactionState": 1,
        "providerTrnId": done["result"]["providerTrnId"],
        "timestamp": paynet.format_time(row["perform_time"]),
    }
    assert out["result"]["timestamp"] == done["result"]["timestamp"]

    unknown = await check(h, 424242)
    assert unknown["result"]["transactionState"] == 3
    assert unknown["result"]["providerTrnId"] == 0
    assert datetime.strptime(unknown["result"]["timestamp"], "%Y-%m-%d %H:%M:%S")


@pytest.mark.parametrize(
    "stamp",
    ["", "2026-10-30", "2026-10-30T12:00:00", "2026-10-30 12:00", "2026-13-01 00:00:00", "2026-02-30 10:00:00",
     "2026-10-30 25:00:00", "2026-10-30 12:00:60", "yesterday", 1761800000, None, True, "2026-10-30 12:00:00 "],
)
async def test_check_validates_timestamp_414(harness, paynet_on, stamp):
    await perform(harness, 9010)
    assert err_code(await check(harness, 9010, timestamp=stamp)) == 414


@pytest.mark.parametrize("stamp", ["16.06.2021 12:44:57", "2026-10-30 12:00:00", "garbage", 1761800000, None])
async def test_cancel_accepts_any_timestamp_format(harness, paynet_on, stamp):
    """Paynet's spec sends Cancel's timestamp as DD.MM.YYYY: it must not turn 77/203 into 414."""
    h = harness
    await perform(h, 9011)
    base = {"serviceId": SERVICE, "timestamp": stamp}
    assert err_code(await rpc(h, "CancelTransaction", {**base, "transactionId": 9011})) == 77
    assert err_code(await rpc(h, "CancelTransaction", {**base, "transactionId": 9012})) == 203


async def test_check_and_cancel_param_rules(harness, paynet_on):
    h = harness
    for method in ("CheckTransaction", "CancelTransaction"):
        full = {"serviceId": SERVICE, "transactionId": 1, "timestamp": "2026-10-30 12:00:00"}
        for drop in full:
            assert err_code(await rpc(h, method, {k: v for k, v in full.items() if k != drop})) == -32602
        for bad in (0, "x", None, 1.5):
            assert err_code(await rpc(h, method, {**full, "transactionId": bad})) == -32602


async def test_cancel_never_cancels_anything(harness, paynet_on):
    h = harness
    await set_bonus(h, 5)
    await perform(h, 9020, amount=1_000_000)
    balance = await h.balance(USER)
    snapshot_orders = await h.query("SELECT * FROM payment_orders")
    snapshot_ledger = await h.query("SELECT * FROM wallet_transactions ORDER BY id")

    cancel = {"serviceId": SERVICE, "transactionId": 9020, "timestamp": "2026-10-30 12:00:00"}
    for _ in range(2):
        assert err_code(await rpc(h, "CancelTransaction", cancel)) == 77
    assert err_code(await rpc(h, "CancelTransaction", {**cancel, "transactionId": 777})) == 203

    assert await h.balance(USER) == balance
    assert await h.query("SELECT * FROM payment_orders") == snapshot_orders
    assert await h.query("SELECT * FROM wallet_transactions ORDER BY id") == snapshot_ledger
    assert (await check(h, 9020))["result"]["transactionState"] == 1


# ---------------------------------------------------------------------------
# GetStatement
# ---------------------------------------------------------------------------


async def seed_paid(h, txn: int, perform_ms: int, soum: int = 1_000, user_id: int = USER, state: str = "paid", provider="paynet"):
    await h.execute(
        "INSERT INTO payment_orders (id, user_id, provider, purpose, amount_soum, state, provider_txn, "
        "create_time, perform_time, click_method, created_at, updated_at) "
        "VALUES (?, ?, ?, 'topup', ?, ?, ?, ?, ?, ?, 1, 1)",
        (f"00000000-0000-4000-8000-{txn:012d}", user_id, provider, soum, state, str(txn), perform_ms, perform_ms,
         "paynet" if provider == "paynet" else "app"),
    )


async def statement(h, date_from: str, date_to: str) -> dict:
    return await rpc(h, "GetStatement", {"serviceId": SERVICE, "dateFrom": date_from, "dateTo": date_to})


async def test_statement_range_is_inclusive_ordered_and_gmt_plus_5(harness, paynet_on):
    h = harness
    t = "2026-10-30 12:00:00"
    # 12:00:00 Tashkent is 07:00:00 UTC.
    assert ms(t) == int(datetime(2026, 10, 30, 7, 0, 0, tzinfo=timezone.utc).timestamp()) * 1000
    await seed_paid(h, 10, ms(t, -1))       # 11:59:59.999: before the range
    await seed_paid(h, 12, ms(t, 500), 2_000)   # inside, same second as the start
    await seed_paid(h, 11, ms(t, 0), 3_000)     # exactly dateFrom
    await seed_paid(h, 13, ms("2026-10-30 12:00:05"), 4_000)
    await seed_paid(h, 14, ms("2026-10-30 12:00:10", 999), 5_000)  # last ms of dateTo
    await seed_paid(h, 15, ms("2026-10-30 12:00:11"), 6_000)        # after the range
    await seed_paid(h, 16, ms("2026-10-30 12:00:05"), 7_000)        # same time as 13: ordered by transactionId

    out = await statement(h, t, "2026-10-30 12:00:10")
    rows = out["result"]["statements"]
    assert [r["transactionId"] for r in rows] == [11, 12, 13, 16, 14]
    assert [r["timestamp"] for r in rows] == [
        "2026-10-30 12:00:00", "2026-10-30 12:00:00", "2026-10-30 12:00:05", "2026-10-30 12:00:05", "2026-10-30 12:00:10",
    ]
    assert [r["amount"] for r in rows] == [300_000, 200_000, 400_000, 700_000, 500_000]
    assert all(isinstance(r["amount"], int) and r["amount"] > 0 for r in rows)
    assert all(r["providerTrnId"] > OFFSET for r in rows)
    assert len({r["providerTrnId"] for r in rows}) == len(rows)
    assert set(rows[0]) == {"amount", "transactionId", "providerTrnId", "timestamp"}

    # A one-second range returns the rows of that second only.
    single = (await statement(h, t, t))["result"]["statements"]
    assert [r["transactionId"] for r in single] == [11, 12]
    # An empty range is an empty list, not an error.
    assert (await statement(h, "2030-01-01 00:00:00", "2030-01-02 00:00:00"))["result"] == {"statements": []}


async def test_statement_lists_only_paid_paynet_orders(harness, paynet_on):
    h = harness
    stamp = ms("2026-10-30 12:00:00")
    await seed_paid(h, 21, stamp)
    await seed_paid(h, 22, stamp, state="cancelled")
    await seed_paid(h, 23, stamp, state="pending")
    await seed_paid(h, 24, stamp, provider="click")
    rows = (await statement(h, "2026-10-30 00:00:00", "2026-10-30 23:59:59"))["result"]["statements"]
    assert [r["transactionId"] for r in rows] == [21]


async def test_statement_matches_what_perform_returned(harness, paynet_on):
    h = harness
    done = await perform(h, 31, amount=12_300_000)
    stamp = done["result"]["timestamp"]
    rows = (await statement(h, stamp, stamp))["result"]["statements"]
    assert rows == [{
        "amount": 12_300_000,
        "transactionId": 31,
        "providerTrnId": done["result"]["providerTrnId"],
        "timestamp": stamp,
    }]


@pytest.mark.parametrize(
    "date_from,date_to",
    [
        ("2026-10-30 12:00:01", "2026-10-30 12:00:00"),  # reversed
        ("", "2026-10-30 12:00:00"),
        ("2026-10-30 12:00:00", ""),
        ("2026-10-30", "2026-10-31"),
        ("bad", "bad"),
        ("2026-13-45 00:00:00", "2026-13-46 00:00:00"),
        (20261030, 20261031),
        (None, None),
    ],
)
async def test_statement_invalid_dates_414(harness, paynet_on, date_from, date_to):
    out = await rpc(harness, "GetStatement", {"serviceId": SERVICE, "dateFrom": date_from, "dateTo": date_to})
    assert err_code(out) == 414


async def test_statement_requires_params(harness, paynet_on):
    for drop in ("serviceId", "dateFrom", "dateTo"):
        params = {"serviceId": SERVICE, "dateFrom": "2026-10-30 00:00:00", "dateTo": "2026-10-30 23:59:59"}
        del params[drop]
        assert err_code(await rpc(harness, "GetStatement", params)) == -32602


async def test_statement_big_range_is_fast_and_unique(harness, paynet_on):
    h = harness
    base = ms("2026-10-30 00:00:00")
    async with h.conn() as conn:
        await conn.executemany(
            "INSERT INTO payment_orders (id, user_id, provider, purpose, amount_soum, state, provider_txn, "
            "create_time, perform_time, click_method, created_at, updated_at) "
            "VALUES (?, ?, 'paynet', 'topup', 1000, 'paid', ?, ?, ?, 'paynet', 1, 1)",
            [(f"id-{i:08d}", USER, str(100_000 + i), base + i * 1000, base + i * 1000) for i in range(5_000)],
        )
        await conn.commit()
    started = time.monotonic()
    out = await statement(h, "2026-10-30 00:00:00", "2026-10-30 23:59:59")
    elapsed = time.monotonic() - started
    rows = out["result"]["statements"]
    assert len(rows) == 5_000
    assert len({r["transactionId"] for r in rows}) == 5_000 == len({r["providerTrnId"] for r in rows})
    assert elapsed < 2.0, elapsed


# ---------------------------------------------------------------------------
# Trail, logs, secrets
# ---------------------------------------------------------------------------


async def test_every_authenticated_call_leaves_one_event_and_no_secret(harness, paynet_on, caplog):
    h = harness
    with caplog.at_level(logging.DEBUG):
        await perform(h, 41)
        await check(h, 41)
        await rpc(h, "CancelTransaction", {"serviceId": SERVICE, "transactionId": 41, "timestamp": "2026-10-30 12:00:00"})
        await rpc(h, "GetInformation", {"serviceId": SERVICE, "fields": payer(999_999_999_999)})
        await rpc(h, "Nope", {})
        await post_raw(h, "{broken")
    events = await h.query("SELECT method, response_code, provider_txn FROM payment_events WHERE provider = 'paynet' ORDER BY id")
    assert [(e["method"], e["response_code"]) for e in events] == [
        ("PerformTransaction", 0),
        ("CheckTransaction", 0),
        ("CancelTransaction", 77),
        ("GetInformation", 302),
        ("invalid", -32601),
        ("invalid", -32700),
    ]
    blob = json.dumps(await h.query("SELECT * FROM payment_events"))
    base64_cred = basic()["Authorization"].split()[1]
    for secret in (PASSWORD, USERNAME, base64_cred):
        assert secret not in blob
        assert secret not in caplog.text
    assert "Authorization" not in blob and "authorization" not in caplog.text.lower()
    assert "paynet" in caplog.text and "method=PerformTransaction" in caplog.text
    # One log line per call from OUR logger: method, service, code, ms - never the body.
    ours = [r.getMessage() for r in caplog.records if r.name == "webapp.payments.paynet"]
    assert len([m for m in ours if m.startswith("[paynet] method=")]) == 6
    assert not any("client_id" in m or "vk-" in m for m in ours)


async def test_failed_auth_is_not_logged_with_credentials(harness, paynet_on, caplog):
    with caplog.at_level(logging.DEBUG):
        await post_raw(harness, "{}", basic(USERNAME, "guess-123456"))
    assert "guess-123456" not in caplog.text


async def test_handler_is_fast(harness, paynet_on):
    h = harness
    await perform(h, 51)
    timings = []
    for i in range(5):
        started = time.monotonic()
        await perform(h, 600 + i)
        await check(h, 51)
        timings.append(time.monotonic() - started)
    assert min(timings) < 0.5, timings


# ---------------------------------------------------------------------------
# Wallet card, Click isolation, admin lists
# ---------------------------------------------------------------------------


async def test_wallet_info_endpoint(harness, paynet_on, monkeypatch):
    h = harness
    headers = await h.session(USER)
    out = await h.http.get("/api/payments/paynet/info", headers=headers)
    assert out.status_code == 200
    assert out.json() == {"enabled": True, "payer_id": f"vk-{USER}", "app_url": None}

    for url, expected in (
        ("https://paynet.uz/app", "https://paynet.uz/app"),
        ("http://paynet.uz/app", None),
        ("javascript:alert(1)", None),
        ("https://", None),
        ("https://pay net.uz", None),
        ("  ", None),
    ):
        monkeypatch.setattr(get_settings(), "PAYNET_APP_URL", url, raising=False)
        got = (await h.http.get("/api/payments/paynet/info", headers=headers)).json()["app_url"]
        assert got == expected, url

    monkeypatch.setattr(get_settings(), "PAYNET_PASSWORD", "", raising=False)
    off = await h.http.get("/api/payments/paynet/info", headers=headers)
    assert off.json() == {"enabled": False, "payer_id": None, "app_url": None}

    assert (await h.http.get("/api/payments/paynet/info")).status_code == 401  # needs a signed-in user


async def test_paynet_orders_are_invisible_to_click_and_user_polling(harness, paynet_on):
    from tests.test_payments_click import SECRET, SERVICE_ID, click_form

    h = harness
    await perform(h, 61)
    row = (await orders(h))[0]
    # Click's Shop API must treat a paynet order as "not found" (-5): never settle, never cancel it.
    settings = get_settings()
    settings.CLICK_SERVICE_ID, settings.CLICK_SECRET_KEY = SERVICE_ID, SECRET
    try:
        for action in ("0", "1"):
            form = click_form(row["id"], action=action, amount="1000", prepare_id=row["seq"])
            out = (await h.http.post("/api/payments/click", data=form)).json()
            assert out["error"] == -5, out
    finally:
        settings.CLICK_SERVICE_ID = settings.CLICK_SECRET_KEY = ""
    assert (await orders(h))[0]["state"] == "paid"
    # The wallet still lists it for its owner and not for anybody else.
    mine = await h.http.get(f"/api/payments/orders/{row['id']}", headers=await h.session(USER))
    assert mine.status_code == 200 and mine.json()["order"]["method"] == "paynet"
    other = await h.http.get(f"/api/payments/orders/{row['id']}", headers=await h.session(USER2))
    assert other.status_code == 404


async def test_admin_finance_lists_paynet_payments(harness, paynet_on):
    h = harness
    await perform(h, 71)
    headers = await h.session(VIEWER)
    out = await h.http.get("/api/admin/finance/payments?method=paynet", headers=headers)
    assert out.status_code == 200, out.text
    items = out.json()["items"]
    assert [(i["method"], i["state"], i["amount"], i["provider_txn"]) for i in items] == [("paynet", "paid", 1_000, "71")]
    assert (await h.http.get("/api/admin/finance/payments?method=nope", headers=headers)).status_code == 400


# ---------------------------------------------------------------------------
# Migration m027
# ---------------------------------------------------------------------------


async def test_m027_rebuilds_orders_and_events_keeping_rows_and_is_idempotent(tmp_path):
    import sqlite3

    import aiosqlite

    from src.db.migrations import m004_wallet_transactions, m020_click_payments, m027_paynet

    path = tmp_path / "m027.sqlite3"
    async with aiosqlite.connect(path) as conn:
        await m004_wallet_transactions.apply(conn)
        await m020_click_payments.apply(conn)
        for i in range(1, 4):
            await conn.execute(
                "INSERT INTO payment_orders (id, user_id, amount_soum, state, provider_txn, prepare_id, "
                "click_method, created_at, updated_at) VALUES (?, 1, ?, 'paid', ?, ?, 'app', 5, 5)",
                (f"11111111-1111-4111-8111-{i:012d}", 1000 * i, f"txn{i}", i),
            )
            await conn.execute(
                "INSERT INTO payment_events (provider, method, payload, received_at) VALUES ('click', 'complete', '{}', ?)", (i,)
            )
        await conn.execute("DELETE FROM payment_orders WHERE seq = 3")  # the high-water mark stays 3
        await conn.execute("DELETE FROM payment_events WHERE id = 3")
        await conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            await conn.execute(
                "INSERT INTO payment_orders (id, user_id, provider, amount_soum, created_at, updated_at) "
                "VALUES ('x', 1, 'paynet', 1, 1, 1)"
            )
        await conn.rollback()

        await m027_paynet.apply(conn)
        await m027_paynet.apply(conn)  # re-applied: a no-op
        await conn.commit()

        rows = await (await conn.execute("SELECT seq, id, amount_soum, provider_txn, prepare_id, click_method FROM payment_orders ORDER BY seq")).fetchall()
        assert [tuple(r)[0] for r in rows] == [1, 2]
        assert tuple(rows[1]) == (2, "11111111-1111-4111-8111-000000000002", 2000, "txn2", 2, "app")
        events = await (await conn.execute("SELECT id FROM payment_events ORDER BY id")).fetchall()
        assert [r[0] for r in events] == [1, 2]

        await conn.execute(
            "INSERT INTO payment_orders (id, user_id, provider, amount_soum, state, provider_txn, click_method, created_at, updated_at) "
            "VALUES ('y', 1, 'paynet', 5, 'paid', '9', 'paynet', 1, 1)"
        )
        assert (await (await conn.execute("SELECT seq FROM payment_orders WHERE id = 'y'")).fetchone())[0] == 4, "ids are never reused"
        await conn.execute("INSERT INTO payment_events (provider, method, payload, received_at) VALUES ('paynet', 'x', '{}', 1)")
        assert (await (await conn.execute("SELECT MAX(id) FROM payment_events")).fetchone())[0] == 4

        with pytest.raises(sqlite3.IntegrityError):  # the unique (provider, provider_txn) guard survived
            await conn.execute(
                "INSERT INTO payment_orders (id, user_id, provider, amount_soum, state, provider_txn, created_at, updated_at) "
                "VALUES ('z', 1, 'paynet', 5, 'paid', '9', 1, 1)"
            )
        await conn.rollback()
        for bad in (
            "INSERT INTO payment_orders (id, user_id, provider, amount_soum, created_at, updated_at) VALUES ('b1', 1, 'payme', 1, 1, 1)",
            "INSERT INTO payment_events (provider, method, payload, received_at) VALUES ('payme', 'x', '{}', 1)",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                await conn.execute(bad)
        names = {r[1] for r in await (await conn.execute("PRAGMA index_list(payment_orders)")).fetchall()}
        assert {"idx_payment_orders_txn", "idx_payment_orders_user_created", "idx_payment_orders_paynet_perform"} <= names
        names = {r[1] for r in await (await conn.execute("PRAGMA index_list(payment_events)")).fetchall()}
        assert {"idx_payment_events_order", "idx_payment_events_txn", "idx_payment_events_received"} <= names
