"""Unified authentication for every API router.

Two mechanisms are supported, in this order:

1. ``Authorization: Bearer <session_token>`` — a JWS over a ``webapp_sessions`` row.
2. ``X-Telegram-Init-Data`` — Telegram Mini App initData, HMAC-verified on every request.

The resolved user is cached on ``request.state`` so several dependencies
(``current_user``, ``get_lang``, ``require_admin``) cost a single lookup.

Admin routes are the exception: ``require_admin`` accepts mechanism 1 only.
Roles come from the ``admins`` table; ``ADMIN_IDS`` merely bootstraps the first
owner.
"""

import time
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


def _remember_identity(request: Request, user_id: Any) -> None:
    """Publish the VERIFIED user id on ``request.state`` for the rate limiter.

    ``webapp.core.limiter`` keys buckets on this when it is set, and only ever
    on a verified identity otherwise — see that module's docstring. It is
    written here, after authentication succeeded, and nowhere else.
    """
    try:
        request.state.user_id = int(user_id)
    except (TypeError, ValueError, AttributeError):  # pragma: no cover
        pass


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
        _remember_identity(request, row["user_id"])
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
        _remember_identity(request, user_id)
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


# --------------------------------------------------------------------------
# Admin roles
# --------------------------------------------------------------------------

#: Ordered from least to most privileged; ``require_role`` compares by index.
ROLES: tuple[str, ...] = ("owner", "admin", "moderator", "viewer")

_ROLE_RANK: dict[str, int] = {"viewer": 0, "moderator": 1, "admin": 2, "owner": 3}


def role_rank(role: str) -> int:
    return _ROLE_RANK.get(str(role or ""), -1)


async def _admins_table_exists(db) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'admins' LIMIT 1"
    )
    return await cursor.fetchone() is not None


async def has_enabled_owner(db) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM admins WHERE role = 'owner' AND disabled = 0 LIMIT 1"
    )
    return await cursor.fetchone() is not None


async def resolve_admin_role(db, user_id: int) -> str | None:
    """The actor's role, or None when they are not an admin.

    ``ADMIN_IDS`` is bootstrap only: as long as the table holds no enabled
    owner, every id in the env list is treated as ``owner`` and inserted
    lazily on first use. Once an owner exists the table is the sole source of
    truth, so removing someone from the panel actually revokes them even if
    the server .env still lists their id.
    """
    user_id = int(user_id)
    if not await _admins_table_exists(db):
        # Migrations have not run yet — fall back to the env list.
        return "owner" if user_id in get_settings().admin_ids_set else None

    cursor = await db.execute(
        "SELECT role, disabled FROM admins WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    if row is not None:
        if int(row["disabled"] or 0):
            return None  # explicit revocation always wins over the env list
        role = str(row["role"] or "")
        return role if role in ROLES else "viewer"

    if user_id in get_settings().admin_ids_set and not await has_enabled_owner(db):
        await db.execute(
            "INSERT OR IGNORE INTO admins (user_id, role, added_by, added_at, disabled) "
            "VALUES (?, 'owner', NULL, ?, 0)",
            (user_id, int(time.time())),
        )
        await db.commit()
        return "owner"
    return None


async def require_admin(request: Request, db=Depends(get_db)) -> dict[str, Any]:
    """Dependency: an admin actor, identified by a Bearer session only.

    Admin routes deliberately refuse ``X-Telegram-Init-Data``: initData is
    replayable for its whole validity window and is accepted anonymously by
    every other route, so admin actions require the session the Mini App
    obtained through ``/auth/launch``.

    Returns ``{"user_id": int, "role": str, "user": {...}}``.
    """
    authorization = request.headers.get("authorization") or ""
    if not authorization.startswith("Bearer "):
        raise errors.api_error(401, errors.AUTH_REQUIRED)

    user = await current_user(request, db)
    role = await resolve_admin_role(db, int(user["user_id"]))
    if role is None:
        raise errors.api_error(403, errors.ADMIN_REQUIRED)
    return {"user_id": int(user["user_id"]), "role": role, "user": user}


def require_role(min_role: str):
    """Dependency factory: an admin actor whose role is at least ``min_role``."""
    if min_role not in _ROLE_RANK:
        raise ValueError(f"unknown role: {min_role}")

    async def dependency(request: Request, db=Depends(get_db)) -> dict[str, Any]:
        actor = await require_admin(request, db)
        if role_rank(actor["role"]) < _ROLE_RANK[min_role]:
            raise errors.api_error(403, errors.ADMIN_REQUIRED, required_role=min_role)
        return actor

    dependency.__name__ = f"require_role_{min_role}"
    # Marker for tests/tooling that walk the dependency tree of admin routes.
    dependency.__require_role__ = min_role  # type: ignore[attr-defined]
    return dependency
