"""``broadcast_targets.last_attempt_at`` — when the worker last tried this row.

Failed and blocked rows never get ``sent_at`` and the worker clears
``claimed_at`` on every result, so nothing recorded *when* a send failed: the
admin "last 20 errors" list could only order by ``rowid`` (insertion order)
and the health check had no per-row progress signal. The worker now stamps
``last_attempt_at`` on every result it writes (sent, failed, blocked, and a
transient failure going back to ``pending``).

Rows written before this migration keep NULL (unknown); readers fall back to
``rowid``. The partial index serves the admin error list
(``WHERE broadcast_id = ? AND status IN ('failed','blocked') ORDER BY
last_attempt_at DESC``).
"""

from src.db.migrate import add_column_if_missing

ID = "m019_broadcast_last_attempt"


async def apply(conn) -> None:
    cursor = await conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'broadcast_targets' LIMIT 1"
    )
    if await cursor.fetchone() is None:
        return  # m008 creates it; nothing to alter on a database without it
    await add_column_if_missing(conn, "broadcast_targets", "last_attempt_at", "INTEGER")
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_broadcast_targets_errors_recent "
        "ON broadcast_targets(broadcast_id, last_attempt_at) "
        "WHERE status IN ('failed', 'blocked')"
    )
