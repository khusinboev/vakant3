"""Per-target error kinds and retry state, plus a content-rejection counter.

``broadcast_targets`` gains:

* ``error_kind`` — what the worker made of the Telegram error (``blocked``,
  ``deactivated``, ``chat_not_found``, ``bad_request``, ``flood``,
  ``network``, ``other``; see ``broadcast_worker.classify_error``). ``error``
  keeps the short text.
* ``attempts`` — send attempts made for this recipient.
* ``next_attempt_at`` — a transient failure puts the row back to ``pending``
  with this epoch second; the worker does not claim it earlier.

``broadcasts.content_failed`` counts recipients whose send failed because of
the message itself (``bad_request``/``other``), so the early abort can be
decided from one row instead of scanning the targets after every batch.

Existing rows keep ``attempts = 0`` and NULL kind/next attempt, which is the
state of a row that was never retried.
"""

from src.db.migrate import add_column_if_missing

ID = "m017_broadcast_retry"


async def _has_table(conn, name: str) -> bool:
    cursor = await conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1", (name,)
    )
    return await cursor.fetchone() is not None


async def apply(conn) -> None:
    if await _has_table(conn, "broadcast_targets"):
        await add_column_if_missing(conn, "broadcast_targets", "error_kind", "TEXT")
        await add_column_if_missing(
            conn, "broadcast_targets", "attempts", "INTEGER NOT NULL DEFAULT 0"
        )
        await add_column_if_missing(conn, "broadcast_targets", "next_attempt_at", "INTEGER")
        # The picker asks "does this job have a pending row due now?"; retries
        # waiting for their time are the only rows with a non-NULL value.
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_broadcast_targets_next_attempt "
            "ON broadcast_targets(broadcast_id, next_attempt_at) WHERE status = 'pending'"
        )
    if await _has_table(conn, "broadcasts"):
        await add_column_if_missing(
            conn, "broadcasts", "content_failed", "INTEGER NOT NULL DEFAULT 0"
        )
