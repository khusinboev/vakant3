"""Forced-subscription checks for the API.

The bot checks channel membership on ``/start`` with aiogram; the API cannot
import the aiogram ``bot`` object (CLAUDE.md: bot -> webapp imports only), so it
talks to ``api.telegram.org`` over httpx and caches the verdict per user in
``subscription_checks``.

Policy (docs/ADMIN_PANEL_PLAN.md §1.2):

* one Telegram round trip per user per TTL — ``CACHE_TTL_OK`` (10 min) after a
  pass, ``CACHE_TTL_MISSING`` (60 s) after a fail, ``CACHE_TTL_DEGRADED`` (30 s)
  when Telegram itself was unreachable;
* **fail-open**: a 5xx, a timeout or a network error never locks anybody out;
* a channel where the bot is not an administrator is skipped, not counted as a
  failed subscription — a misconfigured channel must not wall off the app;
* the verdict is the AND over every enabled channel.

The table has no TTL column (its shape is fixed by the contract), so a degraded
verdict is stored with a back-dated ``checked_at``: the row then ages out after
``CACHE_TTL_DEGRADED`` seconds under the same read rule.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx

from src.functions.functions import channel_row_target
from webapp.core.config import get_settings

_log = logging.getLogger(__name__)

CACHE_TTL_OK = 600
CACHE_TTL_MISSING = 60
CACHE_TTL_DEGRADED = 30

TELEGRAM_TIMEOUT = 8.0
TELEGRAM_API = "https://api.telegram.org"

#: Telegram member statuses that count as "subscribed".
SUBSCRIBED_STATUSES = frozenset({"member", "administrator", "creator"})
ADMIN_STATUSES = frozenset({"administrator", "creator"})

#: Descriptions meaning "the bot cannot see this chat's members" -> skip it.
_BOT_NO_ACCESS_MARKERS = (
    "chat not found",
    "member list is inaccessible",
    "bot is not a member",
    "chat_admin_required",
    "not enough rights",
    "channel_private",
    "bot was kicked",
    "forbidden",
)


def _now() -> int:
    """Indirection so tests can move the clock without touching ``time``."""
    return int(time.time())


class TelegramResponse:
    """Outcome of one Bot API call, split into the three cases we act on."""

    __slots__ = ("ok", "result", "status", "description", "transient")

    def __init__(
        self,
        ok: bool,
        result: Any = None,
        status: int = 0,
        description: str = "",
        transient: bool = False,
    ) -> None:
        self.ok = ok
        self.result = result
        self.status = status
        self.description = description
        self.transient = transient

    @property
    def bot_has_no_access(self) -> bool:
        text = (self.description or "").lower()
        return any(marker in text for marker in _BOT_NO_ACCESS_MARKERS)


async def _request(method: str, params: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
    """Raw httpx call — the single seam tests monkeypatch.

    Returns ``(status_code, json_body)``; ``(0, None)`` for a transport error.
    """
    token = get_settings().TOKEN
    if not token:
        return 0, None
    url = f"{TELEGRAM_API}/bot{token}/{method}"
    try:
        async with httpx.AsyncClient(timeout=TELEGRAM_TIMEOUT) as client:
            response = await client.get(url, params=params)
    except httpx.HTTPError as exc:  # timeout, DNS, connection reset…
        _log.warning("telegram %s transport error: %s", method, exc)
        return 0, None
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


async def call_telegram(method: str, params: dict[str, Any]) -> TelegramResponse:
    status, body = await _request(method, params)
    if status == 0 or status >= 500:
        return TelegramResponse(False, status=status, transient=True, description="upstream_error")
    if not isinstance(body, dict):
        return TelegramResponse(False, status=status, transient=True, description="bad_response")
    if body.get("ok"):
        return TelegramResponse(True, result=body.get("result"), status=status)
    return TelegramResponse(
        False,
        status=status,
        description=str(body.get("description") or ""),
    )


# --------------------------------------------------------------------------
# Bot identity
# --------------------------------------------------------------------------

_bot_id_cache: tuple[int, int] | None = None  # (bot_id, fetched_at)
_BOT_ID_TTL = 3600
_bot_id_lock = asyncio.Lock()


async def get_bot_id() -> int | None:
    """``getMe().id``, cached for an hour (it never changes for a token)."""
    global _bot_id_cache
    cached = _bot_id_cache
    if cached and _now() - cached[1] < _BOT_ID_TTL:
        return cached[0]
    async with _bot_id_lock:
        cached = _bot_id_cache
        if cached and _now() - cached[1] < _BOT_ID_TTL:
            return cached[0]
        response = await call_telegram("getMe", {})
        if not response.ok or not isinstance(response.result, dict):
            return None
        try:
            bot_id = int(response.result["id"])
        except (KeyError, TypeError, ValueError):
            return None
        _bot_id_cache = (bot_id, _now())
        return bot_id


def reset_bot_id_cache() -> None:
    global _bot_id_cache
    _bot_id_cache = None


# --------------------------------------------------------------------------
# Channels
# --------------------------------------------------------------------------


def channel_public(row) -> dict[str, Any]:
    """The subset of a ``channels`` row the Mini App is allowed to see."""
    data = dict(row)
    invite = data.get("invite_link")
    username = data.get("username")
    if not invite and username:
        invite = f"https://t.me/{str(username).lstrip('@')}"
    if not invite:
        raw_id = str(data.get("id") or "")
        if raw_id.startswith("@"):
            invite = f"https://t.me/{raw_id[1:]}"
    return {
        "id": str(data.get("id") or ""),
        "title": data.get("title") or (str(data.get("id") or "").lstrip("@") or None),
        "username": username,
        "invite_link": invite,
    }


async def load_enabled_channels(db) -> list[dict[str, Any]]:
    cursor = await db.execute(
        "SELECT id, chat_id, title, username, invite_link, enabled, "
        "last_check_ok, last_check_at FROM channels WHERE enabled = 1 ORDER BY rowid"
    )
    return [dict(row) for row in await cursor.fetchall()]


async def mark_channel_check(db, channel_id: str, ok: bool) -> None:
    await db.execute(
        "UPDATE channels SET last_check_ok = ?, last_check_at = ? WHERE id = ?",
        (int(ok), _now(), str(channel_id)),
    )


# --------------------------------------------------------------------------
# Per-user subscription verdict
# --------------------------------------------------------------------------


def _ttl_for(ok: bool) -> int:
    return CACHE_TTL_OK if ok else CACHE_TTL_MISSING


async def read_cached(db, user_id: int) -> dict[str, Any] | None:
    """The cached verdict when it is still fresh, else None."""
    cursor = await db.execute(
        "SELECT checked_at, ok, missing_json FROM subscription_checks WHERE user_id = ?",
        (int(user_id),),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    ok = bool(int(row["ok"] or 0))
    if _now() - int(row["checked_at"] or 0) >= _ttl_for(ok):
        return None
    try:
        missing = json.loads(row["missing_json"] or "[]")
    except (TypeError, ValueError):
        missing = []
    if not isinstance(missing, list):
        missing = []
    return {"ok": ok, "missing": missing, "cached": True}


async def store_verdict(
    db, user_id: int, ok: bool, missing: list[dict[str, Any]], ttl: int
) -> None:
    """Persist a verdict whose effective lifetime is ``ttl`` seconds.

    ``subscription_checks`` has no ttl column, so a shorter-than-normal TTL is
    expressed by back-dating ``checked_at`` (see the module docstring).
    """
    checked_at = _now() - max(0, _ttl_for(ok) - ttl)
    await db.execute(
        """
        INSERT INTO subscription_checks (user_id, checked_at, ok, missing_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            checked_at = excluded.checked_at,
            ok = excluded.ok,
            missing_json = excluded.missing_json
        """,
        (int(user_id), checked_at, int(ok), json.dumps(missing, ensure_ascii=False)),
    )


async def invalidate(db, user_id: int) -> None:
    await db.execute("DELETE FROM subscription_checks WHERE user_id = ?", (int(user_id),))


async def check_subscription(db, user_id: int, *, force: bool = False) -> dict[str, Any]:
    """``{"ok": bool, "missing": [channel_public…], "cached": bool}``.

    Never raises: any Telegram failure degrades to ``ok=True`` with a short TTL.
    The caller owns the transaction (``db.commit()``).
    """
    user_id = int(user_id)
    if force:
        await invalidate(db, user_id)
    else:
        cached = await read_cached(db, user_id)
        if cached is not None:
            return cached

    try:
        channels = await load_enabled_channels(db)
    except Exception as exc:  # table missing / migration not run yet
        _log.warning("subscription: channels unreadable (%s) — allowing", exc)
        return {"ok": True, "missing": [], "cached": False, "degraded": True}

    if not channels:
        await store_verdict(db, user_id, True, [], CACHE_TTL_OK)
        return {"ok": True, "missing": [], "cached": False}

    missing: list[dict[str, Any]] = []
    degraded = False

    for channel in channels:
        target = channel_row_target(channel)
        response = await call_telegram(
            "getChatMember", {"chat_id": target, "user_id": user_id}
        )

        if response.transient:
            # Telegram is down: do not hold this user hostage.
            degraded = True
            continue

        if not response.ok:
            if response.bot_has_no_access:
                _log.warning("subscription: bot has no access to %s — skipping", target)
                await mark_channel_check(db, channel["id"], False)
                continue
            # "user not found" & friends: the user is genuinely not a member.
            missing.append(channel_public(channel))
            continue

        await mark_channel_check(db, channel["id"], True)
        status = ""
        if isinstance(response.result, dict):
            status = str(response.result.get("status") or "")
        if status not in SUBSCRIBED_STATUSES:
            missing.append(channel_public(channel))

    ok = not missing
    ttl = CACHE_TTL_DEGRADED if degraded else _ttl_for(ok)
    await store_verdict(db, user_id, ok, missing, ttl)
    return {"ok": ok, "missing": missing, "cached": False, "degraded": degraded}
