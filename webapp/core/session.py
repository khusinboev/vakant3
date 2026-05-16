import time
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from jose import jws

from webapp.core.config import get_settings
from webapp.core.database import get_db


AUTH_ERROR = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def sign_session_payload(payload: dict[str, Any]) -> str:
    settings = get_settings()
    return jws.sign(payload, settings.WEBAPP_SECRET, algorithm="HS256")


def decode_session_token(session_token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jws.verify(session_token, settings.WEBAPP_SECRET, algorithms=["HS256"])
    except Exception as exc:
        raise AUTH_ERROR from exc

    if not isinstance(payload, dict):
        raise AUTH_ERROR

    exp = int(payload.get("exp", 0))
    if exp <= int(time.time()):
        raise AUTH_ERROR

    return payload


async def get_current_user(
    authorization: str | None = Header(default=None),
    db=Depends(get_db),
) -> dict[str, Any]:
    current = await get_optional_current_user(authorization=authorization, db=db)
    if not current:
        raise AUTH_ERROR
    return current


async def get_optional_current_user(
    authorization: str | None = Header(default=None),
    db=Depends(get_db),
) -> dict[str, Any] | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_session_token(token)
    except HTTPException:
        return None

    sid = str(payload.get("sid", "")).strip()
    user_id = int(payload.get("uid", 0))
    if not sid or not user_id:
        return None

    now = int(time.time())
    cursor = await db.execute(
        "SELECT user_id, expires_at FROM webapp_sessions WHERE token = ?",
        (sid,),
    )
    session_row = await cursor.fetchone()
    if not session_row:
        return None

    if int(session_row["expires_at"]) <= now:
        await db.execute("DELETE FROM webapp_sessions WHERE token = ?", (sid,))
        await db.commit()
        return None

    cursor = await db.execute(
        "SELECT user_id, lang, first_name, username, photo_url, date, region, district, specs, money FROM users WHERE user_id = ?",
        (user_id,),
    )
    user_row = await cursor.fetchone()
    if not user_row:
        return None

    return {
        "session_sid": sid,
        "user": dict(user_row),
    }
