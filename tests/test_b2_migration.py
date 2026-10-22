"""m017_broadcast_retry on a database that already holds broadcasts (pre-m017 shape)."""
import aiosqlite
import pytest

from src.db.migrate import run_migrations
from src.db.migrations import (
    m008_broadcasts,
    m015_broadcast_claimed_at,
    m017_broadcast_retry,
    m019_broadcast_last_attempt,
)
from src.functions import broadcast_worker as bw

BASE = 900_000_000_000


async def _columns(conn, table):
    cursor = await conn.execute(f"PRAGMA table_info({table})")
    return {row[1]: row for row in await cursor.fetchall()}


@pytest.fixture
async def legacy(tmp_path):
    """m008 + m015 tables with rows written by the pre-stage-B worker."""
    path = tmp_path / "legacy.sqlite3"
    conn = await aiosqlite.connect(path)
    await conn.execute(
        "CREATE TABLE users (user_id INTEGER PRIMARY KEY, date INTEGER, lang TEXT, region TEXT, "
        "user_pro INTEGER NOT NULL DEFAULT 0, blocked INTEGER NOT NULL DEFAULT 0)"
    )
    await conn.executemany(
        "INSERT INTO users (user_id, date) VALUES (?, 0)", [(BASE + i,) for i in range(1, 5)]
    )
    await m008_broadcasts.apply(conn)
    await m015_broadcast_claimed_at.apply(conn)
    await conn.execute(
        "INSERT INTO broadcasts (id, actor_id, status, kind, text, total, sent, failed, blocked, created_at) "
        "VALUES (1, ?, 'running', 'text', 'salom', 4, 1, 1, 1, 0)",
        (BASE,),
    )
    await conn.executemany(
        "INSERT INTO broadcast_targets (broadcast_id, user_id, status, error, sent_at) VALUES (1, ?, ?, ?, ?)",
        [
            (BASE + 1, "sent", None, 100),
            (BASE + 2, "failed", "chat not found", None),
            (BASE + 3, "blocked", "forbidden", None),
            (BASE + 4, "pending", None, None),
        ],
    )
    await conn.commit()
    try:
        yield conn, path
    finally:
        await conn.close()


async def test_m017_adds_columns_keeps_rows_and_is_idempotent(legacy):
    conn, _ = legacy
    for _ in range(2):  # a second apply must be a no-op, not a "duplicate column" error
        await m017_broadcast_retry.apply(conn)
        await conn.commit()

    targets = await _columns(conn, "broadcast_targets")
    assert {"error_kind", "attempts", "next_attempt_at"} <= set(targets)
    assert targets["attempts"][3] == 1 and targets["attempts"][4] == "0"  # NOT NULL DEFAULT 0
    assert "content_failed" in await _columns(conn, "broadcasts")

    cursor = await conn.execute(
        "SELECT user_id, status, error, attempts, error_kind, next_attempt_at "
        "FROM broadcast_targets ORDER BY user_id"
    )
    rows = [tuple(row) for row in await cursor.fetchall()]
    assert rows == [
        (BASE + 1, "sent", None, 0, None, None),
        (BASE + 2, "failed", "chat not found", 0, None, None),
        (BASE + 3, "blocked", "forbidden", 0, None, None),
        (BASE + 4, "pending", None, 0, None, None),
    ]
    cursor = await conn.execute("SELECT sent, failed, blocked, content_failed FROM broadcasts WHERE id = 1")
    assert tuple(await cursor.fetchone()) == (1, 1, 1, 0)

    # Rows from before m017 have no kind: the breakdown derives it from the status.
    breakdown = await bw.broadcast_breakdown(conn, 1)
    assert breakdown["error_kinds"] == {"other": 1, "blocked": 1}
    assert breakdown["retry"]["scheduled"] == 0


async def test_run_migrations_on_the_legacy_db_then_the_worker_finishes_the_job(legacy):
    conn, path = legacy
    await run_migrations(conn)
    assert await run_migrations(conn) == []
    cursor = await conn.execute("SELECT 1 FROM schema_migrations WHERE id = ?", (m017_broadcast_retry.ID,))
    assert await cursor.fetchone() is not None

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def connect():
        c = await aiosqlite.connect(path)
        c.row_factory = aiosqlite.Row
        try:
            yield c
        finally:
            await c.close()

    class Bot:
        calls = []

        async def send_message(self, user_id, text, reply_markup=None):
            self.calls.append(user_id)
            return object()

    bot = Bot()
    await bw.run_broadcast(bot, 1, connect=connect, bucket=bw.TokenBucket(rate=10_000), pause=bw.SendPause())
    assert bot.calls == [BASE + 4]  # only the pending legacy row is sent
    progress = await bw.broadcast_progress(conn, 1)
    assert (progress["status"], progress["sent"]) == ("done", 2)


async def test_m017_skips_a_database_without_the_broadcast_tables(tmp_path):
    async with aiosqlite.connect(tmp_path / "empty.sqlite3") as conn:
        await m017_broadcast_retry.apply(conn)
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        assert await cursor.fetchall() == []


# ─── m019_broadcast_last_attempt ────────────────────────────────────────────

async def test_m019_adds_last_attempt_at_keeps_rows_and_is_idempotent(legacy):
    conn, _ = legacy
    await m017_broadcast_retry.apply(conn)
    for _ in range(2):  # a re-apply is a no-op, not a "duplicate column" error
        await m019_broadcast_last_attempt.apply(conn)
        await conn.commit()

    targets = await _columns(conn, "broadcast_targets")
    assert "last_attempt_at" in targets and targets["last_attempt_at"][2] == "INTEGER"
    cursor = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_broadcast_targets_errors_recent'"
    )
    assert await cursor.fetchone() is not None
    # Legacy rows keep their data; the failure time is unknown (NULL).
    cursor = await conn.execute(
        "SELECT user_id, status, error, last_attempt_at FROM broadcast_targets ORDER BY user_id"
    )
    assert [tuple(row) for row in await cursor.fetchall()] == [
        (BASE + 1, "sent", None, None),
        (BASE + 2, "failed", "chat not found", None),
        (BASE + 3, "blocked", "forbidden", None),
        (BASE + 4, "pending", None, None),
    ]


async def test_m019_through_run_migrations_is_recorded_once(legacy):
    conn, _ = legacy
    applied = await run_migrations(conn)
    assert m019_broadcast_last_attempt.ID in applied
    assert await run_migrations(conn) == []
    cursor = await conn.execute(
        "SELECT COUNT(*) FROM schema_migrations WHERE id = ?", (m019_broadcast_last_attempt.ID,)
    )
    assert (await cursor.fetchone())[0] == 1


async def test_m019_skips_a_database_without_the_broadcast_tables(tmp_path):
    async with aiosqlite.connect(tmp_path / "empty.sqlite3") as conn:
        await m019_broadcast_last_attempt.apply(conn)
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        assert await cursor.fetchall() == []
