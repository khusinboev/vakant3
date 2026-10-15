"""Generic job queue for the bot process (table ``bot_jobs``, m010).

The API enqueues work here (currently only "post this vacancy now") and the
bot polls and executes it, because the bot process is the only one holding
the aiogram ``Bot`` instance. Dispatch is a plain dict keyed by ``kind`` so
new job types (e.g. broadcast control) can register a handler without
touching the loop itself.

Claiming is exclusive: a row is only ever picked up by one poller because the
claim is a single ``UPDATE ... WHERE status = 'queued' AND id = ?`` whose
rowcount tells the caller whether it actually won the row. Two pollers racing
for the same job — two bot instances, or a slow tick overlapping the next
one — always leave exactly one of them with rowcount 1.

A handler failure (including a timeout) is caught here and stored on the row;
it never propagates out of ``bot_jobs_loop``, so one broken job cannot stop
the loop from picking up the next one.

A row can still be left ``running`` when the process dies mid-job (SIGKILL,
OOM, a deploy restart). No live poller can hold a job longer than
``JOB_TIMEOUT_SECONDS``, so ``reap_stale_jobs`` fails such rows (after
``STALE_JOB_SECONDS``) at loop start
and every ``REAP_INTERVAL_SECONDS``; otherwise ``find_pending_job`` would keep
reporting them and "post now" would answer 409 forever. Stale jobs are failed,
not re-queued: a half-run ``auto_post.post_now`` may already have posted.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import aiosqlite

from src.db.connection import connect
from src.db.settings import invalidate_settings_cache

logger = logging.getLogger(__name__)

POLL_SECONDS = 5
JOB_TIMEOUT_SECONDS = 120
#: A ``running`` row older than this has no live owner: the handler would have
#: timed out already. The margin covers the result write after a slow handler.
STALE_JOB_SECONDS = JOB_TIMEOUT_SECONDS + 30
#: How often the loop looks for ``running`` rows a dead process left behind.
REAP_INTERVAL_SECONDS = 60

JobHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]]

#: kind -> async fn(payload) -> dict. Populated via ``register_job`` at import
#: time (see ``src/functions/auto_post_scheduler.py`` for ``auto_post.post_now``).
JOB_HANDLERS: dict[str, JobHandler] = {}


def register_job(kind: str) -> Callable[[JobHandler], JobHandler]:
    """Decorator: register ``fn`` as the handler for job ``kind``."""

    def decorator(fn: JobHandler) -> JobHandler:
        JOB_HANDLERS[kind] = fn
        return fn

    return decorator


async def enqueue_job(
    conn: aiosqlite.Connection,
    kind: str,
    payload: dict[str, Any] | None = None,
    created_by: int | None = None,
) -> int:
    """INSERT a queued job. The caller commits (same convention as audit rows)."""
    cursor = await conn.execute(
        "INSERT INTO bot_jobs (kind, payload_json, status, created_by, created_at) "
        "VALUES (?, ?, 'queued', ?, ?)",
        (kind, json.dumps(payload or {}), created_by, int(time.time())),
    )
    return int(cursor.lastrowid)


#: Statuses that mean "this job has not finished yet".
PENDING_STATUSES = ("queued", "running")


async def find_pending_job(conn: aiosqlite.Connection, kind: str) -> int | None:
    """Id of an unfinished job of ``kind``, or None.

    Used to keep a kind that must not overlap with itself — ``auto_post.post_now``
    posts to the channel, so two of them queued together post twice — from being
    enqueued twice. Not a lock: the loop runs one job at a time, so this only has
    to stop the *queue* from filling with duplicates a double-click produced.
    A ``running`` row past ``STALE_JOB_SECONDS`` is a dead claim, not a pending
    job, even before the bot's reaper has marked it failed.
    """
    placeholders = ",".join("?" for _ in PENDING_STATUSES)
    cursor = await conn.execute(
        f"SELECT id FROM bot_jobs WHERE kind = ? AND status IN ({placeholders}) "
        "AND NOT (status = 'running' AND COALESCE(started_at, 0) < ?) "
        "ORDER BY id LIMIT 1",
        (kind, *PENDING_STATUSES, int(time.time()) - STALE_JOB_SECONDS),
    )
    row = await cursor.fetchone()
    return int(row[0]) if row is not None else None


async def claim_next_job(conn: aiosqlite.Connection) -> aiosqlite.Row | None:
    """Atomically claim the oldest queued job, or ``None`` if there is none / lost the race."""
    cursor = await conn.execute(
        "SELECT id, kind, payload_json FROM bot_jobs WHERE status = 'queued' ORDER BY id LIMIT 1"
    )
    row = await cursor.fetchone()
    if row is None:
        return None

    job_id = int(row["id"])
    claim = await conn.execute(
        "UPDATE bot_jobs SET status = 'running', started_at = ? WHERE id = ? AND status = 'queued'",
        (int(time.time()), job_id),
    )
    await conn.commit()
    if claim.rowcount != 1:
        return None  # another poller claimed it first
    return row


async def run_claimed_job(conn: aiosqlite.Connection, row: aiosqlite.Row) -> None:
    """Run the handler for an already-claimed row and store result/error. Never raises."""
    job_id = int(row["id"])
    kind = str(row["kind"])
    try:
        payload = json.loads(row["payload_json"] or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    handler = JOB_HANDLERS.get(kind)
    if handler is None:
        await conn.execute(
            "UPDATE bot_jobs SET status = 'failed', error = ?, finished_at = ? WHERE id = ?",
            (f"unknown job kind: {kind}", int(time.time()), job_id),
        )
        await conn.commit()
        return

    try:
        result = await asyncio.wait_for(handler(payload), timeout=JOB_TIMEOUT_SECONDS)
        await conn.execute(
            "UPDATE bot_jobs SET status = 'done', result_json = ?, finished_at = ? WHERE id = ?",
            (json.dumps(result if result is not None else {}), int(time.time()), job_id),
        )
    except asyncio.CancelledError:
        # Shutdown mid-job: record it instead of leaving the row 'running'.
        # Failed rather than re-queued, since the handler may already have done
        # part of its work (a channel post). If even this write fails,
        # reap_stale_jobs fails the row on the next start.
        logger.warning("bot_jobs: job %s (%s) cancelled", job_id, kind)
        try:
            await conn.execute(
                "UPDATE bot_jobs SET status = 'failed', error = ?, finished_at = ? "
                "WHERE id = ? AND status = 'running'",
                ("cancelled", int(time.time()), job_id),
            )
            await conn.commit()
        except Exception:  # noqa: BLE001 - the reaper is the fallback
            logger.exception("bot_jobs: could not record the cancellation of job %s", job_id)
        raise
    except asyncio.TimeoutError:
        logger.error("bot_jobs: job %s (%s) timed out after %ss", job_id, kind, JOB_TIMEOUT_SECONDS)
        await conn.execute(
            "UPDATE bot_jobs SET status = 'failed', error = ?, finished_at = ? WHERE id = ?",
            ("timeout", int(time.time()), job_id),
        )
    except Exception as exc:
        logger.exception("bot_jobs: job %s (%s) failed", job_id, kind)
        await conn.execute(
            "UPDATE bot_jobs SET status = 'failed', error = ?, finished_at = ? WHERE id = ?",
            (str(exc)[:2000], int(time.time()), job_id),
        )
    await conn.commit()


@register_job("settings.reload")
async def _handle_settings_reload(payload: dict[str, Any]) -> dict[str, Any]:
    """Force the bot's TTL-cached ``webapp_admin_settings`` read to refetch."""
    invalidate_settings_cache()
    return {"ok": True}


async def reap_stale_jobs(
    conn: aiosqlite.Connection, *, older_than: int = STALE_JOB_SECONDS
) -> int:
    """Fail ``running`` rows started more than ``older_than`` seconds ago.

    ``run_claimed_job`` bounds every handler by ``JOB_TIMEOUT_SECONDS``, so a
    row still ``running`` after that was claimed by a process that died. Rows
    with no ``started_at`` cannot belong to a live claim either.
    """
    now = int(time.time())
    cursor = await conn.execute(
        "UPDATE bot_jobs SET status = 'failed', error = 'stale: worker died', finished_at = ? "
        "WHERE status = 'running' AND (started_at IS NULL OR started_at < ?)",
        (now, now - int(older_than)),
    )
    await conn.commit()
    return cursor.rowcount or 0


async def bot_jobs_loop(*, connect=connect, poll_seconds: float | None = None) -> None:
    """Poll ``bot_jobs`` every ``POLL_SECONDS`` and run at most one job per tick."""
    logger.info("bot_jobs_loop ishga tushdi")
    last_reap: float | None = None
    while True:
        try:
            async with connect() as conn:
                now = time.monotonic()
                if last_reap is None or now - last_reap >= REAP_INTERVAL_SECONDS:
                    last_reap = now
                    reaped = await reap_stale_jobs(conn)
                    if reaped:
                        logger.warning("bot_jobs: %s stale running job(s) marked failed", reaped)
                row = await claim_next_job(conn)
                if row is not None:
                    await run_claimed_job(conn, row)
        except Exception:
            logger.exception("bot_jobs_loop xato")
        await asyncio.sleep(POLL_SECONDS if poll_seconds is None else poll_seconds)
