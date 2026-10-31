"""Audit rows for admin mutations made from the bot (``admin_audit_log``).

Plain-SQL twin of ``webapp/core/audit.py:log_admin_action`` (the bot must not
import the webapp package). It only issues the INSERT: the caller writes it in
the same transaction as the mutation and commits once, so a failed mutation
leaves no audit row and an audited mutation always has one.

Every payload carries ``source = "bot"`` so the panel's audit view can tell a
bot action from a panel action. Payloads are built by the handlers from known
fields (ids, counts, segments), never from credentials, and are capped in size.
"""

from __future__ import annotations

import json
import time
from typing import Any

#: Dotted action names written by the bot. Channel names match the API's
#: (``webapp/routers/admin_channels.py``) so one audit filter covers both.
ACTIONS: tuple[str, ...] = (
    "broadcast.create",
    "broadcast.test",
    "broadcast.queue",
    "broadcast.pause",
    "broadcast.resume",
    "broadcast.cancel",
    "channels.add",
    "channels.delete",
)

SOURCE = "bot"
_MAX_PAYLOAD_CHARS = 8000


async def log_bot_action(
    conn,
    *,
    actor_id: int,
    action: str,
    target_type: str | None = None,
    target_id: Any = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """INSERT one audit row with ``source = "bot"``. The caller commits."""
    if action not in ACTIONS:
        raise ValueError(f"unknown bot audit action: {action!r}")
    body = {**(payload or {}), "source": SOURCE}
    payload_json = json.dumps(body, ensure_ascii=False, default=str)
    if len(payload_json) > _MAX_PAYLOAD_CHARS:
        payload_json = json.dumps({"source": SOURCE, "_truncated": True})
    await conn.execute(
        "INSERT INTO admin_audit_log "
        "(actor_id, action, target_type, target_id, payload_json, ip, created_at) "
        "VALUES (?, ?, ?, ?, ?, NULL, ?)",
        (
            int(actor_id),
            action,
            target_type,
            None if target_id is None else str(target_id),
            payload_json,
            int(time.time()),
        ),
    )
