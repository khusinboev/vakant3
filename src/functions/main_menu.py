"""Sending the persistent main reply keyboard, and keeping its links fresh.

The keyboard's Mini App buttons carry a per-user signed ``bt`` login link that
is valid for 7 days (``BOT_LINK_TTL_SECONDS``). Telegram keeps a reply keyboard
on the client until it is replaced, so a stale one would open the app with a
dead link. The bot therefore re-sends it:

* on every /start, /lang change and subscription check (``send_main_menu``);
* on the next text interaction the user has with the bot once the keyboard is
  older than ``REFRESH_AFTER_SECONDS`` (6 days) or was never sent with signed
  links (``users.kb_sent_at`` NULL, migration m022): ``refresh_if_stale``.

Cost of the check: one indexed single-row read per laws/HR tap. A user who only
ever taps the app buttons and never writes to the bot is not reached (the bot
does not push keyboards unprompted); /start fixes that.
"""
from __future__ import annotations

import logging
import time

from aiogram.types import Message

from src.buttons.buttuns import main_menu_kb
from src.db.connection import connect
from src.filters.admin import current_admin_role
from src.functions.webapp_link import BOT_LINK_TTL_SECONDS
from src.i18n import DEFAULT_LANG, t

logger = logging.getLogger(__name__)

#: One day of margin before the 7-day link dies.
REFRESH_AFTER_SECONDS = BOT_LINK_TTL_SECONDS - 86_400


async def _mark_sent(user_id: int) -> None:
    try:
        async with connect() as conn:
            await conn.execute(
                "UPDATE users SET kb_sent_at = ? WHERE user_id = ?", (int(time.time()), int(user_id))
            )
            await conn.commit()
    except Exception as exc:  # column missing on an unmigrated DB: not fatal
        logger.warning("kb_sent_at not written user_id=%s: %s", user_id, exc)


async def send_main_menu(
    message: Message, user_id: int, lang: str, text: str, *, admin_role: str | None = None
) -> Message:
    """Send ``text`` carrying the main keyboard for ``user_id`` and stamp it."""
    role = admin_role if admin_role is not None else await current_admin_role(user_id)
    sent = await message.answer(text, reply_markup=main_menu_kb(lang, user_id, role))
    await _mark_sent(user_id)
    return sent


async def keyboard_is_stale(user_id: int, now: float | None = None) -> bool:
    try:
        async with connect() as conn:
            cursor = await conn.execute("SELECT kb_sent_at FROM users WHERE user_id = ?", (int(user_id),))
            row = await cursor.fetchone()
    except Exception as exc:
        logger.warning("kb_sent_at not read user_id=%s: %s", user_id, exc)
        return False
    if row is None:
        return False
    sent_at = row[0]
    if sent_at is None:
        return True
    return (time.time() if now is None else now) - int(sent_at) >= REFRESH_AFTER_SECONDS


async def refresh_if_stale(message: Message, user_id: int, lang: str = DEFAULT_LANG) -> bool:
    """Re-send the keyboard when its login links are old. True when it was sent."""
    if not await keyboard_is_stale(user_id):
        return False
    await send_main_menu(message, user_id, lang, t(lang, "menu.refreshed"))
    return True
