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
    """
    placeholders = ",".join("?" for _ in PENDING_STATUSES)
    cursor = await conn.execute(
        f"SELECT id FROM bot_jobs WHERE kind = ? AND status IN ({placeholders}) "
        "ORDER BY id LIMIT 1",
        (kind, *PENDING_STATUSES),
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


async def bot_jobs_loop() -> None:
    """Poll ``bot_jobs`` every ``POLL_SECONDS`` and run at most one job per tick."""
    logger.info("bot_jobs_loop ishga tushdi")
    while True:
        try:
            async with connect() as conn:
                row = await claim_next_job(conn)
                if row is not None:
                    await run_claimed_job(conn, row)
        except Exception:
            logger.exception("bot_jobs_loop xato")
        await asyncio.sleep(POLL_SECONDS)
