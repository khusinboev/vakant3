"""``webapp.core.event_queue``: batching, draining and dropping.

``resume_events`` rows are analytics only, so they are buffered in memory and
written by one background task instead of costing a COMMIT per request. These
tests pin the three behaviours the rest of the system depends on: the flusher
eventually writes everything, a clean shutdown loses nothing, and a queue that
cannot keep up drops instead of growing.
"""

import asyncio

import aiosqlite
import pytest

from webapp.core import event_queue as eq
from webapp.core.event_queue import EventQueue, enqueue_event, get_event_queue
from webapp.resume.router import is_autosave_key, track_event

RESUME_EVENTS_DDL = """
CREATE TABLE resume_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    event_name TEXT NOT NULL,
    step TEXT,
    meta_json TEXT,
    created_at INTEGER NOT NULL
)
"""


@pytest.fixture
async def event_db(tmp_path, monkeypatch):
    """A throwaway DB plus an ``open_connection`` that always points at it."""
    path = tmp_path / "events.sqlite3"
    conn = await aiosqlite.connect(str(path))
    conn.row_factory = aiosqlite.Row
    await conn.execute(RESUME_EVENTS_DDL)
    await conn.commit()

    async def _open(db_path=None):
        new = await aiosqlite.connect(str(path))
        new.row_factory = aiosqlite.Row
        return new

    monkeypatch.setattr(eq, "open_connection", _open)
    try:
        yield conn
    finally:
        await conn.close()


async def _count(conn) -> int:
    cursor = await conn.execute("SELECT COUNT(*) FROM resume_events")
    return int((await cursor.fetchone())[0])


async def _wait_for_rows(conn, expected: int, timeout: float = 3.0) -> int:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        found = await _count(conn)
        if found >= expected:
            return found
        await asyncio.sleep(0.02)
    return await _count(conn)


async def test_flush_writes_buffered_rows(event_db):
    queue = EventQueue()
    assert queue.enqueue(7, "builder_opened", "basic", '{"a":1}') is True
    assert queue.enqueue(7, "save_success", "final", None) is True
    assert queue.pending == 2
    assert await _count(event_db) == 0  # nothing hits the DB before a flush

    written = await queue.flush()
    assert written == 2
    assert queue.pending == 0

    cursor = await event_db.execute(
        "SELECT user_id, event_name, step, meta_json, created_at FROM resume_events ORDER BY id"
    )
    rows = [dict(r) for r in await cursor.fetchall()]
    assert [r["event_name"] for r in rows] == ["builder_opened", "save_success"]
    assert rows[0]["step"] == "basic" and rows[0]["meta_json"] == '{"a":1}'
    assert rows[1]["meta_json"] is None
    assert all(r["created_at"] > 0 for r in rows)

    assert await queue.flush() == 0  # empty buffer is a no-op


async def test_flusher_task_writes_on_the_interval(event_db):
    queue = EventQueue(interval=0.05, batch_size=1000)
    await queue.start()
    try:
        queue.enqueue(1, "builder_ready")
        assert await _wait_for_rows(event_db, 1) == 1
    finally:
        await queue.stop()


async def test_flusher_task_writes_early_on_a_full_batch(event_db):
    """A full batch must not wait for the (long) interval."""
    queue = EventQueue(interval=30.0, batch_size=3)
    await queue.start()
    try:
        for _ in range(3):
            queue.enqueue(2, "autosave_success", "basic")
        assert await _wait_for_rows(event_db, 3) == 3
    finally:
        await queue.stop()


async def test_stop_drains_the_buffer(event_db):
    """Shutdown writes what is pending even though the interval has not elapsed."""
    queue = EventQueue(interval=30.0, batch_size=1000)
    await queue.start()
    queue.enqueue(3, "send_success", "final")
    queue.enqueue(3, "export_success", "final")

    await queue.stop()

    assert queue.pending == 0
    assert queue.running is False
    assert await _count(event_db) == 2


async def test_stop_flushes_events_enqueued_without_a_running_task(event_db):
    queue = EventQueue(interval=30.0)
    queue.enqueue(4, "builder_opened")
    await queue.stop()
    assert await _count(event_db) == 1


async def test_overflow_drops_and_counts(event_db):
    queue = EventQueue(max_size=5)
    for _ in range(5):
        assert queue.enqueue(5, "builder_opened") is True
    assert queue.enqueue(5, "builder_opened") is False
    assert queue.enqueue(5, "builder_opened") is False

    assert queue.pending == 5
    assert queue.dropped == 2

    # The buffer never grows past the ceiling; what fits is still written.
    assert await queue.flush() == 5
    assert await _count(event_db) == 5


async def test_failing_flush_drops_the_batch(tmp_path, monkeypatch):
    """A broken table must not pin the buffer at its ceiling forever."""
    path = tmp_path / "no-table.sqlite3"

    async def _open(db_path=None):
        return await aiosqlite.connect(str(path))

    monkeypatch.setattr(eq, "open_connection", _open)
    queue = EventQueue()
    queue.enqueue(6, "builder_opened")
    assert await queue.flush() == 0
    assert queue.pending == 0
    assert queue.dropped == 1


async def test_track_event_uses_the_process_queue():
    """``POST /api/resume/events`` enqueues instead of writing."""
    queue = get_event_queue()
    queue._buffer.clear()  # this test owns the singleton for its duration
    try:
        track_event(9, "builder_opened", "basic", None)
        enqueue_event(9, "save_success")
        assert queue.pending == 2
    finally:
        queue._buffer.clear()


@pytest.mark.parametrize(
    "key,expected",
    [
        ("resume_autosave:1730712345678:x7f2ab", True),
        ("RESUME_AUTOSAVE:1730712345678:x7f2ab", True),
        ("resume_save:1730712345678:x7f2ab", False),
        ("", False),
    ],
)
def test_autosave_keys_are_recognised(key, expected):
    """Autosave writes no idempotency row; an explicit save still does."""
    assert is_autosave_key(key) is expected
