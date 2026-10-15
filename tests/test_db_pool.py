"""API connection pool: acquire/release, cleanup, exhaustion, PRAGMAs."""

import asyncio

import pytest
from fastapi import HTTPException

from webapp.core import database


@pytest.fixture
async def db_file(tmp_path, monkeypatch):
    """Point the pool at a throwaway database and rebuild it for this loop."""
    path = tmp_path / "pool.sqlite3"
    monkeypatch.setattr(database, "DB_PATH", path)
    await database.reset_pool()
    yield path
    await database.reset_pool()


async def _drain(gen) -> None:
    """Finish a get_db dependency the way FastAPI does on success."""
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()


async def test_connection_is_reused_after_release(db_file):
    gen = database.get_db()
    first = await gen.__anext__()
    await first.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    await first.commit()
    await _drain(gen)

    pool = database.get_pool()
    assert pool.opened == 1

    gen2 = database.get_db()
    second = await gen2.__anext__()
    assert second is first
    await _drain(gen2)
    assert pool.opened == 1


async def test_uncommitted_write_is_rolled_back_on_exception(db_file):
    gen = database.get_db()
    conn = await gen.__anext__()
    await conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    await conn.commit()
    await _drain(gen)

    gen = database.get_db()
    conn = await gen.__anext__()
    await conn.execute("INSERT INTO t (id) VALUES (1)")
    assert conn.in_transaction
    with pytest.raises(RuntimeError):
        await gen.athrow(RuntimeError("boom"))

    # Same pooled connection, and the half-finished write is gone.
    gen = database.get_db()
    conn = await gen.__anext__()
    assert not conn.in_transaction
    cursor = await conn.execute("SELECT COUNT(*) FROM t")
    assert (await cursor.fetchone())[0] == 0
    await _drain(gen)


async def test_forgotten_transaction_is_rolled_back_on_success(db_file):
    gen = database.get_db()
    conn = await gen.__anext__()
    await conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    await conn.commit()
    await conn.execute("INSERT INTO t (id) VALUES (7)")  # handler forgot to commit
    await _drain(gen)

    gen = database.get_db()
    conn = await gen.__anext__()
    assert not conn.in_transaction
    cursor = await conn.execute("SELECT COUNT(*) FROM t")
    assert (await cursor.fetchone())[0] == 0
    await _drain(gen)


async def test_pool_exhaustion_raises_server_busy(db_file):
    pool = database.ConnectionPool(db_file, size=2)
    held = [await pool.acquire(), await pool.acquire()]
    try:
        with pytest.raises(HTTPException) as exc_info:
            await pool.acquire(timeout=0.05)
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["code"] == "SERVER_BUSY"
    finally:
        for conn in held:
            await pool.release(conn)
        await pool.close()


async def test_waiter_gets_the_next_released_connection(db_file):
    pool = database.ConnectionPool(db_file, size=1)
    conn = await pool.acquire()

    async def _release_soon():
        await asyncio.sleep(0.05)
        await pool.release(conn)

    task = asyncio.create_task(_release_soon())
    try:
        reacquired = await pool.acquire(timeout=2)
        assert reacquired is conn
        await pool.release(reacquired)
    finally:
        await task
        await pool.close()


async def test_pooled_connection_pragmas(db_file):
    gen = database.get_db()
    conn = await gen.__anext__()
    values = {}
    for pragma in ("journal_mode", "synchronous", "foreign_keys", "busy_timeout", "journal_size_limit"):
        cursor = await conn.execute(f"PRAGMA {pragma}")
        values[pragma] = (await cursor.fetchone())[0]
    await _drain(gen)

    assert str(values["journal_mode"]).lower() == "wal"
    assert values["synchronous"] == 1  # NORMAL
    assert values["foreign_keys"] == 1
    assert values["busy_timeout"] == 5000
    assert values["journal_size_limit"] == database.JOURNAL_SIZE_LIMIT
    assert conn.row_factory is not None


async def test_close_pool_closes_idle_connections(db_file):
    gen = database.get_db()
    conn = await gen.__anext__()
    await _drain(gen)

    await database.close_pool()
    with pytest.raises(ValueError):
        await conn.execute("SELECT 1")


async def test_discard_wakes_a_waiter_with_a_fresh_connection(db_file):
    pool = database.ConnectionPool(db_file, size=1)
    broken = await pool.acquire()
    waiter = asyncio.create_task(pool.acquire(timeout=2))
    await asyncio.sleep(0.05)
    assert not waiter.done()  # the only slot is taken

    await pool.discard(broken)
    replacement = await asyncio.wait_for(waiter, 1)  # woken, not left to time out
    try:
        assert replacement is not broken
        assert pool.opened == 1
        cursor = await replacement.execute("SELECT 1")
        assert (await cursor.fetchone())[0] == 1
    finally:
        await pool.release(replacement)
        await pool.close()


async def test_slots_never_exceed_the_pool_size(db_file):
    pool = database.ConnectionPool(db_file, size=2)
    first, second = await pool.acquire(), await pool.acquire()
    await pool.discard(first)
    third = await pool.acquire(timeout=0.5)
    with pytest.raises(HTTPException):
        await pool.acquire(timeout=0.05)
    assert pool.opened == 2
    for conn in (second, third):
        await pool.release(conn)
    await pool.close()


async def test_release_db_returns_the_connection_early_and_once(db_file):
    pool = database.get_pool()
    gen = database.get_db()
    conn = await gen.__anext__()
    await conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY)")
    await conn.commit()
    await conn.execute("INSERT INTO t (id) VALUES (1)")  # left open on purpose

    await database.release_db(conn)
    # Back in the pool (the open write rolled back): the next request gets it.
    gen2 = database.get_db()
    again = await gen2.__anext__()
    assert again is conn
    assert not again.in_transaction
    cursor = await again.execute("SELECT COUNT(*) FROM t")
    assert (await cursor.fetchone())[0] == 0

    # The first request ending later must not release it a second time.
    await _drain(gen)
    assert pool._idle == []
    await _drain(gen2)
    assert pool._idle == [conn]


async def test_release_db_ignores_a_connection_the_pool_did_not_hand_out(db_file):
    conn = await database.open_connection(db_file)
    try:
        await database.release_db(conn)  # e.g. a test's dependency override
        cursor = await conn.execute("SELECT 1")
        assert (await cursor.fetchone())[0] == 1
    finally:
        await conn.close()
