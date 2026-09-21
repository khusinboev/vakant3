"""Data retention: delete rows nobody reads any more.

Runs once at API startup and then hourly in a background task
(``webapp/main.py``). Every statement is guarded by a table-existence check so
a fresh database — or one where another process has not created its tables yet
— does not produce an hourly wall of warnings.
"""

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


async def _existing_tables(db) -> set[str]:
    cursor = await db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {row[0] for row in await cursor.fetchall()}


async def purge_expired(db) -> dict[str, int]:
    """Delete rows nobody reads any more. Returns per-table deleted counts."""
    now = int(time.time())
    statements = [
        ("webapp_sessions", "DELETE FROM webapp_sessions WHERE expires_at <= ?", (now - SESSION_GRACE_SECONDS,)),
        ("bot_handoff_tokens", "DELETE FROM bot_handoff_tokens WHERE expires_at <= ?", (now,)),
        (
            "resume_idempotency",
            "DELETE FROM resume_idempotency WHERE created_at < ?",
            (now - IDEMPOTENCY_TTL_SECONDS,),
        ),
        (
            "sent_notifications",
            "DELETE FROM sent_notifications WHERE sent_at < ?",
            (now - SENT_NOTIFICATIONS_TTL_SECONDS,),
        ),
        (
            "vacancy_cache",
            "DELETE FROM vacancy_cache WHERE expires_at < ?",
            (now - VACANCY_CACHE_TTL_SECONDS,),
        ),
        (
            "resume_events",
            "DELETE FROM resume_events WHERE created_at < ?",
            (now - RESUME_EVENTS_TTL_SECONDS,),
        ),
        # Created by the AUTH migration; absent on databases that predate it.
        (
            "admin_audit_log",
            "DELETE FROM admin_audit_log WHERE created_at < ?",
            (now - AUDIT_LOG_TTL_SECONDS,),
        ),
        # m010. Only finished rows: a queued/running job is still live work.
        (
            "bot_jobs",
            "DELETE FROM bot_jobs WHERE status IN ('done', 'failed') "
            "AND COALESCE(finished_at, created_at) < ?",
            (now - BOT_JOBS_TTL_SECONDS,),
        ),
        # m010.
        (
            "auto_post_log",
            "DELETE FROM auto_post_log WHERE posted_at < ?",
            (now - AUTO_POST_LOG_TTL_SECONDS,),
        ),
    ]

    try:
        tables = await _existing_tables(db)
    except Exception as exc:
        _log.error("retention: cannot list tables: %s", exc)
        return {}

    deleted: dict[str, int] = {}
    for table, sql, params in statements:
        if table not in tables:
            continue
        try:
            cursor = await db.execute(sql, params)
            deleted[table] = int(cursor.rowcount or 0)
        except Exception as exc:
            _log.warning("retention: skipping %s (%s)", table, exc)
    try:
        await db.commit()
    except Exception as exc:
        _log.error("retention: commit failed: %s", exc)
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
