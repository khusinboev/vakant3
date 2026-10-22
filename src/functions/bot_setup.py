"""One-time bot UI setup at startup: chat menu button and command lists.

Every call is best effort: a failure is logged and never stops the bot.

* Menu button (the button left of the input field) opens the Mini App. It is a
  ``MenuButtonWebApp``, so the app gets initData like an inline web_app button.
  Its text is global (no per-language variant in the Bot API): uz, the source.
* Commands: ``/start`` and ``/lang`` for everyone, per language
  (``language_code`` ru/en, the default list in uz). Admins additionally get
  ``/admin`` through a ``BotCommandScopeChat`` in their own language. Admins
  added later see it after the next bot restart (the command itself works for
  them right away).
"""
from __future__ import annotations

import logging
from typing import Iterable

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault, MenuButtonWebApp, WebAppInfo

from src.db.connection import connect
from src.functions.admin_roles import admin_candidate_ids
from src.i18n import DEFAULT_LANG, LANGS, normalize_lang, t

logger = logging.getLogger(__name__)

#: Upper bound of per-admin ``setMyCommands`` calls at startup.
MAX_ADMIN_SCOPES = 50

USER_COMMANDS = ("start", "lang")
ADMIN_COMMANDS = ("start", "lang", "admin")


def commands_for(lang: str, names: Iterable[str]) -> list[BotCommand]:
    return [BotCommand(command=name, description=t(lang, f"cmd.{name}")) for name in names]


async def _admin_langs(admin_ids: Iterable[int] | None) -> dict[int, str]:
    async with connect() as conn:
        ids = sorted(await admin_candidate_ids(conn, admin_ids))[:MAX_ADMIN_SCOPES]
        langs: dict[int, str] = {}
        for user_id in ids:
            cursor = await conn.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            langs[user_id] = normalize_lang(row[0] if row else DEFAULT_LANG)
    return langs


async def setup_bot_ui(bot: Bot, webapp_url: str, admin_ids: Iterable[int] | None = None) -> dict[str, int]:
    """Set the menu button and command lists. Returns ``{"ok": n, "failed": m}``."""
    result = {"ok": 0, "failed": 0}

    async def attempt(label: str, coro) -> None:
        try:
            await coro
            result["ok"] += 1
        except Exception as exc:
            result["failed"] += 1
            logger.warning("bot_setup: %s failed: %s", label, exc)

    await attempt(
        "set_chat_menu_button",
        bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text=t(DEFAULT_LANG, "bot.menu_button"), web_app=WebAppInfo(url=webapp_url)
            )
        ),
    )

    for lang in LANGS:
        await attempt(
            f"set_my_commands[{lang}]",
            bot.set_my_commands(
                commands=commands_for(lang, USER_COMMANDS),
                scope=BotCommandScopeDefault(),
                language_code=None if lang == DEFAULT_LANG else lang,
            ),
        )

    try:
        admins = await _admin_langs(admin_ids)
    except Exception as exc:
        logger.warning("bot_setup: admin lookup failed: %s", exc)
        admins = {}
    for user_id, lang in admins.items():
        await attempt(
            f"set_my_commands[admin {user_id}]",
            bot.set_my_commands(
                commands=commands_for(lang, ADMIN_COMMANDS),
                scope=BotCommandScopeChat(chat_id=user_id),
            ),
        )

    logger.info("bot_setup: %s ok, %s failed", result["ok"], result["failed"])
    return result
