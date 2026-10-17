"""Ledger invariants (Phase 0).

These talk to ``webapp.core.ledger`` over a throwaway SQLite file directly, so
they do not depend on the API app, auth, confirmation tokens or the audit log.
"""

import asyncio

import aiosqlite
import pytest

from src.db.migrate import run_migrations
from webapp.core import ledger


async def _open(path) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA busy_timeout=5000")
    return conn


async def _setup(path) -> aiosqlite.Connection:
    conn = await _open(path)
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            lang TEXT,
            date INTEGER,
            ref_by INTEGER,
            user_balance INTEGER DEFAULT 0,
            user_pro INTEGER DEFAULT 0
        )
        """
    )
    await conn.commit()
    await run_migrations(conn)
    return conn


async def _add_user(conn, user_id: int, balance: int = 0, pro: int = 0) -> None:
    await conn.execute(
        "INSERT OR REPLACE INTO users (user_id, date, user_balance, user_pro) VALUES (?, 0, ?, ?)",
        (user_id, balance, pro),
    )
    await conn.commit()


async def _balance(conn, user_id: int) -> int:
    cursor = await conn.execute("SELECT user_balance FROM users WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    return int(row[0] or 0)


async def _ledger_sum(conn, user_id: int) -> int:
    cursor = await conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM wallet_transactions WHERE user_id = ?", (user_id,)
    )
    return int((await cursor.fetchone())[0])


async def _tx_count(conn, user_id: int, kind: str | None = None) -> int:
    sql = "SELECT COUNT(*) FROM wallet_transactions WHERE user_id = ?"
    params: list = [user_id]
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    cursor = await conn.execute(sql, tuple(params))
    return int((await cursor.fetchone())[0])


@pytest.fixture
async def db(tmp_path):
    conn = await _setup(tmp_path / "ledger.sqlite3")
    try:
        yield conn
    finally:
        await conn.close()


async def test_balance_after_matches_users_row(db):
    await _add_user(db, 10, balance=0)

    result = await ledger.apply_balance_change(db, user_id=10, amount=5_000, kind="admin_credit")
    await db.commit()
    assert result["balance_after"] == await _balance(db, 10) == 5_000

    result = await ledger.apply_balance_change(
        db, user_id=10, amount=-1_500, kind="adjustment", require_sufficient=True
    )
    await db.commit()
    assert result["balance_after"] == await _balance(db, 10) == 3_500

    result = await ledger.activate_pro(db, 10, 1_000)
    await db.commit()
    assert result["balance_after"] == await _balance(db, 10) == 2_500


async def test_sum_of_amounts_equals_balance_from_zero(db):
    await _add_user(db, 11, balance=0)
    for amount in (1_000, 7_000, -2_000, 400):
        await ledger.apply_balance_change(
            db,
            user_id=11,
            amount=amount,
            kind="admin_credit" if amount > 0 else "adjustment",
            require_sufficient=amount < 0,
        )
        await db.commit()
    await ledger.activate_pro(db, 11, 3_000)
    await db.commit()

    assert await _ledger_sum(db, 11) == await _balance(db, 11) == 3_400


async def test_insufficient_balance_writes_nothing(db):
    await _add_user(db, 12, balance=500)

    with pytest.raises(ledger.InsufficientBalance) as excinfo:
        await ledger.apply_balance_change(
            db, user_id=12, amount=-900, kind="adjustment", require_sufficient=True
        )
    await db.rollback()
    assert excinfo.value.required == 900
    assert excinfo.value.balance == 500

    with pytest.raises(ledger.InsufficientBalance):
        await ledger.activate_pro(db, 12, 900)
    await db.rollback()

    assert await _balance(db, 12) == 500
    assert await _tx_count(db, 12) == 0


async def test_already_pro_and_unknown_user(db):
    await _add_user(db, 13, balance=5_000, pro=1)
    with pytest.raises(ledger.AlreadyPro):
        await ledger.activate_pro(db, 13, 1_000)
    await db.rollback()
    assert await _tx_count(db, 13) == 0

    with pytest.raises(ledger.UserNotFound):
        await ledger.activate_pro(db, 999_999, 1_000)
    with pytest.raises(ledger.UserNotFound):
        await ledger.apply_balance_change(db, user_id=999_999, amount=10, kind="admin_credit")
    await db.rollback()


async def test_amount_bound_is_enforced(db):
    await _add_user(db, 14, balance=0)
    with pytest.raises(ValueError):
        await ledger.apply_balance_change(
            db, user_id=14, amount=ledger.MAX_AMOUNT + 1, kind="admin_credit"
        )
    assert await _tx_count(db, 14) == 0


async def test_reset_user_records_the_delta(db):
    await _add_user(db, 15, balance=4_200, pro=1)
    result = await ledger.reset_user(db, user_id=15, actor_id=1, note="test")
    await db.commit()

    assert result["balance_after"] == 0
    assert result["amount"] == -4_200
    cursor = await db.execute("SELECT user_balance, user_pro FROM users WHERE user_id = 15")
    row = await cursor.fetchone()
    assert (int(row[0]), int(row[1])) == (0, 0)
    assert await _tx_count(db, 15, "admin_reset") == 1


async def test_concurrent_activate_pro_charges_once(tmp_path):
    path = tmp_path / "concurrent.sqlite3"
    setup = await _setup(path)
    await _add_user(setup, 20, balance=10_000)
    await setup.close()

    async def worker():
        conn = await _open(path)
        try:
            try:
                result = await ledger.activate_pro(conn, 20, 10_000)
                await conn.commit()
                return result
            except ledger.LedgerError as exc:
                await conn.rollback()
                return exc
        finally:
            await conn.close()

    results = await asyncio.gather(worker(), worker())
    winners = [r for r in results if isinstance(r, dict)]
    losers = [r for r in results if isinstance(r, ledger.LedgerError)]
    assert len(winners) == 1, results
    assert len(losers) == 1 and isinstance(losers[0], (ledger.AlreadyPro, ledger.InsufficientBalance))

    conn = await _open(path)
    try:
        assert await _tx_count(conn, 20, "pro_activation") == 1
        assert await _balance(conn, 20) == 0
        assert await _ledger_sum(conn, 20) == -10_000
    finally:
        await conn.close()


async def test_list_transactions_pages_newest_first(db):
    await _add_user(db, 21, balance=0)
    for _ in range(5):
        await ledger.apply_balance_change(db, user_id=21, amount=100, kind="admin_credit")
    await db.commit()

    first = await ledger.list_transactions(db, user_id=21, limit=2)
    assert [row["id"] for row in first] == sorted([row["id"] for row in first], reverse=True)
    second = await ledger.list_transactions(db, user_id=21, before_id=first[-1]["id"], limit=2)
    assert all(row["id"] < first[-1]["id"] for row in second)
    assert len(await ledger.list_transactions(db, user_id=21, limit=50)) == 5


async def test_referral_payout_writes_one_ledger_row(tmp_path):
    from src.middleware.middlewares import pay_referral_reward

    conn = await _setup(tmp_path / "referral.sqlite3")
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS referral_payouts (
                user_id INTEGER PRIMARY KEY,
                inviter_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                ts INTEGER NOT NULL
            )
            """
        )
        await conn.commit()
        await _add_user(conn, 100, balance=0)  # inviter
        await _add_user(conn, 200, balance=0)  # invited

        reward = await pay_referral_reward(conn, user_id=200, inviter_id=100)
        assert reward is not None
        # The middleware may run again for the same user: no second payout, no second row.
        assert await pay_referral_reward(conn, user_id=200, inviter_id=100) is None

        assert await _tx_count(conn, 100, "referral_reward") == 1
        assert await _balance(conn, 100) == reward
        assert await _ledger_sum(conn, 100) == reward

        await _add_user(conn, 201, balance=0)
        await pay_referral_reward(conn, user_id=201, inviter_id=100)
        assert await _tx_count(conn, 100, "referral_reward") == 2
        assert await _ledger_sum(conn, 100) == await _balance(conn, 100)
    finally:
        await conn.close()


async def test_settings_cache_refetches_when_version_changes(tmp_path):
    from src.db import settings as bot_settings

    conn = await _open(tmp_path / "settings.sqlite3")
    try:
        await conn.execute(
            """
            CREATE TABLE webapp_admin_settings (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                pro_price INTEGER NOT NULL DEFAULT 10000,
                version INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        await conn.execute(
            "INSERT INTO webapp_admin_settings (singleton, pro_price, version) VALUES (1, 10000, 0)"
        )
        await conn.commit()
        bot_settings.invalidate_settings_cache()

        assert (await bot_settings.get_admin_settings(conn, ttl=600))["pro_price"] == 10000

        # Same version, inside the TTL -> the cached row is reused.
        await conn.execute("UPDATE webapp_admin_settings SET pro_price = 20000 WHERE singleton = 1")
        await conn.commit()
        assert (await bot_settings.get_admin_settings(conn, ttl=600))["pro_price"] == 10000

        # The API bumps version on every PATCH -> the cache must refetch at once.
        await conn.execute("UPDATE webapp_admin_settings SET version = version + 1")
        await conn.commit()
        fresh = await bot_settings.get_admin_settings(conn, ttl=600)
        assert fresh["pro_price"] == 20000
        assert int(fresh["version"]) == 1
    finally:
        bot_settings.invalidate_settings_cache()
        await conn.close()


async def test_settings_cache_without_version_column(tmp_path):
    """m005 may not have run yet: absence of the column behaves as version 0."""
    from src.db import settings as bot_settings

    conn = await _open(tmp_path / "settings_old.sqlite3")
    try:
        await conn.execute(
            "CREATE TABLE webapp_admin_settings (singleton INTEGER PRIMARY KEY, pro_price INTEGER)"
        )
        await conn.execute("INSERT INTO webapp_admin_settings VALUES (1, 777)")
        await conn.commit()
        bot_settings.invalidate_settings_cache()

        assert await bot_settings.read_settings_version(conn) == 0
        assert (await bot_settings.get_admin_settings(conn, ttl=600))["pro_price"] == 777
        assert (await bot_settings.get_admin_settings(conn, ttl=600))["pro_price"] == 777
    finally:
        bot_settings.invalidate_settings_cache()
        await conn.close()
