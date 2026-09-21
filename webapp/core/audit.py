"""Append-only audit trail for admin mutations (``admin_audit_log``).

``log_admin_action`` only issues the INSERT — it never commits. Callers write
the audit row inside the same transaction as the mutation itself and commit
once, so a mutation that fails (or a request that dies before the commit)
leaves no orphan audit row, and an audited mutation can never be missing its
row. aiosqlite runs an implicit transaction per connection, so "same
transaction" simply means "before the caller's single ``await db.commit()``".

Payloads are scrubbed before they are stored: an audit log is read by more
people than the code that writes it, so no token, secret or raw credential may
ever reach it.
"""

import json
import time
from typing import Any

from starlette.requests import Request

from webapp.core.request_ip import client_ip as _resolve_client_ip

#: Dotted lowercase action names. Keep this list in sync with the routers.
ACTIONS = (
    "settings.patch",
    "wallet.add_balance",
    "wallet.reset_user",
    "admins.add",
    "admins.remove",
    "admins.role",
)

#: Substrings that mark a value as a credential; the value is replaced, never stored.
_SECRET_HINTS = (
    "token",
    "secret",
    "password",
    "passwd",
    "authorization",
    "auth_header",
    "init_data",
    "initdata",
    "api_key",
    "apikey",
    "signature",
    "hash",
)

_MAX_PAYLOAD_CHARS = 8000


def _is_secret_key(key: str) -> bool:
    lowered = str(key).lower()
    return any(hint in lowered for hint in _SECRET_HINTS)


def scrub(value: Any, _depth: int = 0) -> Any:
    """Recursively replace credential-looking values with ``"[redacted]"``."""
    if _depth > 6:
        return "[truncated]"
    if isinstance(value, dict):
        return {
            str(k): ("[redacted]" if _is_secret_key(k) else scrub(v, _depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [scrub(item, _depth + 1) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def client_ip(request: Request | None) -> str | None:
    """The caller's IP.

    Re-exported from :mod:`webapp.core.request_ip` so the many callers that
    already import it from here keep working; the resolution order (X-Real-IP,
    then the LAST X-Forwarded-For hop, then the socket peer) lives there. An
    audit row must never record an attacker-chosen address, which is exactly
    what reading the first forwarded hop used to allow.
    """
    return _resolve_client_ip(request)


async def log_admin_action(
    db,
    *,
    actor_id: int,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    payload: dict | None = None,
    ip: str | None = None,
) -> None:
    """INSERT one audit row. The caller commits (see the module docstring)."""
    payload_json: str | None = None
    if payload is not None:
        try:
            payload_json = json.dumps(scrub(payload), ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            payload_json = json.dumps({"_unserializable": True})
        if len(payload_json) > _MAX_PAYLOAD_CHARS:
            payload_json = payload_json[:_MAX_PAYLOAD_CHARS] + '..."[truncated]"'

    await db.execute(
        "INSERT INTO admin_audit_log "
        "(actor_id, action, target_type, target_id, payload_json, ip, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            int(actor_id),
            str(action),
            str(target_type) if target_type is not None else None,
            str(target_id) if target_id is not None else None,
            payload_json,
            str(ip)[:64] if ip else None,
            int(time.time()),
        ),
    )
