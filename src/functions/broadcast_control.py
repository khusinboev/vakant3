"""Broadcast state transitions shared by the bot admin panel and the API.

The worker (``broadcast_worker.run_broadcast``) re-reads ``broadcasts.status``
at every batch boundary: ``paused`` makes it stop without finishing the job,
``cancelled`` finishes it, ``queued`` lets the picker take it again. So pausing,
resuming and cancelling are pure status changes, done here as one conditional
UPDATE each so two admins (or the bot and the panel) cannot race into an
invalid state.

The caller owns the transaction: it writes its audit row and commits.
"""

from __future__ import annotations

import time

#: action -> (statuses it may start from, status it sets)
TRANSITIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "pause": (("queued", "running"), "paused"),
    "resume": (("paused",), "queued"),
    "cancel": (("draft", "queued", "running", "paused"), "cancelled"),
}


async def set_broadcast_state(conn, broadcast_id: int, action: str) -> tuple[str, str] | None:
    """Apply ``action`` (pause | resume | cancel) to one broadcast.

    Returns ``(old_status, new_status)``, or ``None`` when the broadcast does
    not exist or its current status does not allow the action. Does not commit.
    """
    if action not in TRANSITIONS:
        raise ValueError(f"unknown broadcast action: {action!r}")
    allowed, new_status = TRANSITIONS[action]

    cursor = await conn.execute("SELECT status FROM broadcasts WHERE id = ?", (broadcast_id,))
    row = await cursor.fetchone()
    if row is None or row[0] not in allowed:
        return None
    old_status = row[0]

    finished_at = int(time.time()) if new_status == "cancelled" else None
    placeholders = ",".join("?" for _ in allowed)
    cursor = await conn.execute(
        f"UPDATE broadcasts SET status = ?, finished_at = COALESCE(?, finished_at) "
        f"WHERE id = ? AND status IN ({placeholders})",
        (new_status, finished_at, broadcast_id, *allowed),
    )
    if cursor.rowcount != 1:  # someone else moved it between the read and the write
        return None
    return old_status, new_status
