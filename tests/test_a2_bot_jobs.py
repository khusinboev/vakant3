"""bot_jobs recovery: rows a dead process left ``running`` must not block forever."""
from __future__ import annotations

import asyncio
import functools
import time

import pytest

from src.db.connection import connect
from src.db.migrate import run_migrations
from src.functions import bot_jobs
from src.functions.bot_jobs import (
    JOB_HANDLERS,
    STALE_JOB_SECONDS,
    claim_next_job,
    enqueue_job,
    find_pending_job,
    reap_stale_jobs,
    run_claimed_job,
)

KIND = "test.a2.post_now"


@pytest.fixture
async def db(tmp_path):
    connect_db = functools.partial(connect, str(tmp_path / "jobs.sqlite3"))
    async with connect_db() as conn:
        await run_migrations(conn)
    return connect_db


async def _insert(conn, *, status, started_at, kind=KIND):
    cursor = await conn.execute(
        "INSERT INTO bot_jobs (kind, payload_json, status, created_at, started_at) "
        "VALUES (?, '{}', ?, ?, ?)",
        (kind, status, int(time.time()) - 1000, started_at),
    )
    await conn.commit()
    return int(cursor.lastrowid)


async def _status(conn, job_id):
    cursor = await conn.execute("SELECT status, error, finished_at FROM bot_jobs WHERE id = ?", (job_id,))
    return tuple(await cursor.fetchone())


async def test_reap_fails_only_running_rows_past_the_timeout(db):
    now = int(time.time())
    async with db() as conn:
        dead = await _insert(conn, status="running", started_at=now - STALE_JOB_SECONDS - 5)
        no_start = await _insert(conn, status="running", started_at=None)
        live = await _insert(conn, status="running", started_at=now - 10)
        queued = await _insert(conn, status="queued", started_at=None)

        assert await reap_stale_jobs(conn) == 2

        status, error, finished_at = await _status(conn, dead)
        assert (status, error) == ("failed", "stale: worker died") and finished_at >= now
        assert (await _status(conn, no_start))[0] == "failed"
        assert (await _status(conn, live))[0] == "running"
        assert (await _status(conn, queued))[0] == "queued"


async def test_a_dead_running_row_no_longer_counts_as_pending(db):
    """``find_pending_job`` drives the API's 409 JOB_ALREADY_QUEUED."""
    now = int(time.time())
    async with db() as conn:
        await _insert(conn, status="running", started_at=now - STALE_JOB_SECONDS - 5)
        assert await find_pending_job(conn, KIND) is None
        live = await _insert(conn, status="running", started_at=now - 10)
        assert await find_pending_job(conn, KIND) == live


async def test_loop_start_reaps_then_runs_the_queue(db):
    ran = []

    async def handler(payload):
        ran.append(payload)
        return {"ok": True}

    JOB_HANDLERS[KIND] = handler
    now = int(time.time())
    async with db() as conn:
        dead = await _insert(conn, status="running", started_at=now - STALE_JOB_SECONDS - 5)
        fresh = await enqueue_job(conn, KIND, {"n": 1})
        await conn.commit()

    task = asyncio.create_task(bot_jobs.bot_jobs_loop(connect=db, poll_seconds=0.01))
    try:
        for _ in range(200):
            async with db() as conn:
                if (await _status(conn, fresh))[0] == "done":
                    break
            await asyncio.sleep(0.01)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        JOB_HANDLERS.pop(KIND, None)

    async with db() as conn:
        assert (await _status(conn, dead))[0] == "failed"
        assert (await _status(conn, fresh))[0] == "done"
        assert await find_pending_job(conn, KIND) is None
    assert ran == [{"n": 1}]


async def test_cancellation_mid_job_leaves_a_finished_row(db):
    started = asyncio.Event()

    async def hangs(payload):
        started.set()
        await asyncio.sleep(3600)

    JOB_HANDLERS[KIND] = hangs
    try:
        async with db() as conn:
            job_id = await enqueue_job(conn, KIND, {})
            await conn.commit()
            row = await claim_next_job(conn)
            task = asyncio.create_task(run_claimed_job(conn, row))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            status, error, finished_at = await _status(conn, job_id)
            assert (status, error) == ("failed", "cancelled")
            assert finished_at is not None
            assert await find_pending_job(conn, KIND) is None
    finally:
        JOB_HANDLERS.pop(KIND, None)
