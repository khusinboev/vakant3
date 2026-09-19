"""Cheap data retention pass, run once at API startup."""

import logging
import time

_log = logging.getLogger(__name__)

SESSION_GRACE_SECONDS = 0
IDEMPOTENCY_TTL_SECONDS = 7 * 24 * 60 * 60
SENT_NOTIFICATIONS_TTL_SECONDS = 60 * 24 * 60 * 60
VACANCY_CACHE_TTL_SECONDS = 24 * 60 * 60


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
    ]

    deleted: dict[str, int] = {}
    for table, sql, params in statements:
        try:
            cursor = await db.execute(sql, params)
            deleted[table] = int(cursor.rowcount or 0)
        except Exception as exc:  # table may not exist yet on a fresh DB
            _log.warning("retention: skipping %s (%s)", table, exc)
    try:
        await db.commit()
    except Exception as exc:
        _log.error("retention: commit failed: %s", exc)
    return deleted
