from typing import Any

from fastapi import Header, HTTPException, Request, status

from webapp.core.config import get_settings
from webapp.core.session import resolve_session_user_id
from webapp.core.telegram_auth import verify_webapp_init_data


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    return token or None


def resolve_user_id_from_init_data(init_data: str, bot_token: str) -> int | None:
    user_data = verify_webapp_init_data(init_data, bot_token)
    if not user_data or not user_data.get("id"):
        return None
    try:
        return int(user_data["id"])
    except (TypeError, ValueError):
        return None


def get_init_data_from_header(x_telegram_init_data: str | None = Header(default=None)) -> str:
    return (x_telegram_init_data or "").strip()


def get_init_data_from_request(request: Request) -> str:
    return (request.headers.get("X-Telegram-Init-Data") or "").strip()


def resolve_user_id_from_request_init_data(request: Request) -> int | None:
    settings = get_settings()
    if not settings.TOKEN:
        return None

    init_data = get_init_data_from_request(request)
    if not init_data:
        return None

    return resolve_user_id_from_init_data(init_data, settings.TOKEN)


def require_user_id_from_request_init_data(request: Request) -> int:
    user_id = resolve_user_id_from_request_init_data(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing initData")
    return user_id


def require_admin_user_id_from_request_init_data(request: Request) -> int:
    settings = get_settings()
    user_id = require_user_id_from_request_init_data(request)
    if user_id not in settings.admin_ids_set:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return user_id


async def resolve_request_user_id(
    request: Request,
    db,
    authorization: str | None = None,
) -> int | None:
    session_user_id = await resolve_session_user_id(authorization=authorization, db=db)
    if session_user_id:
        return session_user_id
    return resolve_user_id_from_request_init_data(request)


async def require_request_user_id(
    request: Request,
    db,
    authorization: str | None = None,
) -> int:
    user_id = await resolve_request_user_id(request=request, db=db, authorization=authorization)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return user_id
