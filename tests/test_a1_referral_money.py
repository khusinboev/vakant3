"""Referral reward and money settings: an admin-set 0 means 0.

* ``pay_referral_reward`` falls back to the default only when the stored
  reward is NULL; a reward <= 0 pays nothing and writes no payout/ledger row.
* ``StatsMiddleware.resolve_user`` pays only when its own INSERT created the
  user (a concurrent creator already owns the referral).
* ``/api/admin/state`` shows the stored price/reward and bounds them by
  ``ledger.MAX_AMOUNT``; ``pro_price`` must be >= 1 (0 would be free Pro).
"""

import asyncio
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import test_admin_auth as admin_fx
from src.db.migrate import run_migrations
from src.middleware.middlewares import StatsMiddleware, pay_referral_reward
from webapp.core import ledger
from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.main import app

MW_MODULE = "src.middleware.middlewares"
INVITER = 900000000101
INVITEE = 900000000102


async def _bot_db(path: str, reward) -> None:
    """Bot-owned schema + migrations + a settings row with ``reward``."""
    middleware = StatsMiddleware(path)
    with patch(f"{MW_MODULE}._seed_from_osonish_api", new_callable=AsyncMock):
        await middleware.init_db()
    async with aiosqlite.connect(path) as conn:
        await run_migrations(conn)
        await conn.execute(
            "INSERT OR REPLACE INTO webapp_admin_settings (singleton, referral_reward) VALUES (1, ?)",
            (reward,),
        )
        await conn.execute(
            "INSERT INTO users (user_id, date, lang, user_balance) VALUES (?, 0, 'uz', 0)", (INVITER,)
        )
        await conn.commit()


async def _scalar(path: str, sql: str, params: tuple = ()):
    async with aiosqlite.connect(path) as conn:
        cursor = await conn.execute(sql, params)
        row = await cursor.fetchone()
        return row[0] if row else None


async def _money_state(path: str) -> tuple[int, int, int]:
    balance = await _scalar(path, "SELECT user_balance FROM users WHERE user_id = ?", (INVITER,))
    payouts = await _scalar(path, "SELECT COUNT(*) FROM referral_payouts")
    ledger_rows = await _scalar(
        path, "SELECT COUNT(*) FROM wallet_transactions WHERE kind = 'referral_reward'"
    )
    return int(balance or 0), int(payouts), int(ledger_rows)


# --------------------------------------------------------------------------
# Bot: reward resolution
# --------------------------------------------------------------------------


@pytest.mark.parametrize("reward", [0, -500])
async def test_reward_zero_or_negative_pays_nothing(tmp_path, reward):
    path = str(tmp_path / "bot.sqlite3")
    await _bot_db(path, reward)
    middleware = StatsMiddleware(path)

    with patch(f"{MW_MODULE}._notify_inviter", new_callable=AsyncMock) as notify:
        assert await middleware.resolve_user(INVITEE, "uz", INVITER) == ("uz", True)
        notify.assert_not_awaited()

    assert await _money_state(path) == (0, 0, 0)
    # The referral itself is still recorded (it counts toward the referral gate).
    assert await _scalar(path, "SELECT ref_by FROM users WHERE user_id = ?", (INVITEE,)) == INVITER


async def test_positive_reward_is_paid_once_with_one_ledger_row(tmp_path):
    path = str(tmp_path / "bot.sqlite3")
    await _bot_db(path, 1500)
    middleware = StatsMiddleware(path)

    with patch(f"{MW_MODULE}._notify_inviter", new_callable=AsyncMock) as notify:
        assert await middleware.resolve_user(INVITEE, "uz", INVITER) == ("uz", True)
        assert await middleware.resolve_user(INVITEE, "uz", INVITER) == ("uz", False)
        assert notify.await_count == 1

    assert await _money_state(path) == (1500, 1, 1)


async def test_null_reward_falls_back_to_default():
    conn = await aiosqlite.connect(":memory:")
    try:
        await conn.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, user_balance INTEGER DEFAULT 0)"
        )
        await conn.execute(
            "CREATE TABLE referral_payouts (user_id INTEGER PRIMARY KEY, inviter_id INTEGER, "
            "amount INTEGER, ts INTEGER)"
        )
        # Legacy shape: nullable column holding NULL.
        await conn.execute(
            "CREATE TABLE webapp_admin_settings (singleton INTEGER PRIMARY KEY, referral_reward INTEGER)"
        )
        await conn.execute("INSERT INTO webapp_admin_settings VALUES (1, NULL)")
        await conn.execute("INSERT INTO users VALUES (?, 0)", (INVITER,))
        await conn.execute("INSERT INTO users VALUES (?, 0)", (INVITEE,))
        await conn.commit()

        assert await pay_referral_reward(conn, INVITEE, INVITER) == 2000
    finally:
        await conn.close()


async def test_no_payout_when_another_writer_created_the_user_first(tmp_path):
    """SELECT saw no row, but the INSERT OR IGNORE was a no-op: not ours to pay."""
    path = str(tmp_path / "bot.sqlite3")
    await _bot_db(path, 1500)
    # The concurrent creator already inserted the invitee (without paying yet).
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "INSERT INTO users (user_id, date, lang, ref_by) VALUES (?, 0, 'uz', ?)", (INVITEE, INVITER)
        )
        await conn.commit()

    middleware = StatsMiddleware(path)

    async def stale_state(conn, user_id):
        return None, True  # what the losing process read before the winner's INSERT

    with patch(f"{MW_MODULE}.fetch_user_state", side_effect=stale_state), patch(
        f"{MW_MODULE}._notify_inviter", new_callable=AsyncMock
    ) as notify:
        lang, is_new = await middleware.resolve_user(INVITEE, "uz", INVITER)
        notify.assert_not_awaited()

    assert is_new is False
    assert await _money_state(path) == (0, 0, 0)


# --------------------------------------------------------------------------
# API: /api/admin/state shows stored values and bounds them
# --------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path) -> str:
    path = str(tmp_path / "admin_money.sqlite3")
    asyncio.run(admin_fx._build_schema(path))
    admin_fx.seed_admin(path, admin_fx.OWNER_ID, "owner")
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    async def _override_get_db():
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
        finally:
            await conn.close()

    monkeypatch.setattr(get_settings(), "ADMIN_IDS", str(admin_fx.OWNER_ID), raising=False)
    app.dependency_overrides[get_db] = _override_get_db
    app.state.limiter.enabled = False
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.state.limiter.enabled = True


def test_state_shows_stored_zero_reward(client, db_path):
    headers = admin_fx.bearer(db_path, admin_fx.OWNER_ID)
    response = client.patch("/api/admin/state", headers=headers, json={"referral_reward": 0})
    assert response.status_code == 200
    assert response.json()["referral_reward"] == 0
    assert client.get("/api/admin/state", headers=headers).json()["referral_reward"] == 0
    stored = admin_fx._query(db_path, "SELECT referral_reward FROM webapp_admin_settings")
    assert stored[0]["referral_reward"] == 0


def test_state_shows_stored_zero_price(client, db_path):
    # A legacy row may hold 0 (the API never accepted it): show it, do not mask it.
    admin_fx._execute(db_path, "UPDATE webapp_admin_settings SET pro_price = 0")
    headers = admin_fx.bearer(db_path, admin_fx.OWNER_ID)
    assert client.get("/api/admin/state", headers=headers).json()["pro_price"] == 0


@pytest.mark.parametrize(
    "body",
    [
        {"pro_price": ledger.MAX_AMOUNT + 1},
        {"referral_reward": ledger.MAX_AMOUNT + 1},
        {"pro_price": 0},
        {"pro_price": -1},
        {"referral_reward": -1},
    ],
)
def test_money_settings_out_of_bounds_are_rejected(client, db_path, body):
    headers = admin_fx.bearer(db_path, admin_fx.OWNER_ID)
    response = client.patch("/api/admin/state", headers=headers, json=body)
    assert response.status_code == 422
    row = admin_fx._query(db_path, "SELECT pro_price, referral_reward, version FROM webapp_admin_settings")[0]
    assert row == {"pro_price": 10000, "referral_reward": 2000, "version": 0}


def test_money_settings_at_bounds_are_accepted(client, db_path):
    headers = admin_fx.bearer(db_path, admin_fx.OWNER_ID)
    response = client.patch(
        "/api/admin/state",
        headers=headers,
        json={"pro_price": ledger.MAX_AMOUNT, "referral_reward": ledger.MAX_AMOUNT},
    )
    assert response.status_code == 200
    assert response.json()["pro_price"] == ledger.MAX_AMOUNT
    response = client.patch("/api/admin/state", headers=headers, json={"pro_price": 1})
    assert response.status_code == 200
    assert response.json()["pro_price"] == 1
