import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.limiter import limiter
from webapp.core.session import get_current_user, sign_session_payload
from webapp.core.telegram_auth import verify_telegram_login
from webapp.models.schemas import AuthResponse, LogoutResponse, TelegramAuthRequest, UserProfile

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=AuthResponse)
@limiter.limit("10/minute")
async def telegram_login(request: Request, payload: TelegramAuthRequest, db=Depends(get_db)) -> AuthResponse:
    settings = get_settings()
    incoming = payload.model_dump()

    if not settings.TOKEN:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="TOKEN not configured")

    if not verify_telegram_login(incoming, settings.TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid telegram auth payload")

    now = int(time.time())

    await db.execute(
        """
        INSERT OR IGNORE INTO users (user_id, date, lang)
        VALUES (?, ?, ?)
        """,
        (payload.id, now, "uz"),
    )
    await db.execute(
        """
        UPDATE users
        SET first_name = ?, username = ?, photo_url = ?
        WHERE user_id = ?
        """,
        (payload.first_name, payload.username, payload.photo_url, payload.id),
    )

    sid = secrets.token_urlsafe(32)
    exp = now + settings.SESSION_TTL_SECONDS
    await db.execute(
        "INSERT INTO webapp_sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (sid, payload.id, now, exp),
    )
    await db.commit()

    session_token = sign_session_payload({"sid": sid, "uid": payload.id, "exp": exp})

    cursor = await db.execute(
        "SELECT user_id, first_name, username, photo_url, lang FROM users WHERE user_id = ?",
        (payload.id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User was not persisted")

    user = UserProfile(
        user_id=int(row["user_id"]),
        first_name=str(row["first_name"] or ""),
        username=row["username"],
        photo_url=row["photo_url"],
        lang=str(row["lang"] or "uz"),
    )
    return AuthResponse(session_token=session_token, user=user)


@router.post("/logout", response_model=LogoutResponse)
async def logout(current=Depends(get_current_user), db=Depends(get_db)) -> LogoutResponse:
    sid = current["session_sid"]
    await db.execute("DELETE FROM webapp_sessions WHERE token = ?", (sid,))
    await db.commit()
    return LogoutResponse(ok=True)


@router.get("/me", response_model=UserProfile)
async def me(current=Depends(get_current_user)) -> UserProfile:
    user = current["user"]
    return UserProfile(
        user_id=int(user["user_id"]),
        first_name=str(user.get("first_name") or ""),
        username=user.get("username"),
        photo_url=user.get("photo_url"),
        lang=str(user.get("lang") or "uz"),
    )


class HandoffRequest(BaseModel):
    token: str


@router.post("/handoff", response_model=AuthResponse)
async def handoff_login(payload: HandoffRequest, db=Depends(get_db)) -> AuthResponse:
    """Exchange a one-time bot-generated token for a full webapp session."""
    now = int(time.time())

    cursor = await db.execute(
        "SELECT user_id, used, expires_at FROM bot_handoff_tokens WHERE token = ?",
        (payload.token,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid handoff token")

    if int(row["used"]) or int(row["expires_at"]) <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Handoff token expired or already used")

    user_id = int(row["user_id"])

    # Mark as used immediately (one-time only)
    await db.execute("UPDATE bot_handoff_tokens SET used = 1 WHERE token = ?", (payload.token,))

    settings = get_settings()
    sid = secrets.token_urlsafe(32)
    exp = now + settings.SESSION_TTL_SECONDS
    await db.execute(
        "INSERT INTO webapp_sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (sid, user_id, now, exp),
    )
    await db.commit()

    session_token = sign_session_payload({"sid": sid, "uid": user_id, "exp": exp})

    cursor = await db.execute(
        "SELECT user_id, first_name, username, photo_url, lang FROM users WHERE user_id = ?",
        (user_id,),
    )
    user_row = await cursor.fetchone()
    if not user_row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return AuthResponse(
        session_token=session_token,
        user=UserProfile(
            user_id=int(user_row["user_id"]),
            first_name=str(user_row["first_name"] or ""),
            username=user_row["username"],
            photo_url=user_row["photo_url"],
            lang=str(user_row["lang"] or "uz"),
        ),
    )
