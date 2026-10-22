"""Tests for ``webapp/routers/admin_finance.py`` (read-only finance reports).

Per CONTRACT_P12.md this module builds a MINIMAL app with only the finance
router mounted, independent of the other Phase 0/2 agents' files. ``get_db``
is overridden onto a temp SQLite file (a fresh connection per request, like
``tests/test_admin_auth.py`` does, so aiosqlite is never shared across event
loops). ``require_role`` is monkeypatched to a stub that returns a fixed
admin actor before the router is (re)imported, so no ``admins`` table is
needed.

``wallet_transactions`` is owned by the LEDGER agent's migration
(``m004_wallet_transactions``); per the coordinator's instructions this file
creates it itself from the CONTRACT_P0.md DDL rather than depending on that
migration file.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import time
from datetime import datetime, timedelta

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.core.timeutil import TZ, now_tz
from webapp.core import auth as auth_module
from webapp.core.database import get_db
from webapp.core.limiter import limiter

ACTOR_ID = 990001

# --------------------------------------------------------------------------
# Schema (CONTRACT_P0.md DDL for wallet_transactions; the bot-owned bits of
# users/referral_payouts trimmed to what the finance queries touch)
# --------------------------------------------------------------------------

SCHEMA_DDL = (
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        date INTEGER,
        lang TEXT,
        ref_by INTEGER,
        user_balance INTEGER DEFAULT 0,
        user_pro INTEGER DEFAULT 0,
        first_name TEXT,
        username TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS referral_payouts (
        user_id INTEGER PRIMARY KEY,
        inviter_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        ts INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS wallet_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN (
            'pro_activation', 'referral_reward', 'admin_credit', 'admin_reset', 'adjustment'
        )),
        amount INTEGER NOT NULL,
        balance_after INTEGER NOT NULL,
        price_snapshot INTEGER,
        actor_id INTEGER,
        note TEXT,
        created_at INTEGER NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_wallet_tx_user_created ON wallet_transactions (user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_wallet_tx_created ON wallet_transactions (created_at)",
    "CREATE INDEX IF NOT EXISTS idx_wallet_tx_kind_created ON wallet_transactions (kind, created_at)",
)


async def _build_schema(path: str) -> None:
    async with aiosqlite.connect(path) as conn:
        for ddl in SCHEMA_DDL:
            await conn.execute(ddl)
        await conn.commit()


@pytest.fixture
def db_path(tmp_path) -> str:
    path = str(tmp_path / "admin_finance.sqlite3")
    asyncio.run(_build_schema(path))
    return path


# --------------------------------------------------------------------------
# Minimal app: only the finance router, require_role stubbed before import
# --------------------------------------------------------------------------

@pytest.fixture
def client(db_path, monkeypatch):
    def _fake_require_role(min_role: str):
        async def _dep() -> dict:
            return {"user_id": ACTOR_ID, "role": "owner", "user": {}}

        return _dep

    monkeypatch.setattr(auth_module, "require_role", _fake_require_role)

    # Force a fresh import so the router's `Depends(require_role("viewer"))`
    # defaults are built against the stub above, not a previously-imported
    # (and by-then-reverted) real require_role.
    sys.modules.pop("webapp.routers.admin_finance", None)
    admin_finance = importlib.import_module("webapp.routers.admin_finance")

    app = FastAPI()
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    async def _rate_limited(request, exc):  # pragma: no cover - not expected to trigger
        raise exc

    app.add_exception_handler(RateLimitExceeded, _rate_limited)
    app.include_router(admin_finance.router, prefix="/api")

    async def _override_get_db():
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    app.dependency_overrides[get_db] = _override_get_db
    limiter.enabled = False
    try:
        yield TestClient(app)
    finally:
        limiter.enabled = True
        app.dependency_overrides.pop(get_db, None)
        sys.modules.pop("webapp.routers.admin_finance", None)


# --------------------------------------------------------------------------
# Seeding helpers
# --------------------------------------------------------------------------

def _exec(db_path: str, sql: str, params: tuple = ()) -> None:
    async def run():
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute(sql, params)
            await conn.commit()

    asyncio.run(run())


def _insert_user(db_path, user_id, *, balance=0, ref_by=None, first_name=None, username=None):
    _exec(
        db_path,
        "INSERT INTO users (user_id, date, lang, ref_by, user_balance, user_pro, first_name, username) "
        "VALUES (?, ?, 'uz', ?, ?, 0, ?, ?)",
        (user_id, int(time.time()), ref_by, balance, first_name, username),
    )


def _insert_tx(db_path, *, user_id, kind, amount, balance_after, created_at, price_snapshot=None, actor_id=None, note=None):
    _exec(
        db_path,
        "INSERT INTO wallet_transactions "
        "(user_id, kind, amount, balance_after, price_snapshot, actor_id, note, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, kind, amount, balance_after, price_snapshot, actor_id, note, int(created_at)),
    )


def _insert_payout(db_path, *, user_id, inviter_id, amount, ts):
    _exec(
        db_path,
        "INSERT INTO referral_payouts (user_id, inviter_id, amount, ts) VALUES (?, ?, ?, ?)",
        (user_id, inviter_id, amount, int(ts)),
    )


def _tashkent_ts(day, hour=12, minute=0) -> int:
    return int(datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ).timestamp())


# --------------------------------------------------------------------------
# Summary: totals + day-boundary series
# --------------------------------------------------------------------------

def test_summary_totals_and_day_boundary(client, db_path):
    today = now_tz().astimezone(TZ).date()
    day_a = today - timedelta(days=2)
    day_b = day_a + timedelta(days=1)  # the very next Tashkent calendar day

    _insert_user(db_path, 1, balance=7000)
    _insert_user(db_path, 2, balance=3000)

    # 23:30 Tashkent on day_a -> 18:30 UTC same day: unambiguous, sanity check.
    ts_a = _tashkent_ts(day_a, hour=23, minute=30)
    # 00:05 Tashkent on day_b -> 19:05 UTC on day_a: a naive UTC date() would
    # misfile this into day_a. The +5h shift in the router must put it in day_b.
    ts_b = _tashkent_ts(day_b, hour=0, minute=5)

    _insert_tx(db_path, user_id=1, kind="pro_activation", amount=-10000, balance_after=7000,
               price_snapshot=10000, created_at=ts_a)
    _insert_tx(db_path, user_id=1, kind="admin_credit", amount=5000, balance_after=7000,
               actor_id=ACTOR_ID, created_at=ts_a)
    _insert_tx(db_path, user_id=2, kind="referral_reward", amount=2000, balance_after=3000,
               created_at=ts_b)

    resp = client.get("/api/admin/finance/summary", params={"days": 5})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    totals = body["totals"]
    assert totals["revenue"] == 10000
    assert totals["activations"] == 1
    assert totals["admin_credits"] == 5000
    assert totals["referral_payouts"] == 2000
    assert totals["balance_outstanding"] == 10000  # 7000 + 3000

    series = {point["day"]: point for point in body["series"]}
    assert len(body["series"]) == 5
    assert series[day_a.isoformat()]["revenue"] == 10000
    assert series[day_a.isoformat()]["activations"] == 1
    assert series[day_a.isoformat()]["payouts"] == 0
    assert series[day_b.isoformat()]["revenue"] == 0
    assert series[day_b.isoformat()]["activations"] == 0
    assert series[day_b.isoformat()]["payouts"] == 2000
    # every other day in the window is zero-filled
    other_days = [d for d in series if d not in (day_a.isoformat(), day_b.isoformat())]
    for d in other_days:
        assert series[d] == {"day": d, "revenue": 0, "activations": 0, "payouts": 0}


def test_summary_days_bounds(client):
    assert client.get("/api/admin/finance/summary", params={"days": 0}).status_code == 422
    assert client.get("/api/admin/finance/summary", params={"days": 366}).status_code == 422
    assert client.get("/api/admin/finance/summary", params={"days": 365}).status_code == 200


# --------------------------------------------------------------------------
# Transactions: filters + cursor pagination
# --------------------------------------------------------------------------

def test_transactions_filters_and_cursor(client, db_path):
    _insert_user(db_path, 1, balance=0)
    _insert_user(db_path, 2, balance=0)
    base_ts = int(time.time()) - 1000

    # 7 rows: 4 admin_credit for user 1, 3 pro_activation for user 2.
    for i in range(4):
        _insert_tx(db_path, user_id=1, kind="admin_credit", amount=1000, balance_after=1000 * (i + 1),
                   actor_id=ACTOR_ID, created_at=base_ts + i)
    for i in range(3):
        _insert_tx(db_path, user_id=2, kind="pro_activation", amount=-5000, balance_after=0,
                   price_snapshot=5000, created_at=base_ts + 10 + i)

    # Filter by kind.
    resp = client.get("/api/admin/finance/transactions", params={"kind": "admin_credit", "limit": 100})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4
    assert all(item["kind"] == "admin_credit" for item in body["items"])

    # Filter by user_id.
    resp = client.get("/api/admin/finance/transactions", params={"user_id": 2, "limit": 100})
    body = resp.json()
    assert body["total"] == 3
    assert all(item["user_id"] == 2 for item in body["items"])

    # Filter by from/to.
    resp = client.get(
        "/api/admin/finance/transactions",
        params={"from": base_ts + 10, "to": base_ts + 11, "limit": 100},
    )
    body = resp.json()
    assert body["total"] == 2

    # Invalid kind -> validation error.
    resp = client.get("/api/admin/finance/transactions", params={"kind": "not_a_kind"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"

    # Invalid cursor -> validation error.
    resp = client.get("/api/admin/finance/transactions", params={"cursor": "!!!not-base64!!!"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"

    # Cursor pagination across all 7 rows, newest (highest id) first, no overlap.
    seen_ids: list[int] = []
    cursor = None
    for _ in range(10):
        params = {"limit": 3}
        if cursor:
            params["cursor"] = cursor
        resp = client.get("/api/admin/finance/transactions", params=params)
        body = resp.json()
        ids = [item["id"] for item in body["items"]]
        seen_ids.extend(ids)
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert len(seen_ids) == 7
    assert len(set(seen_ids)) == 7  # no duplicates across pages
    assert seen_ids == sorted(seen_ids, reverse=True)  # newest (id desc) first


# --------------------------------------------------------------------------
# Referrals: inviter aggregation + cursor
# --------------------------------------------------------------------------

def test_referrals_aggregation_and_cursor(client, db_path):
    _insert_user(db_path, 100, first_name="Ali", username=None)
    _insert_user(db_path, 200, first_name="Vali", username="bekjon")

    # Inviter 100 -> 3 invitees, 2 of them paid out.
    for i, uid in enumerate((101, 102, 103)):
        _insert_user(db_path, uid, ref_by=100)
    _insert_payout(db_path, user_id=101, inviter_id=100, amount=2000, ts=int(time.time()))
    _insert_payout(db_path, user_id=102, inviter_id=100, amount=2000, ts=int(time.time()))
    # 103 invited but not yet paid (payout may lag) -> LEFT JOIN must still count it.

    # Inviter 200 -> 1 invitee, paid.
    _insert_user(db_path, 201, ref_by=200)
    _insert_payout(db_path, user_id=201, inviter_id=200, amount=2000, ts=int(time.time()))

    resp = client.get("/api/admin/finance/referrals", params={"limit": 100})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    items = {item["inviter_id"]: item for item in body["items"]}

    assert items[100]["invited_count"] == 3
    assert items[100]["paid_sum"] == 4000
    assert items[100]["inviter_name"] == "Ali"  # no username -> falls back to first_name

    assert items[200]["invited_count"] == 1
    assert items[200]["paid_sum"] == 2000
    assert items[200]["inviter_name"] == "bekjon"  # username preferred

    # Ordering: invited_count desc -> inviter 100 (3) before inviter 200 (1).
    assert [item["inviter_id"] for item in body["items"]] == [100, 200]

    # Cursor pagination: limit=1 pages through both without duplicates/loss.
    seen = []
    cursor = None
    for _ in range(5):
        params = {"limit": 1}
        if cursor:
            params["cursor"] = cursor
        resp = client.get("/api/admin/finance/referrals", params=params)
        body = resp.json()
        seen.extend(item["inviter_id"] for item in body["items"])
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert seen == [100, 200]
