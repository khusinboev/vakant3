"""Self-healing fallback for premium (custom) emoji.

Custom emoji in bot messages and ``icon_custom_emoji_id`` on buttons only work
when the bot owner has Telegram Premium. If Telegram refuses them, every
message with an icon would fail and the bot would stay dead until someone edits
``.env``. This request middleware sits under ALL Bot API methods
(``bot.session.middleware(...)`` in ``config.py``):

* a request fails with ``TelegramBadRequest`` (any wording) AND carried custom
  emoji (``<tg-emoji`` in ``text``/``caption``, or ``icon_custom_emoji_id`` on
  a keyboard button) -> it is rewritten to the plain form exactly as the
  non-premium path renders it (tag -> fallback emoji, icon id -> fallback
  prefix on the label, so ``TextKey`` matching still works) and retried ONCE;
* the retry succeeds -> premium is switched off process-wide
  (``emoji.disable_premium``), one WARNING is logged; later requests are built
  plain from the start;
* the retry fails -> its error is raised (the problem was not the emoji);
* no custom emoji in the request -> the original error is re-raised unchanged.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

from src.ui import emoji

logger = logging.getLogger(__name__)

_TG_EMOJI_RE = re.compile(r"<tg-emoji\b[^>]*>(.*?)</tg-emoji>", re.DOTALL | re.IGNORECASE)
_TEXT_FIELDS = ("text", "caption")

#: custom emoji id -> fallback emoji (first registry entry wins).
_FALLBACK_BY_ID: dict[str, str] = {}
for _icon in emoji.ICONS.values():
    if _icon.id:
        _FALLBACK_BY_ID.setdefault(_icon.id, _icon.fallback)


def strip_tg_emoji(text: str) -> str:
    return _TG_EMOJI_RE.sub(r"\1", text)


def _plain_button(button: Any) -> Any:
    cid = getattr(button, "icon_custom_emoji_id", None)
    if not cid:
        return button
    fb = _FALLBACK_BY_ID.get(cid, "")
    label = f"{fb} {button.text}" if fb else button.text
    return button.model_copy(update={"icon_custom_emoji_id": None, "text": label})


def _plain_markup(markup: Any) -> Any:
    if isinstance(markup, InlineKeyboardMarkup):
        rows = [[_plain_button(b) for b in row] for row in markup.inline_keyboard]
        return markup.model_copy(update={"inline_keyboard": rows})
    if isinstance(markup, ReplyKeyboardMarkup):
        rows = [[_plain_button(b) for b in row] for row in markup.keyboard]
        return markup.model_copy(update={"keyboard": rows})
    return markup


def _markup_has_icons(markup: Any) -> bool:
    if isinstance(markup, InlineKeyboardMarkup):
        rows = markup.inline_keyboard
    elif isinstance(markup, ReplyKeyboardMarkup):
        rows = markup.keyboard
    else:
        return False
    return any(getattr(b, "icon_custom_emoji_id", None) for row in rows for b in row)


def has_custom_emoji(method: Any) -> bool:
    for field in _TEXT_FIELDS:
        value = getattr(method, field, None)
        if isinstance(value, str) and "<tg-emoji" in value.lower():
            return True
    return _markup_has_icons(getattr(method, "reply_markup", None))


def plain_copy(method: Any) -> Any:
    """A copy of ``method`` with every custom emoji replaced by its fallback."""
    update: dict[str, Any] = {}
    for field in _TEXT_FIELDS:
        value = getattr(method, field, None)
        if isinstance(value, str) and "<tg-emoji" in value.lower():
            update[field] = strip_tg_emoji(value)
    markup = getattr(method, "reply_markup", None)
    if _markup_has_icons(markup):
        update["reply_markup"] = _plain_markup(markup)
    return method.model_copy(update=update)


class PremiumEmojiFallback(BaseRequestMiddleware):
    async def __call__(self, make_request, bot, method):
        try:
            return await make_request(bot, method)
        except TelegramBadRequest as exc:
            if not has_custom_emoji(method):
                raise
            first_error = exc
        response = await make_request(bot, plain_copy(method))  # a failure here propagates
        if emoji.disable_premium():
            logger.warning(
                "premium emoji rejected by Telegram (%s: %s); switched to plain emoji for this process",
                type(method).__name__,
                first_error,
            )
        return response
