"""Tests for src/functions/daily_rollup.py and the admin analytics/system routers.

Router tests build a minimal FastAPI app containing only the router under
test, with `get_db` overridden (FastAPI dependency_overrides, same function
object every module imports) and `webapp.core.auth.require_admin` monkeypatched
to bypass real session/init-data auth — this file never touches the shared
conftest DB and never depends on Phase 0/1 files having landed.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.timeutil import TZ, day_key
from src.db.migrate import run_migrations
from src.functions.daily_rollup import (
    backfill_missing_days,
    compute_day,
    upsert_daily_stats,
)
from webapp.core.database import get_db
from webapp.core.error_log import install_exception_handler, log_error


# --------------------------------------------------------------------------
# compute_day / backfill
# --------------------------------------------------------------------------

async def _connect(path) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(str(path))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys=OFF")
    return conn


async def _seed_full_schema(conn: aiosqlite.Connection) -> None:
    """A trimmed but realistic copy of the tables compute_day reads from."""
    await conn.execute(
        "CREATE TABLE users (user_id INTEGER PRIMARY KEY, date INTEGER, user_pro INTEGER DEFAULT 0)"
    )
    await conn.execute(
        "CREATE TABLE resume_events (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, "
        "event_name TEXT, step TEXT, meta_json TEXT, created_at INTEGER)"
    )
    await conn.execute(
        "CREATE TABLE webapp_sessions (token TEXT PRIMARY KEY, user_id INTEGER, "
        "created_at INTEGER, expires_at INTEGER)"
    )
    await conn.execute(
        "CREATE TABLE sent_notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, "
        "vacancy_uid TEXT, sent_at INTEGER)"
    )
    await conn.execute(
        "CREATE TABLE posted_vacancies (vacancy_uid TEXT, channel TEXT, posted_at INTEGER, "
        "PRIMARY KEY (vacancy_uid, channel))"
    )
    await conn.execute(
        "CREATE TABLE referral_payouts (user_id INTEGER PRIMARY KEY, inviter_id INTEGER, "
        "amount INTEGER, ts INTEGER)"
    )
    await conn.commit()
    # daily_stats, error_log, wallet_transactions, admin_audit_log, admins, ...
    await run_migrations(conn)


def _ts(day: str, hour: int = 12) -> int:
    dt = datetime.strptime(day, "%Y-%m-%d").replace(hour=hour, tzinfo=TZ)
    return int(dt.timestamp())


@pytest.fixture
async def seeded_db(tmp_path):
    conn = await _connect(tmp_path / "rollup.sqlite3")
    await _seed_full_schema(conn)
    try:
        yield conn
    finally:
        await conn.close()


async def test_compute_day_gives_expected_counts(seeded_db):
    conn = seeded_db
    day = "2025-06-10"
    other_day = "2025-06-11"

    await conn.execute("INSERT INTO users (user_id, date, user_pro) VALUES (1, ?, 1)", (_ts(day),))
    await conn.execute("INSERT INTO users (user_id, date, user_pro) VALUES (2, ?, 0)", (_ts(day),))
    await conn.execute("INSERT INTO users (user_id, date, user_pro) VALUES (3, ?, 0)", (_ts(other_day),))

    for name, uid in (("save_success", 1), ("send_success", 1), ("send_error", 2), ("autosave_success", 2)):
        await conn.execute(
            "INSERT INTO resume_events (user_id, event_name, created_at) VALUES (?, ?, ?)",
            (uid, name, _ts(day)),
        )
    # Outside the day window — must not be counted.
    await conn.execute(
        "INSERT INTO resume_events (user_id, event_name, created_at) VALUES (9, 'send_success', ?)",
        (_ts(other_day),),
    )

    await conn.execute(
        "INSERT INTO webapp_sessions (token, user_id, created_at, expires_at) VALUES ('t1', 3, ?, ?)",
        (_ts(day), _ts(day) + 1000),
    )
    await conn.execute(
        "INSERT INTO sent_notifications (user_id, vacancy_uid, sent_at) VALUES (1, 'osonish_1', ?)",
        (_ts(day),),
    )
    await conn.execute(
        "INSERT INTO posted_vacancies (vacancy_uid, channel, posted_at) VALUES ('osonish_1', 'c1', ?)",
        (_ts(day),),
    )
    # auto_post_log (m010, AUTOPOST agent) already exists in this repo state,
    # so it — not the posted_vacancies fallback — is the primary source here.
    await conn.execute(
        "INSERT INTO auto_post_log (uid, channel, message_id, status, posted_at) "
        "VALUES ('osonish_1', 'c1', 5, 'sent', ?)",
        (_ts(day),),
    )
    await conn.execute(
        "INSERT INTO auto_post_log (uid, channel, message_id, status, error, posted_at) "
        "VALUES ('osonish_2', 'c1', NULL, 'failed', 'boom', ?)",
        (_ts(day),),
    )
    # Primary source for referral_payouts/revenue once the ledger is migrated
    # (m004): wallet_transactions, not the bot's older referral_payouts table.
    await conn.execute(
        "INSERT INTO wallet_transactions (user_id, kind, amount, balance_after, price_snapshot, "
        "actor_id, note, created_at) VALUES (2, 'referral_reward', 2000, 2000, NULL, NULL, NULL, ?)",
        (_ts(day),),
    )
    await conn.execute(
        "INSERT INTO wallet_transactions (user_id, kind, amount, balance_after, price_snapshot, "
        "actor_id, note, created_at) VALUES (1, 'pro_activation', -10000, 0, 10000, NULL, NULL, ?)",
        (_ts(day),),
    )
    await conn.commit()

    stats = await compute_day(conn, day)

    assert stats["new_users"] == 2
    assert stats["pro_users"] == 1
    # active_users: distinct of {1, 2} from resume_events + {3} from webapp_sessions.
    assert stats["active_users"] == 3
    assert stats["resume_saves"] == 2  # save_success + autosave_success
    assert stats["resume_sends_ok"] == 1
    assert stats["resume_sends_err"] == 1
    assert stats["notifications"] == 1
    assert stats["referral_payouts"] == 2000
    assert stats["pro_activations"] == 1
    assert stats["revenue"] == 10000
    # auto_post_log exists -> counts only status='sent', ignoring 'failed'.
    assert stats["auto_posts"] == 1
    assert stats["saves"] == 0  # `saves` table isn't even created here.
    assert stats["computed_at"] > 0

    empty = await compute_day(conn, "2099-01-01")
    # pro_users is a snapshot at computation time (not day-bounded — see the
    # docstring), so it stays whatever it is regardless of which day is asked.
    assert all(v == 0 for k, v in empty.items() if k not in {"computed_at", "pro_users"})
    assert empty["pro_users"] == 1


async def test_auto_posts_falls_back_to_posted_vacancies_without_auto_post_log(tmp_path):
    """Guard behaviour for a DB where m010 (auto_post_log) hasn't landed yet."""
    conn = await _connect(tmp_path / "fallback.sqlite3")
    await conn.execute(
        "CREATE TABLE posted_vacancies (vacancy_uid TEXT, channel TEXT, posted_at INTEGER, "
        "PRIMARY KEY (vacancy_uid, channel))"
    )
    day = "2025-06-10"
    await conn.execute(
        "INSERT INTO posted_vacancies (vacancy_uid, channel, posted_at) VALUES ('osonish_1', 'c1', ?)",
        (_ts(day),),
    )
    await conn.commit()
    try:
        stats = await compute_day(conn, day)
        assert stats["auto_posts"] == 1
    finally:
        await conn.close()


async def test_missing_tables_tolerated(tmp_path):
    """A DB with none of the source tables must not raise, and reports zeros."""
    conn = await _connect(tmp_path / "empty.sqlite3")
    await run_migrations(conn)  # only creates daily_stats/error_log/etc., no users/saves/...
    try:
        stats = await compute_day(conn, day_key())
        assert all(v == 0 for k, v in stats.items() if k != "computed_at")
        assert stats["computed_at"] > 0
    finally:
        await conn.close()


async def test_backfill_fills_gaps(seeded_db):
    conn = seeded_db
    reference = datetime(2025, 6, 15, 3, 0, tzinfo=TZ)

    filled = await backfill_missing_days(conn, max_days=5, reference=reference)
    expected_days = [day_key(reference - timedelta(days=n)) for n in range(5, 0, -1)]
    assert filled == expected_days

    cursor = await conn.execute("SELECT COUNT(*) FROM daily_stats")
    assert (await cursor.fetchone())[0] == 5

    # Overwrite one row with a sentinel, then re-run: an already-present day
    # must be left alone (only *missing* days are (re)computed).
    sentinel_day = expected_days[2]
    await conn.execute("UPDATE daily_stats SET computed_at = 999999 WHERE day = ?", (sentinel_day,))
    await conn.commit()

    filled_again = await backfill_missing_days(conn, max_days=5, reference=reference)
    assert filled_again == []
    cursor = await conn.execute("SELECT computed_at FROM daily_stats WHERE day = ?", (sentinel_day,))
    assert (await cursor.fetchone())[0] == 999999


async def test_upsert_is_idempotent(seeded_db):
    conn = seeded_db
    day = "2025-06-10"
    stats = await compute_day(conn, day)
    await upsert_daily_stats(conn, day, stats)
    await upsert_daily_stats(conn, day, stats)  # must not raise / duplicate
    cursor = await conn.execute("SELECT COUNT(*) FROM daily_stats WHERE day = ?", (day,))
    assert (await cursor.fetchone())[0] == 1


# --------------------------------------------------------------------------
# Error log + exception handler
# --------------------------------------------------------------------------

async def test_log_error_writes_row(tmp_path):
    conn = await _connect(tmp_path / "errors.sqlite3")
    await run_migrations(conn)
    try:
        await log_error(conn, source="scheduler", message="boom", context={"foo": "bar"})
        cursor = await conn.execute("SELECT source, level, message, context_json FROM error_log")
        row = await cursor.fetchone()
        assert row["source"] == "scheduler"
        assert row["level"] == "error"
        assert row["message"] == "boom"
        assert json.loads(row["context_json"]) == {"foo": "bar"}
    finally:
        await conn.close()


async def test_log_error_never_raises_on_missing_table(tmp_path):
    conn = await _connect(tmp_path / "no_table.sqlite3")
    try:
        # No migrations run: error_log does not exist.
        await log_error(conn, source="api", message="should not raise")
    finally:
        await conn.close()


def test_exception_handler_writes_row_and_returns_code(tmp_path, monkeypatch):
    db_path = tmp_path / "handler.sqlite3"

    async def _prepare():
        conn = await _connect(db_path)
        await run_migrations(conn)
        await conn.close()

    asyncio.run(_prepare())

    monkeypatch.setattr("webapp.core.database.DB_PATH", db_path)

    app = FastAPI()
    install_exception_handler(app)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("kaboom")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")

    assert resp.status_code == 500
    body = resp.json()
    assert body["detail"]["code"] == "INTERNAL_ERROR"
    assert isinstance(body["detail"]["request_id"], str) and body["detail"]["request_id"]

    async def _check():
        conn = await _connect(db_path)
        try:
            cursor = await conn.execute("SELECT source, message FROM error_log")
            row = await cursor.fetchone()
            assert row["source"] == "api"
            assert "kaboom" in row["message"]
        finally:
            await conn.close()

    asyncio.run(_check())


# --------------------------------------------------------------------------
# admin_analytics / admin_system routers
# --------------------------------------------------------------------------

async def _fake_require_admin(request=None, db=None):
    return {"user_id": 1, "role": "owner", "user": {"user_id": 1}}


def _build_app(router, db_path, monkeypatch):
    import webapp.core.auth as auth_module

    monkeypatch.setattr(auth_module, "require_admin", _fake_require_admin)

    async def override_get_db():
        conn = await aiosqlite.connect(str(db_path))
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_db] = override_get_db
    return app


def test_system_endpoint_works_on_temp_db(tmp_path, monkeypatch):
    from webapp.routers import admin_system

    db_path = tmp_path / "system.sqlite3"

    async def _prepare():
        conn = await _connect(db_path)
        await _seed_full_schema(conn)
        # m005 only creates the table; the singleton row is inserted by the
        # bot/API init_db, not by the migration itself.
        await conn.execute("INSERT INTO webapp_admin_settings (singleton) VALUES (1)")
        await conn.execute(
            "UPDATE webapp_admin_settings SET auto_post_scheduled_times_json = ? WHERE singleton = 1",
            (json.dumps(["09:00", "14:00"]),),
        )
        cursor = await conn.execute("PRAGMA table_info(webapp_admin_settings)")
        cols = {row[1] for row in await cursor.fetchall()}
        if "auto_post_scheduled_day" not in cols:
            await conn.execute(
                "ALTER TABLE webapp_admin_settings ADD COLUMN auto_post_scheduled_day TEXT DEFAULT ''"
            )
        if "last_weekly_stats_week" not in cols:
            await conn.execute(
                "ALTER TABLE webapp_admin_settings ADD COLUMN last_weekly_stats_week TEXT DEFAULT ''"
            )
        await conn.execute(
            "UPDATE webapp_admin_settings SET auto_post_scheduled_day = '2025-06-10', "
            "last_weekly_stats_week = '2025-W24' WHERE singleton = 1"
        )
        await conn.commit()
        await conn.close()

    asyncio.run(_prepare())

    monkeypatch.setattr(admin_system, "DB_PATH", str(db_path))

    async def _no_redis():
        return None

    monkeypatch.setattr("src.functions.cache.get_redis", _no_redis)

    app = _build_app(admin_system.router, db_path, monkeypatch)
    client = TestClient(app)

    resp = client.get("/api/admin/system")
    assert resp.status_code == 200
    body = resp.json()
    assert body["db"]["size_bytes"] > 0
    assert body["counts"]["users"] == 0
    assert body["schedulers"]["weekly_stats"]["last_week"] == "2025-W24"
    assert body["schedulers"]["auto_post"]["scheduled_day"] == "2025-06-10"
    assert body["schedulers"]["auto_post"]["next_slots"] == ["09:00", "14:00"]
    assert body["redis"] is False
    assert isinstance(body["uptime"], int)


def test_analytics_overview_endpoint(tmp_path, monkeypatch):
    from webapp.routers import admin_analytics

    db_path = tmp_path / "analytics.sqlite3"

    async def _prepare():
        conn = await _connect(db_path)
        await _seed_full_schema(conn)
        await conn.execute("INSERT INTO users (user_id, date, user_pro) VALUES (42, ?, 1)", (int(time.time()),))
        stats = await compute_day(conn, day_key(datetime.now(TZ) - timedelta(days=1)))
        await upsert_daily_stats(conn, day_key(datetime.now(TZ) - timedelta(days=1)), stats)
        await conn.close()

    asyncio.run(_prepare())

    app = _build_app(admin_analytics.router, db_path, monkeypatch)
    client = TestClient(app)

    resp = client.get("/api/admin/analytics/overview?days=7")
    assert resp.status_code == 200
    body = resp.json()
    assert body["days"] == 7
    assert isinstance(body["series"], list) and len(body["series"]) == 1
    assert body["today"]["new_users"] == 1


def test_errors_and_audit_pagination(tmp_path, monkeypatch):
    from webapp.routers import admin_system

    db_path = tmp_path / "pagination.sqlite3"

    async def _prepare():
        conn = await _connect(db_path)
        await _seed_full_schema(conn)
        for i in range(5):
            await log_error(conn, source="api", message=f"err-{i}", context={"i": i})
        for i in range(5):
            await conn.execute(
                "INSERT INTO admin_audit_log (actor_id, action, target_type, target_id, "
                "payload_json, ip, created_at) VALUES (1, 'settings.patch', 'user', ?, NULL, NULL, ?)",
                (str(i), int(time.time()) + i),
            )
        await conn.commit()
        await conn.close()

    asyncio.run(_prepare())

    monkeypatch.setattr(admin_system, "DB_PATH", str(db_path))
    app = _build_app(admin_system.router, db_path, monkeypatch)
    client = TestClient(app)

    seen_ids: list[int] = []
    cursor = None
    for _ in range(10):
        url = "/api/admin/errors?limit=2"
        if cursor:
            url += f"&cursor={cursor}"
        resp = client.get(url)
        assert resp.status_code == 200
        body = resp.json()
        seen_ids.extend(item["id"] for item in body["items"])
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert len(seen_ids) == 5
    assert seen_ids == sorted(seen_ids, reverse=True)
    assert len(set(seen_ids)) == 5

    resp = client.get("/api/admin/audit?limit=2&action=settings.patch")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] is not None
    assert all(item["action"] == "settings.patch" for item in body["items"])

    resp = client.get("/api/admin/audit?actor=999")
    body = resp.json()
    assert body["items"] == []
