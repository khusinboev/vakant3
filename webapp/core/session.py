"""Signed Mini App sessions backed by the ``webapp_sessions`` table.

The token payload is only a pointer: the session row is the identity.
``load_session_user`` returns the user of the row, never a user id taken
from the (client-held) token payload.
"""

import json
import time
from typing import Any

from jose import jws

from webapp.core.config import get_settings
from webapp.core.users import USER_COLUMNS


def sign_session_payload(payload: dict[str, Any]) -> str:
    settings = get_settings()
    return jws.sign(payload, settings.WEBAPP_SECRET, algorithm="HS256")


def decode_session_token(session_token: str) -> dict[str, Any]:
    """Verify the signature and expiry. Raises ValueError for anything invalid."""
    settings = get_settings()
    try:
        raw = jws.verify(session_token, settings.WEBAPP_SECRET, algorithms=["HS256"])
    except Exception as exc:
        raise ValueError("invalid session signature") from exc

    if isinstance(raw, (bytes, bytearray, str)):
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid session payload") from exc
    elif isinstance(raw, dict):
        payload = raw
    else:
        raise ValueError("invalid session payload")

    if not isinstance(payload, dict):
        raise ValueError("invalid session payload")

    try:
        exp = int(payload.get("exp", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid session expiry") from exc
    if exp <= int(time.time()):
        raise ValueError("session expired")

    return payload


async def load_session_user(db, sid: str) -> dict[str, Any] | None:
    """Resolve a session id to its user row, deleting the row once it expired."""
    cursor = await db.execute(
        "SELECT user_id, expires_at FROM webapp_sessions WHERE token = ?",
        (sid,),
    )
    session_row = await cursor.fetchone()
    if not session_row:
        return None

    if int(session_row["expires_at"]) <= int(time.time()):
        await db.execute("DELETE FROM webapp_sessions WHERE token = ?", (sid,))
        await db.commit()
        return None

    user_id = int(session_row["user_id"])
    cursor = await db.execute(
        f"SELECT {USER_COLUMNS} FROM users WHERE user_id = ?",
        (user_id,),
    )
    user_row = await cursor.fetchone()
    return dict(user_row) if user_row else None


async def create_session(db, user_id: int) -> tuple[str, int]:
    """Insert a session row and return ``(session_token, expires_at)``."""
    import secrets

    settings = get_settings()
    now = int(time.time())
    exp = now + settings.SESSION_TTL_SECONDS
    sid = secrets.token_urlsafe(32)
    await db.execute(
        "INSERT INTO webapp_sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (sid, int(user_id), now, exp),
    )
    return sign_session_payload({"sid": sid, "exp": exp}), exp
