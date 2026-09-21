"""The single entry gate every user-facing endpoint sits behind.

Before this module the Mini App trusted whoever arrived with valid initData:
BotFather's Main App button, ``t.me/<bot>/app`` and ``?startapp=`` links all
open the app without ever pressing /start, so neither the "start the bot" step
nor the forced-subscription wall was actually enforced (docs/ADMIN_PANEL_PLAN.md
§1). ``require_entry`` moves all three checks to the server; the lock screen in
the Mini App is only a rendering of what the API already decided.

Order (first failure wins):

1. ``users.banned``      -> 403 ``USER_BANNED``
2. ``users.started_at``  -> 403 ``BOT_START_REQUIRED``
3. subscription          -> 403 ``SUBSCRIPTION_REQUIRED {channels}``
4. referral gate         -> 403 ``REFERRAL_LOCKED {count, required}``

Admins bypass every check so a misconfigured channel can never lock the panel
out of reach.
"""

import logging
from typing import Any

from fastapi import Depends, Request

from webapp.core import errors, subscription
from webapp.core.auth import current_user
from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.referral_gate import get_referral_gate_state

_log = logging.getLogger(__name__)

# Codes owned by this feature (errors.py belongs to the AUTH agent; api_error
# accepts any string, so they live here until they are merged upstream).
BOT_START_REQUIRED = "BOT_START_REQUIRED"
SUBSCRIPTION_REQUIRED = "SUBSCRIPTION_REQUIRED"
USER_BANNED = "USER_BANNED"

_ROLES = ("owner", "admin", "moderator", "viewer")


#: Cached once per process, and only after m006 ran — before that the set is
#: still growing and caching it would keep the gate disabled for ever.
_users_columns: set[str] | None = None


async def _table_columns(db, table: str) -> set[str]:
    cursor = await db.execute(f"PRAGMA table_info({table})")
    return {str(row[1]) for row in await cursor.fetchall()}


async def users_columns(db) -> set[str]:
    global _users_columns
    if _users_columns is None:
        columns = await _table_columns(db, "users")
        if "started_at" in columns:
            _users_columns = columns
        return columns
    return _users_columns


def reset_users_columns_cache() -> None:
    global _users_columns
    _users_columns = None


async def admin_role(db, user_id: int) -> str | None:
    """The actor's admin role, or None.

    Deliberately read-only and independent of ``webapp.core.auth``: the gate
    runs on every request of every user, and must not write rows or raise.
    ``ADMIN_IDS`` stays a fallback so a fresh database is never gate-locked.
    """
    user_id = int(user_id)
    try:
        cursor = await db.execute(
            "SELECT role, disabled FROM admins WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
    except Exception:
        row = None  # table not created yet
    else:
        if row is not None:
            if int(row["disabled"] or 0):
                return None  # an explicit revocation beats the env list
            role = str(row["role"] or "")
            return role if role in _ROLES else "viewer"
    return "owner" if user_id in get_settings().admin_ids_set else None


async def _user_flags(db, user_id: int) -> tuple[bool, bool]:
    """``(bot_started, banned)`` read straight from ``users``.

    ``started_at`` (m006) and ``banned`` (m009) may not exist yet — a missing
    column means "not enforced", never "everybody is locked out".
    """
    columns = await users_columns(db)
    wanted = [c for c in ("started_at", "banned") if c in columns]
    if not wanted:
        return True, False
    try:
        cursor = await db.execute(
            f"SELECT {', '.join(wanted)} FROM users WHERE user_id = ?", (int(user_id),)
        )
        row = await cursor.fetchone()
    except Exception as exc:  # schema changed under a cached column set
        _log.warning("entry gate: users flags unreadable (%s) — allowing", exc)
        reset_users_columns_cache()
        return True, False
    if row is None:
        return False, False
    data = dict(row)
    started = True if "started_at" not in data else data.get("started_at") is not None
    banned = bool(int(data.get("banned") or 0)) if "banned" in data else False
    return started, banned


async def evaluate_entry(db, user_id: int, *, force: bool = False) -> dict[str, Any]:
    """Everything ``GET /api/auth/gate`` reports, in one pass."""
    user_id = int(user_id)
    role = await admin_role(db, user_id)
    bot_started, banned = await _user_flags(db, user_id)

    if role is not None:
        # Admins skip the checks but still see their real state in the payload.
        return {
            "bot_started": bot_started,
            "subscribed": True,
            "banned": banned,
            "channels": [],
            "referral": {"enabled": False, "required": 0, "count": 0, "unlocked": True},
            "is_admin": True,
            "role": role,
        }

    verdict = {"ok": True, "missing": []}
    if bot_started and not banned:
        verdict = await subscription.check_subscription(db, user_id, force=force)

    referral = {"enabled": False, "required": 0, "count": 0, "unlocked": True}
    try:
        state = await get_referral_gate_state(db, user_id)
        referral = {
            "enabled": bool(state["enabled"]),
            "required": int(state["required"]),
            "count": int(state["current"]),
            "unlocked": bool(state["unlocked"]),
        }
    except Exception as exc:  # settings row missing on a fresh DB
        _log.warning("entry gate: referral state unavailable (%s)", exc)

    return {
        "bot_started": bool(bot_started),
        "subscribed": bool(verdict["ok"]),
        "banned": bool(banned),
        "channels": list(verdict["missing"]),
        "referral": referral,
        "is_admin": False,
        "role": None,
    }


def raise_for_state(state: dict[str, Any]) -> None:
    """Turn a gate state into the first failure's HTTPException."""
    if state.get("is_admin"):
        return
    if state.get("banned"):
        raise errors.api_error(403, USER_BANNED)
    if not state.get("bot_started"):
        raise errors.api_error(403, BOT_START_REQUIRED)
    if not state.get("subscribed"):
        raise errors.api_error(403, SUBSCRIPTION_REQUIRED, channels=state.get("channels") or [])
    referral = state.get("referral") or {}
    if not referral.get("unlocked", True):
        raise errors.api_error(
            403,
            errors.REFERRAL_LOCKED,
            count=int(referral.get("count") or 0),
            required=int(referral.get("required") or 0),
        )


_STATE_KEY = "_entry_gate_state"


async def require_entry(
    request: Request, user=Depends(current_user), db=Depends(get_db)
) -> dict[str, Any]:
    """Dependency: the authenticated user, allowed through the entry gate."""
    cached = getattr(request.state, _STATE_KEY, None)
    if cached is None:
        cached = await evaluate_entry(db, int(user["user_id"]))
        # Telegram verdicts and channel check marks are written by the gate.
        await db.commit()
        setattr(request.state, _STATE_KEY, cached)
    raise_for_state(cached)
    return user
