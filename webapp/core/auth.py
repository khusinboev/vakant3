"""Unified authentication for every API router.

Two mechanisms are supported, in this order:

1. ``Authorization: Bearer <session_token>`` — a JWS over a ``webapp_sessions`` row.
2. ``X-Telegram-Init-Data`` — Telegram Mini App initData, HMAC-verified on every request.

The resolved user is cached on ``request.state`` so several dependencies
(``current_user``, ``get_lang``, ``require_admin``) cost a single lookup.
"""

from typing import Any

from fastapi import Depends, Request

from webapp.core import errors
from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.i18n import normalize_lang
from webapp.core.session import decode_session_token, load_session_user
from webapp.core.telegram_auth import verify_webapp_init_data
from webapp.core.users import ensure_user

_STATE_KEY = "_auth_resolution"


def _user_payload(row: dict[str, Any], session_sid: str | None) -> dict[str, Any]:
    data = dict(row)
    data["user_id"] = int(data["user_id"])
    data["lang"] = normalize_lang(data.get("lang"))
    data["is_pro"] = bool(int(data.get("user_pro") or 0))
    data["session_sid"] = session_sid
    return data


async def _resolve(request: Request, db) -> tuple[dict[str, Any] | None, str | None]:
    """Return ``(user, error_code)``. Both are None for an anonymous request."""
    authorization = request.headers.get("authorization") or ""
    if authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            payload = decode_session_token(token)
        except ValueError:
            return None, errors.SESSION_EXPIRED
        sid = str(payload.get("sid") or "").strip()
        if not sid:
            return None, errors.SESSION_EXPIRED
        row = await load_session_user(db, sid)
        if not row:
            return None, errors.SESSION_EXPIRED
        return _user_payload(row, sid), None

    init_data = (request.headers.get("x-telegram-init-data") or "").strip()
    if init_data:
        settings = get_settings()
        if not settings.TOKEN:
            return None, errors.SERVER_MISCONFIGURED
        tg_user = verify_webapp_init_data(init_data, settings.TOKEN)
        if not tg_user or not tg_user.get("id"):
            return None, errors.INVALID_INIT_DATA
        try:
            user_id = int(tg_user["id"])
        except (TypeError, ValueError):
            return None, errors.INVALID_INIT_DATA
        row = await ensure_user(
            db,
            user_id,
            lang=normalize_lang(tg_user.get("language_code")),
            first_name=tg_user.get("first_name"),
            username=tg_user.get("username"),
            photo_url=tg_user.get("photo_url"),
        )
        if not row:
            return None, errors.AUTH_REQUIRED
        return _user_payload(row, None), None

    return None, None


async def resolve_optional_user(request: Request, db) -> dict[str, Any] | None:
    """Plain helper (not a dependency) — resolves and caches the user for this request."""
    cached = getattr(request.state, _STATE_KEY, None)
    if cached is None:
        cached = await _resolve(request, db)
        setattr(request.state, _STATE_KEY, cached)
    return cached[0]


async def optional_user(request: Request, db=Depends(get_db)) -> dict[str, Any] | None:
    """Dependency: the authenticated user, or None for anonymous/invalid credentials."""
    return await resolve_optional_user(request, db)


async def current_user(request: Request, db=Depends(get_db)) -> dict[str, Any]:
    """Dependency: the authenticated user, or 401 with a machine-readable code."""
    cached = getattr(request.state, _STATE_KEY, None)
    if cached is None:
        cached = await _resolve(request, db)
        setattr(request.state, _STATE_KEY, cached)
    user, code = cached
    if user:
        return user
    if code == errors.SERVER_MISCONFIGURED:
        raise errors.api_error(500, errors.SERVER_MISCONFIGURED)
    raise errors.api_error(401, code or errors.AUTH_REQUIRED)


async def require_admin(user=Depends(current_user)) -> dict[str, Any]:
    """Dependency: the authenticated user, who must be listed in ADMIN_IDS."""
    settings = get_settings()
    if int(user["user_id"]) not in settings.admin_ids_set:
        raise errors.api_error(403, errors.ADMIN_REQUIRED)
    return user
