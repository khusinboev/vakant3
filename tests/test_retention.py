"""Retention sweep: what it deletes, what it keeps, what it tolerates."""

import time

import aiosqlite
import pytest

from webapp.core.retention import RESUME_EVENTS_TTL_SECONDS, checkpoint_wal, purge_expired

DAY = 24 * 60 * 60


@pytest.fixture
async def db(tmp_path):
    conn = await aiosqlite.connect(tmp_path / "retention.sqlite3")
    conn.row_factory = aiosqlite.Row
    await conn.execute(
        """
        CREATE TABLE resume_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_name TEXT NOT NULL,
            step TEXT,
            meta_json TEXT,
            created_at INTEGER NOT NULL
        )
        """
    )
    await conn.commit()
    try:
        yield conn
    finally:
        await conn.close()


async def _insert_event(conn, created_at: int) -> None:
    await conn.execute(
        "INSERT INTO resume_events (user_id, event_name, created_at) VALUES (?, ?, ?)",
        (1, "resume_started", created_at),
    )
    await conn.commit()


async def test_purges_old_resume_events_and_keeps_recent(db):
    now = int(time.time())
    await _insert_event(db, now - RESUME_EVENTS_TTL_SECONDS - DAY)  # 91 days old
    await _insert_event(db, now - 89 * DAY)
    await _insert_event(db, now)

    deleted = await purge_expired(db)
    assert deleted["resume_events"] == 1

    cursor = await db.execute("SELECT COUNT(*) FROM resume_events")
    assert (await cursor.fetchone())[0] == 2


async def test_missing_tables_are_skipped_silently(db):
    deleted = await purge_expired(db)
    # Only the one table this fixture created is reported on.
    assert set(deleted) == {"resume_events"}
    assert "admin_audit_log" not in deleted
    assert "webapp_sessions" not in deleted


async def test_purges_audit_log_when_the_table_exists(db):
    now = int(time.time())
    await db.execute(
        """
        CREATE TABLE admin_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor INTEGER NOT NULL,
            action TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
        """
    )
    await db.execute(
        "INSERT INTO admin_audit_log (actor, action, created_at) VALUES (?, ?, ?)",
        (1, "settings.patch", now - 400 * DAY),
    )
    await db.execute(
        "INSERT INTO admin_audit_log (actor, action, created_at) VALUES (?, ?, ?)",
        (1, "settings.patch", now - 10 * DAY),
    )
    await db.commit()

    deleted = await purge_expired(db)
    assert deleted["admin_audit_log"] == 1
    cursor = await db.execute("SELECT COUNT(*) FROM admin_audit_log")
    assert (await cursor.fetchone())[0] == 1


async def test_expired_sessions_go_and_live_ones_stay(db):
    now = int(time.time())
    await db.execute(
        """
        CREATE TABLE webapp_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
        """
    )
    await db.execute(
        "INSERT INTO webapp_sessions VALUES (?, ?, ?, ?)", ("dead", 1, now - 100, now - 10)
    )
    await db.execute(
        "INSERT INTO webapp_sessions VALUES (?, ?, ?, ?)", ("live", 1, now - 100, now + 3600)
    )
    await db.commit()

    deleted = await purge_expired(db)
    assert deleted["webapp_sessions"] == 1
    cursor = await db.execute("SELECT token FROM webapp_sessions")
    assert [row[0] for row in await cursor.fetchall()] == ["live"]


async def test_checkpoint_wal_is_safe_on_a_non_wal_database(db):
    assert await checkpoint_wal(db) in (True, False)
