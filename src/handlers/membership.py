# ============================================
# src/handlers/membership.py - Aiogram 3.x
# Telegram membership updates: `my_chat_member` (bot blocked/unblocked in a
# private chat) and `chat_member` (a user joined/left a required channel).
# ============================================
import logging

from aiogram import Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.types import ChatMemberUpdated

from src.db.connection import connect

logger = logging.getLogger(__name__)

router = Router(name="membership")


def _status(member) -> str:
    """Plain status string of a ChatMember* object (enum or str)."""
    value = getattr(member, "status", None)
    return str(getattr(value, "value", value) or "")


def _is_member_flag(member) -> bool | None:
    """`is_member` exists only on ChatMemberRestricted; None for other statuses."""
    value = getattr(member, "is_member", None)
    return None if value is None else bool(value)


async def set_blocked(user_id: int, blocked: bool) -> bool:
    """Idempotent `users.blocked` write. True when a row actually changed.

    Never inserts: an unknown id is not a user of ours. Never raises.
    """
    try:
        async with connect() as conn:
            cursor = await conn.execute(
                "UPDATE users SET blocked = ? WHERE user_id = ? AND blocked IS NOT ?",
                (int(blocked), int(user_id), int(blocked)),
            )
            await conn.commit()
            return bool(cursor.rowcount)
    except Exception:
        logger.exception("membership: users.blocked write failed (user=%s)", user_id)
        return False


@router.my_chat_member()
async def on_my_chat_member(update: ChatMemberUpdated) -> None:
    """The bot's own status changed. Only PRIVATE chats say anything about a user.

    kicked -> the user blocked the bot (broadcasts/notifications skip them);
    member -> the user unblocked/restarted it. Groups and channels (bot added or
    removed) are ignored. Needs "my_chat_member" in allowed_updates, which
    `dp.resolve_used_update_types()` provides once this router is included.
    """
    try:
        if update.chat.type != ChatType.PRIVATE:
            return
        status = _status(update.new_chat_member)
        if status == ChatMemberStatus.KICKED.value:
            blocked = True
        elif status == ChatMemberStatus.MEMBER.value:
            blocked = False
        else:
            return
        changed = await set_blocked(update.chat.id, blocked)
        if changed:
            logger.info("membership: user %s blocked=%s", update.chat.id, int(blocked))
    except Exception:
        logger.exception("membership: my_chat_member handling failed")


async def is_required_channel(conn, update: ChatMemberUpdated) -> bool:
    """Is the update's chat one of the enabled (required) channels?

    Rows are matched the way they are stored: numeric `chat_id`, `id` as the
    numeric id or the pasted `@username`, or the `username` column.
    """
    chat_id = int(update.chat.id)
    username = (update.chat.username or "").lstrip("@").lower()
    cursor = await conn.execute(
        "SELECT 1 FROM channels WHERE enabled = 1 AND ("
        " chat_id = :chat_id OR id = CAST(:chat_id AS TEXT)"
        " OR (:username != '' AND (lower(ltrim(id, '@')) = :username OR lower(ltrim(COALESCE(username, ''), '@')) = :username))"
        ") LIMIT 1",
        {"chat_id": chat_id, "username": username},
    )
    return await cursor.fetchone() is not None


@router.chat_member()
async def on_chat_member(update: ChatMemberUpdated) -> None:
    """A user's membership in a chat changed.

    Telegram sends `chat_member` only when the bot is an administrator of the
    channel AND "chat_member" is in allowed_updates (included automatically via
    `dp.resolve_used_update_types()`). When the chat is a required channel, the
    user's cached verdict in `subscription_checks` is dropped so the entry gate
    re-asks Telegram on the next request instead of waiting for the TTL. The
    cache is keyed by user only (one verdict over all channels), so the whole
    row goes; an unknown user simply has no row.
    """
    try:
        old, new = update.old_chat_member, update.new_chat_member
        if _status(old) == _status(new) and _is_member_flag(old) == _is_member_flag(new):
            return  # e.g. an admin's permissions changed: subscription unchanged
        user_id = int(new.user.id)
        async with connect() as conn:
            if not await is_required_channel(conn, update):
                return
            await conn.execute("DELETE FROM subscription_checks WHERE user_id = ?", (user_id,))
            await conn.commit()
        logger.info("membership: dropped subscription cache of user %s (chat %s)", user_id, update.chat.id)
    except Exception:
        logger.exception("membership: chat_member handling failed")
