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


async def test_checkpoint_wal_is_a_noop_success_on_a_non_wal_database(db):
    cursor = await db.execute("PRAGMA journal_mode")
    assert str((await cursor.fetchone())[0]).lower() != "wal"
    # SQLite answers (0, -1, -1) outside WAL mode: nothing to do, not "busy".
    assert await checkpoint_wal(db) is True


async def test_checkpoint_wal_truncates_the_wal(tmp_path):
    path = tmp_path / "wal.sqlite3"
    conn = await aiosqlite.connect(path)
    try:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("CREATE TABLE t (v TEXT)")
        await conn.executemany("INSERT INTO t VALUES (?)", [("x" * 500,)] * 200)
        await conn.commit()
        wal = tmp_path / "wal.sqlite3-wal"
        assert wal.stat().st_size > 0
        assert await checkpoint_wal(conn) is True
        assert wal.stat().st_size == 0
    finally:
        await conn.close()


async def test_checkpoint_wal_reports_busy_when_a_reader_blocks_it(tmp_path):
    path = tmp_path / "busy.sqlite3"
    writer = await aiosqlite.connect(path)
    reader = await aiosqlite.connect(path)
    try:
        await writer.execute("PRAGMA journal_mode=WAL")
        await writer.execute("PRAGMA busy_timeout=50")  # do not wait out the reader
        await writer.execute("CREATE TABLE t (v INTEGER)")
        await writer.commit()
        await reader.execute("BEGIN")
        await (await reader.execute("SELECT COUNT(*) FROM t")).fetchone()  # read snapshot held
        await writer.execute("INSERT INTO t VALUES (1)")
        await writer.commit()
        assert await checkpoint_wal(writer) is False
    finally:
        await reader.close()
        await writer.close()


async def _create(db, ddl: str) -> None:
    await db.execute(ddl)
    await db.commit()


async def test_purges_old_error_log_rows(db):
    now = int(time.time())
    await _create(
        db,
        "CREATE TABLE error_log (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at INTEGER NOT NULL, "
        "source TEXT NOT NULL, level TEXT NOT NULL DEFAULT 'error', message TEXT NOT NULL, context_json TEXT)",
    )
    for age_days in (31, 29, 0):
        await db.execute(
            "INSERT INTO error_log (created_at, source, message) VALUES (?, 'api', ?)",
            (now - age_days * DAY, f"age {age_days}"),
        )
    await db.commit()

    deleted = await purge_expired(db)
    assert deleted["error_log"] == 1
    cursor = await db.execute("SELECT message FROM error_log ORDER BY id")
    assert [r[0] for r in await cursor.fetchall()] == ["age 29", "age 0"]


async def test_purges_targets_of_long_finished_broadcasts_only(db):
    now = int(time.time())
    await _create(
        db,
        "CREATE TABLE broadcasts (id INTEGER PRIMARY KEY, status TEXT NOT NULL, created_at INTEGER, "
        "started_at INTEGER, finished_at INTEGER)",
    )
    await _create(
        db,
        "CREATE TABLE broadcast_targets (broadcast_id INTEGER NOT NULL, user_id INTEGER NOT NULL, "
        "status TEXT NOT NULL DEFAULT 'pending', error TEXT, sent_at INTEGER, PRIMARY KEY (broadcast_id, user_id))",
    )
    old = now - 40 * DAY
    broadcasts = [
        (1, "done", old, old, old),            # finished 40 d ago -> purge
        (2, "cancelled", old, None, None),     # cancelled long ago, no finished_at -> purge
        (3, "failed", old, old, now - 5 * DAY),  # finished recently -> keep
        (4, "paused", old, old, None),         # still resumable -> keep
        (5, "running", old, old, None),        # live -> keep
    ]
    await db.executemany("INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?)", broadcasts)
    await db.executemany(
        "INSERT INTO broadcast_targets (broadcast_id, user_id, status) VALUES (?, ?, 'sent')",
        [(b[0], 900000000000 + u) for b in broadcasts for u in range(3)],
    )
    await db.commit()

    deleted = await purge_expired(db)
    assert deleted["broadcast_targets"] == 6
    cursor = await db.execute("SELECT DISTINCT broadcast_id FROM broadcast_targets ORDER BY 1")
    assert [r[0] for r in await cursor.fetchall()] == [3, 4, 5]
    cursor = await db.execute("SELECT COUNT(*) FROM broadcasts")
    assert (await cursor.fetchone())[0] == 5  # the history rows stay


async def test_broadcast_targets_need_the_broadcasts_table(db):
    await _create(db, "CREATE TABLE broadcast_targets (broadcast_id INTEGER, user_id INTEGER)")
    deleted = await purge_expired(db)
    assert "broadcast_targets" not in deleted


async def test_purges_stale_subscription_checks(db):
    now = int(time.time())
    await _create(
        db,
        "CREATE TABLE subscription_checks (user_id INTEGER PRIMARY KEY, checked_at INTEGER NOT NULL, "
        "ok INTEGER NOT NULL, missing_json TEXT NOT NULL DEFAULT '[]')",
    )
    await db.executemany(
        "INSERT INTO subscription_checks (user_id, checked_at, ok) VALUES (?, ?, 1)",
        [(1, now - 2 * DAY), (2, now - 600), (3, now)],
    )
    await db.commit()
    deleted = await purge_expired(db)
    assert deleted["subscription_checks"] == 1
    cursor = await db.execute("SELECT user_id FROM subscription_checks ORDER BY 1")
    assert [r[0] for r in await cursor.fetchall()] == [2, 3]


async def test_deletes_in_chunks_with_a_commit_per_chunk(db, monkeypatch):
    now = int(time.time())
    old = now - RESUME_EVENTS_TTL_SECONDS - DAY
    await db.executemany(
        "INSERT INTO resume_events (user_id, event_name, created_at) VALUES (1, 'resume_started', ?)",
        [(old,)] * 23 + [(now,)] * 4,
    )
    await db.commit()

    statements: list[str] = []
    commits = {"n": 0}
    real_execute, real_commit = db.execute, db.commit

    async def spy_execute(sql, params=()):
        statements.append(sql)
        return await real_execute(sql, params)

    async def spy_commit():
        commits["n"] += 1
        return await real_commit()

    monkeypatch.setattr(db, "execute", spy_execute)
    monkeypatch.setattr(db, "commit", spy_commit)

    deleted = await purge_expired(db, chunk=10)
    assert deleted["resume_events"] == 23
    deletes = [s for s in statements if s.startswith("DELETE FROM resume_events")]
    assert len(deletes) == 3  # 10 + 10 + 3
    assert commits["n"] == 3
    monkeypatch.undo()
    cursor = await db.execute("SELECT COUNT(*) FROM resume_events")
    assert (await cursor.fetchone())[0] == 4
