"""Forced-subscription channels, managed from the admin panel.

Until now channels existed only as a bare ``@NAME`` typed into the bot, with no
way to tell whether the bot was actually an administrator there — a channel the
bot had been removed from silently walled users off. Every channel added here is
resolved and validated against Telegram before it is stored (plan §6.2), and the
same rows are what the bot and ``webapp.core.subscription`` read.
"""

import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from src.functions.functions import parse_channel_link
from webapp.core import errors, subscription
from webapp.core.audit import client_ip, log_admin_action
from webapp.core.auth import require_role
from webapp.core.database import get_db
from webapp.core.limiter import limiter

router = APIRouter(prefix="/admin/channels", tags=["admin", "channels"])

CHANNEL_INVALID = "CHANNEL_INVALID"
CHANNEL_BOT_NOT_ADMIN = "CHANNEL_BOT_NOT_ADMIN"
CHANNEL_EXISTS = "CHANNEL_EXISTS"

#: Per-channel validation outcomes reported to the panel.
STATUS_OK = "ok"
STATUS_BOT_NOT_ADMIN = "bot_not_admin"
STATUS_NOT_FOUND = "not_found"
STATUS_UPSTREAM_ERROR = "upstream_error"


class ChannelCreateRequest(BaseModel):
    link: str
    # A private ``t.me/+hash`` invite cannot be resolved through the Bot API,
    # so the numeric id is required alongside it (see validate_target).
    chat_id: int | None = None


class ChannelPatchRequest(BaseModel):
    enabled: bool


def _row(row) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": str(data.get("id") or ""),
        "chat_id": data.get("chat_id"),
        "title": data.get("title"),
        "username": data.get("username"),
        "invite_link": data.get("invite_link"),
        "enabled": bool(int(data.get("enabled") or 0)),
        "added_by": data.get("added_by"),
        "added_at": data.get("added_at"),
        "last_check_ok": None if data.get("last_check_ok") is None else bool(int(data["last_check_ok"])),
        "last_check_at": data.get("last_check_at"),
    }


async def validate_target(target: str) -> dict[str, Any]:
    """Resolve ``target`` and report whether the bot can police it.

    Never raises: the caller decides whether a bad status is an error (adding a
    channel) or just a status line (re-checking one).
    """
    chat = await subscription.call_telegram("getChat", {"chat_id": target})
    if not chat.ok:
        if chat.transient:
            return {"status": STATUS_UPSTREAM_ERROR, "detail": chat.description}
        return {"status": STATUS_NOT_FOUND, "detail": chat.description}

    info = chat.result if isinstance(chat.result, dict) else {}
    resolved = {
        "chat_id": info.get("id"),
        "title": info.get("title") or info.get("username"),
        "username": info.get("username"),
        "invite_link": info.get("invite_link"),
    }

    bot_id = await subscription.get_bot_id()
    if bot_id is None:
        return {"status": STATUS_UPSTREAM_ERROR, "detail": "getMe failed", **resolved}

    member = await subscription.call_telegram(
        "getChatMember", {"chat_id": str(resolved["chat_id"] or target), "user_id": bot_id}
    )
    if not member.ok:
        if member.transient:
            return {"status": STATUS_UPSTREAM_ERROR, "detail": member.description, **resolved}
        return {"status": STATUS_BOT_NOT_ADMIN, "detail": member.description, **resolved}

    status = ""
    if isinstance(member.result, dict):
        status = str(member.result.get("status") or "")
    if status not in subscription.ADMIN_STATUSES:
        return {"status": STATUS_BOT_NOT_ADMIN, "detail": status, **resolved}

    if not resolved["invite_link"] and resolved["username"]:
        resolved["invite_link"] = f"https://t.me/{resolved['username']}"
    return {"status": STATUS_OK, **resolved}


@router.get("")
@limiter.limit("60/minute")
async def list_channels(
    request: Request, admin=Depends(require_role("viewer")), db=Depends(get_db)
) -> dict[str, Any]:
    cursor = await db.execute(
        "SELECT id, chat_id, title, username, invite_link, enabled, added_by, added_at, "
        "last_check_ok, last_check_at FROM channels ORDER BY rowid"
    )
    return {"items": [_row(row) for row in await cursor.fetchall()]}


@router.post("")
@limiter.limit("10/minute")
async def add_channel(
    request: Request,
    payload: ChannelCreateRequest,
    admin=Depends(require_role("admin")),
    db=Depends(get_db),
) -> dict[str, Any]:
    try:
        parsed = parse_channel_link(payload.link)
    except ValueError as exc:
        raise errors.api_error(400, CHANNEL_INVALID, reason=str(exc)) from None

    invite_link = parsed.invite_link
    target = parsed.target
    if parsed.kind == "invite":
        if payload.chat_id is None:
            # getChat does not accept invite links; the panel asks for the id.
            raise errors.api_error(400, CHANNEL_INVALID, reason="invite_link_requires_chat_id")
        target = str(payload.chat_id)

    result = await validate_target(target)
    if result["status"] == STATUS_UPSTREAM_ERROR:
        raise errors.api_error(502, errors.UPSTREAM_ERROR)
    if result["status"] == STATUS_NOT_FOUND:
        raise errors.api_error(400, CHANNEL_INVALID, reason="chat_not_found")
    if result["status"] == STATUS_BOT_NOT_ADMIN:
        raise errors.api_error(400, CHANNEL_BOT_NOT_ADMIN, title=result.get("title"))

    chat_id = result.get("chat_id")
    username = result.get("username")
    # Stable row id: the public @name when there is one, the numeric id otherwise.
    channel_id = f"@{username}" if username else str(chat_id)

    cursor = await db.execute(
        "SELECT id FROM channels WHERE id = ? OR (chat_id IS NOT NULL AND chat_id = ?)",
        (channel_id, chat_id),
    )
    existing = await cursor.fetchone()
    if existing is not None:
        raise errors.api_error(409, CHANNEL_EXISTS, id=str(existing["id"]))

    now = int(time.time())
    await db.execute(
        """
        INSERT INTO channels
            (id, title, username, invite_link, chat_id, enabled,
             added_by, added_at, last_check_ok, last_check_at)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?, 1, ?)
        """,
        (
            channel_id,
            result.get("title"),
            username,
            invite_link or result.get("invite_link"),
            chat_id,
            int(admin["user_id"]),
            now,
            now,
        ),
    )
    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="channels.add",
        target_type="channel",
        target_id=channel_id,
        payload={"link": payload.link, "chat_id": chat_id, "title": result.get("title")},
        ip=client_ip(request),
    )
    await db.commit()

    cursor = await db.execute(
        "SELECT id, chat_id, title, username, invite_link, enabled, added_by, added_at, "
        "last_check_ok, last_check_at FROM channels WHERE id = ?",
        (channel_id,),
    )
    row = await cursor.fetchone()
    return {"channel": _row(row), "status": STATUS_OK}


@router.patch("/{channel_id}")
@limiter.limit("10/minute")
async def patch_channel(
    request: Request,
    channel_id: str,
    payload: ChannelPatchRequest,
    admin=Depends(require_role("admin")),
    db=Depends(get_db),
) -> dict[str, Any]:
    cursor = await db.execute("SELECT id FROM channels WHERE id = ?", (channel_id,))
    if await cursor.fetchone() is None:
        raise errors.not_found("channel")

    await db.execute(
        "UPDATE channels SET enabled = ? WHERE id = ?", (int(payload.enabled), channel_id)
    )
    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="channels.update",
        target_type="channel",
        target_id=channel_id,
        payload={"enabled": payload.enabled},
        ip=client_ip(request),
    )
    await db.commit()
    return {"ok": True, "id": channel_id, "enabled": payload.enabled}


@router.delete("/{channel_id}")
@limiter.limit("10/minute")
async def delete_channel(
    request: Request,
    channel_id: str,
    admin=Depends(require_role("admin")),
    db=Depends(get_db),
) -> dict[str, Any]:
    cursor = await db.execute("SELECT id FROM channels WHERE id = ?", (channel_id,))
    if await cursor.fetchone() is None:
        raise errors.not_found("channel")

    await db.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
    # Cached verdicts were computed against the old channel set.
    await db.execute("DELETE FROM subscription_checks")
    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="channels.delete",
        target_type="channel",
        target_id=channel_id,
        ip=client_ip(request),
    )
    await db.commit()
    return {"ok": True, "id": channel_id}


@router.post("/{channel_id}/check")
@limiter.limit("10/minute")
async def check_channel(
    request: Request,
    channel_id: str,
    admin=Depends(require_role("admin")),
    db=Depends(get_db),
) -> dict[str, Any]:
    cursor = await db.execute(
        "SELECT id, chat_id, title, username, invite_link, enabled, added_by, added_at, "
        "last_check_ok, last_check_at FROM channels WHERE id = ?",
        (channel_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise errors.not_found("channel")

    data = dict(row)
    target = str(data["chat_id"]) if data.get("chat_id") is not None else str(data["id"])
    result = await validate_target(target)
    ok = result["status"] == STATUS_OK

    if result["status"] != STATUS_UPSTREAM_ERROR:
        await db.execute(
            "UPDATE channels SET last_check_ok = ?, last_check_at = ?, "
            "title = COALESCE(?, title), username = COALESCE(?, username), "
            "invite_link = COALESCE(?, invite_link), chat_id = COALESCE(?, chat_id) "
            "WHERE id = ?",
            (
                int(ok),
                int(time.time()),
                result.get("title"),
                result.get("username"),
                result.get("invite_link"),
                result.get("chat_id"),
                channel_id,
            ),
        )

    # Audited like every other admin action on this router: a re-check writes
    # ``last_check_ok``, which is what the entry gate reads, so "who re-checked
    # this channel, when, and what did Telegram say" has to be on the record.
    # The row is written even when the check could not reach Telegram — an
    # upstream error is exactly the case someone will want to trace later.
    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="channels.check",
        target_type="channel",
        target_id=channel_id,
        payload={"ok": ok, "status": result["status"]},
        ip=client_ip(request),
    )
    await db.commit()

    return {"id": channel_id, "ok": ok, "status": result["status"], "detail": result.get("detail")}
