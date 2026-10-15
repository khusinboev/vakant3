"""Data retention: delete rows nobody reads any more.

Runs once at API startup and then hourly in a background task
(``webapp/main.py``). Every statement is guarded by a table-existence check so
a fresh database — or one where another process has not created its tables yet
— does not produce an hourly wall of warnings.
"""

import asyncio
import logging
import time

_log = logging.getLogger(__name__)

SESSION_GRACE_SECONDS = 0
IDEMPOTENCY_TTL_SECONDS = 7 * 24 * 60 * 60
SENT_NOTIFICATIONS_TTL_SECONDS = 60 * 24 * 60 * 60
VACANCY_CACHE_TTL_SECONDS = 24 * 60 * 60
RESUME_EVENTS_TTL_SECONDS = 90 * 24 * 60 * 60
AUDIT_LOG_TTL_SECONDS = 365 * 24 * 60 * 60
#: Finished ``bot_jobs`` rows are only read while the panel polls the job it
#: just created; a week is far past that.
BOT_JOBS_TTL_SECONDS = 7 * 24 * 60 * 60
#: ``auto_post_log`` backs the history tab, which pages six months back.
AUTO_POST_LOG_TTL_SECONDS = 180 * 24 * 60 * 60
#: m012: the admin "Errors" view is for recent incidents.
ERROR_LOG_TTL_SECONDS = 30 * 24 * 60 * 60
#: m008: one row per recipient per broadcast — the fastest-growing table. Kept
#: while the broadcast is live and for 30 days after it finished (the per-user
#: breakdown in the admin panel); the ``broadcasts`` row and its counters stay.
BROADCAST_TARGETS_TTL_SECONDS = 30 * 24 * 60 * 60
#: m006: a cache of getChatMember answers that is trusted for at most 10 min;
#: a row a day old is never read again (a returning user is re-checked anyway).
SUBSCRIPTION_CHECKS_TTL_SECONDS = 24 * 60 * 60

#: Rows per DELETE transaction. Each chunk commits on its own, so the SQLite
#: write lock (shared with the bot process) is held for milliseconds, not for
#: the whole backlog of a first run on a large database.
DELETE_CHUNK_ROWS = 5000

_FINISHED_BROADCAST_STATUSES = "('done', 'cancelled', 'failed')"


async def _existing_tables(db) -> set[str]:
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {row[0] for row in await cursor.fetchall()}


def _rules(now: int) -> list[tuple[str, tuple[str, ...], str, tuple]]:
    """``(table, other tables the condition reads, WHERE, params)``."""
    return [
        ("webapp_sessions", (), "expires_at <= ?", (now - SESSION_GRACE_SECONDS,)),
        ("bot_handoff_tokens", (), "expires_at <= ?", (now,)),
        ("resume_idempotency", (), "created_at < ?", (now - IDEMPOTENCY_TTL_SECONDS,)),
        ("sent_notifications", (), "sent_at < ?", (now - SENT_NOTIFICATIONS_TTL_SECONDS,)),
        ("vacancy_cache", (), "expires_at < ?", (now - VACANCY_CACHE_TTL_SECONDS,)),
        ("resume_events", (), "created_at < ?", (now - RESUME_EVENTS_TTL_SECONDS,)),
        # Created by the AUTH migration; absent on databases that predate it.
        ("admin_audit_log", (), "created_at < ?", (now - AUDIT_LOG_TTL_SECONDS,)),
        # m010. Only finished rows: a queued/running job is still live work.
        (
            "bot_jobs",
            (),
            "status IN ('done', 'failed') AND COALESCE(finished_at, created_at) < ?",
            (now - BOT_JOBS_TTL_SECONDS,),
        ),
        # m010.
        ("auto_post_log", (), "posted_at < ?", (now - AUTO_POST_LOG_TTL_SECONDS,)),
        # m012.
        ("error_log", (), "created_at < ?", (now - ERROR_LOG_TTL_SECONDS,)),
        # m008. Never a target of a broadcast that is still draft/queued/running/paused.
        (
            "broadcast_targets",
            ("broadcasts",),
            "broadcast_id IN (SELECT id FROM broadcasts WHERE status IN "
            f"{_FINISHED_BROADCAST_STATUSES} "
            "AND COALESCE(finished_at, started_at, created_at, 0) < ?)",
            (now - BROADCAST_TARGETS_TTL_SECONDS,),
        ),
        # m006.
        ("subscription_checks", (), "checked_at < ?", (now - SUBSCRIPTION_CHECKS_TTL_SECONDS,)),
    ]


async def _delete_chunked(db, table: str, where: str, params: tuple, chunk: int) -> int:
    """DELETE in ``chunk``-row transactions; returns the number of rows removed."""
    sql = f"DELETE FROM {table} WHERE rowid IN (SELECT rowid FROM {table} WHERE {where} LIMIT ?)"
    total = 0
    while True:
        cursor = await db.execute(sql, (*params, chunk))
        removed = int(cursor.rowcount or 0)
        await db.commit()
        total += removed
        if removed < chunk:
            return total
        # Let the request handlers (and the bot's writers) in between chunks.
        await asyncio.sleep(0)


async def purge_expired(db, *, chunk: int = DELETE_CHUNK_ROWS) -> dict[str, int]:
    """Delete rows nobody reads any more. Returns per-table deleted counts.

    Table names and conditions come from ``_rules`` only (never from input).
    """
    now = int(time.time())
    try:
        tables = await _existing_tables(db)
    except Exception as exc:
        _log.error("retention: cannot list tables: %s", exc)
        return {}

    deleted: dict[str, int] = {}
    for table, needs, where, params in _rules(now):
        if table not in tables or any(other not in tables for other in needs):
            continue
        try:
            deleted[table] = await _delete_chunked(db, table, where, params, max(1, int(chunk)))
        except Exception as exc:
            _log.warning("retention: skipping %s (%s)", table, exc)
            try:
                await db.rollback()
            except Exception as rollback_exc:  # pragma: no cover - connection gone
                _log.error("retention: rollback failed: %s", rollback_exc)
    return deleted


async def checkpoint_wal(db) -> bool:
    """Fold the WAL back into the database file and shrink it."""
    try:
        cursor = await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        row = await cursor.fetchone()
        if row is not None and int(row[0]) != 0:
            # 1 = the checkpoint was blocked by a reader; harmless, try again later.
            _log.info("wal checkpoint busy: %s", tuple(row))
            return False
        return True
    except Exception as exc:
        _log.warning("wal checkpoint failed: %s", exc)
        return False
