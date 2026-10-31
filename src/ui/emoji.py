"""Premium (custom) emoji registry and button helpers for the bot.

Every icon has a semantic key, a plain ``fallback`` emoji and optionally the id
of a Telegram custom emoji (Fluent Emoji 3D / TopicIcons packs, the same ids the
SlaydX bot uses). With premium emoji enabled:

* in a message text an icon is ``<tg-emoji emoji-id="ID">fallback</tg-emoji>``;
* a button gets ``icon_custom_emoji_id`` and a BARE label (Telegram draws the
  icon in front of the text, a second plain emoji would double it).

Otherwise (flag off, no id, or ``plain=True``) the fallback emoji is written
into the text / prefixed to the label. Never both.

Custom emoji only render for bots whose owner has Telegram Premium in PRIVATE
and group chats. A bot without a Fragment username cannot use them in CHANNEL
posts, so channel code (auto-post, weekly stats) always passes ``plain=True``.
Toasts/alerts (``callback.answer``) are plain text, so their keys carry literal
emoji, never ``{e:...}`` tokens.

Flag: env ``BOT_PREMIUM_EMOJI`` (default on; ``0/false/no/off`` disables it).
It is read on every call so tests can flip it with ``monkeypatch.setenv``.

Text templates in ``src/i18n`` reference icons as ``{e:key}``; ``t()`` renders
them through :func:`render_tokens` before the ``str.format`` variables are
substituted, so user input can never smuggle a token in.
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, NamedTuple

from aiogram.types import InlineKeyboardButton, KeyboardButton, WebAppInfo


class Icon(NamedTuple):
    fallback: str
    id: str | None = None


#: semantic key -> icon. Ids fetched by SlaydX with getStickerSet (2026-10-08).
ICONS: dict[str, Icon] = {
    # Navigation / generic
    "app": Icon("📱", "6334342012954740512"),
    "back": Icon("⬅️"),
    "next": Icon("▶️", "5341270334882463507"),
    "home": Icon("🏠", "6334564870217795443"),
    "link": Icon("🔗", "6334318948980360832"),
    "share": Icon("📤"),
    "lang": Icon("🌐", "6334670964499941098"),
    "wave": Icon("👋", "6332573100609111421"),
    "info": Icon("💬", "6334320873125709187"),
    "lock": Icon("🔒", "6334379984760604198"),
    "new": Icon("🆕", "5400038655861466061"),
    "rocket": Icon("🚀", "6334710044407368265"),
    "sparkles": Icon("✨", "6334649330749671032"),
    "fire": Icon("🔥", "6334402121022048240"),
    "hourglass": Icon("⏳", "5363826996314912469"),
    "pointer": Icon("👇"),
    # Status
    "success": Icon("✅"),
    "ok": Icon("👍", "6334815245336315702"),
    "warning": Icon("🚨", "6334656829762569757"),
    "error": Icon("❌"),
    "stop": Icon("⛔"),
    "cancel": Icon("✖️"),
    "party": Icon("🎉", "6332586724245374910"),
    # Product sections
    "job": Icon("💼", "6332307572845971158"),
    "search": Icon("🔍", "6334784609334592942"),
    "saves": Icon("📂", "6334367610959824701"),
    "profile": Icon("👤"),
    "wallet": Icon("💰", "6334575946938451719"),
    "money": Icon("💵", "6334849386031351338"),
    "laws": Icon("📚", "6334818668425250358"),
    "tips": Icon("💡", "6334385804441290536"),
    "bell": Icon("🔔", "6334583798138668579"),
    "resume": Icon("📄", "6334335136712099470"),
    "pro": Icon("💎", "6334498994009408947"),
    "star": Icon("⭐", "6334496442798835895"),
    "gift": Icon("🎁", "6332182224225437319"),
    "group": Icon("👥"),
    # Admin
    "admin": Icon("🛠", "6332490126135920267"),
    "stats": Icon("📈", "6334338757369530043"),
    "broadcast": Icon("📢"),
    "channel": Icon("📣"),
    "plus": Icon("➕"),
    "list": Icon("📋"),
    "test": Icon("🧪"),
    "pause": Icon("⏸"),
    "refresh": Icon("🔄"),
    "skip": Icon("⏭"),
    # Vacancy fields
    "company": Icon("🏢", "6334586495378130466"),
    "position": Icon("👔", "6334576191751587505"),
    "salary": Icon("💰", "6334575946938451719"),
    "location": Icon("📌", "6334567936824444680"),
    "work_type": Icon("🧩"),
    "busyness": Icon("⏱"),
    "payment": Icon("💳", "6334829912649631269"),
    "education": Icon("🎓", "6334337408749799175"),
    "experience": Icon("🧰", "6334533164769216289"),
    "gender": Icon("👤"),
    "count": Icon("🔢"),
    "hours": Icon("🕘"),
    "calendar": Icon("📅"),
    "deadline": Icon("⌛", "6334358870701376795"),
    "description": Icon("📝", "6334434311801931493"),
    "phone": Icon("📞", "6332469123745842874"),
    "bot": Icon("🤖"),
}

_OFF_VALUES = {"0", "false", "no", "off"}

#: ``{e:key}`` placeholder inside an i18n template.
TOKEN_RE = re.compile(r"\{e:([a-z0-9_]+)\}")

#: Telegram's ``callback_data`` limit, in bytes.
CALLBACK_MAX_BYTES = 64

#: Bot API button styles (``KeyboardButton.style`` / ``InlineKeyboardButton.style``).
STYLES = ("primary", "success", "danger")


#: Kill switches, set by ``src/ui/emoji_fallback.py`` when Telegram rejected a
#: request with custom emoji and its plain retry went through. They are per chat
#: type: a CHANNEL rejection (a bot without a Fragment username cannot use custom
#: emoji there) must never turn premium off for private chats, where it works.
PRIVATE = "private"
CHANNEL = "channel"
_premium_killed = False  # private chats (and any request without a chat id)
_channels_plain = False


def disable_premium(scope: str = PRIVATE) -> bool:
    """Switch premium emoji off for ``scope`` in this process. True if it was on before.

    ``PRIVATE`` (default) stops :func:`premium_enabled`; ``CHANNEL`` only makes
    :func:`channels_plain` true (channel code is plain anyway).
    """
    global _premium_killed, _channels_plain
    if scope == CHANNEL:
        was_on = not _channels_plain
        _channels_plain = True
        return was_on
    was_on = not _premium_killed
    _premium_killed = True
    return was_on


def reset_premium_kill_switch() -> None:
    """Tests only: undo :func:`disable_premium` for every scope."""
    global _premium_killed, _channels_plain
    _premium_killed = False
    _channels_plain = False


def channels_plain() -> bool:
    """True once Telegram rejected custom emoji in a channel/supergroup request."""
    return _channels_plain


def premium_enabled() -> bool:
    """True unless ``BOT_PREMIUM_EMOJI`` is switched off or a private-chat rejection fired."""
    if _premium_killed:
        return False
    return (os.getenv("BOT_PREMIUM_EMOJI") or "1").strip().lower() not in _OFF_VALUES


def icon_id(key: str | None, *, plain: bool = False) -> str | None:
    """The custom emoji id of ``key`` when premium emoji apply, else None."""
    if not key or plain or not premium_enabled():
        return None
    icon = ICONS.get(key)
    return icon.id if icon is not None else None


def fallback(key: str | None) -> str:
    icon = ICONS.get(key or "")
    return icon.fallback if icon is not None else ""


def e(key: str, *, plain: bool = False) -> str:
    """An icon inside an HTML message text ("" for an unknown key)."""
    icon = ICONS.get(key)
    if icon is None:
        return ""
    cid = icon_id(key, plain=plain)
    if cid:
        return f'<tg-emoji emoji-id="{cid}">{icon.fallback}</tg-emoji>'
    return icon.fallback


def render_tokens(template: str, *, plain: bool = False) -> str:
    """Replace every ``{e:key}`` in a trusted template with :func:`e`."""
    if "{e:" not in template:
        return template
    return TOKEN_RE.sub(lambda m: e(m.group(1), plain=plain), template)


# ── Labels and buttons ───────────────────────────────────────────────────

def clip(text: str, max_chars: int) -> str:
    """Collapse whitespace and cut to ``max_chars`` code points, ellipsis included.

    Python strings index by code point, so a cut never splits a surrogate pair
    (a broken emoji makes Telegram reject the whole keyboard).
    """
    value = " ".join(str(text or "").split())
    if max_chars <= 0:
        return ""
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "…"


def labelled(icon: str | None, text: str, *, plain: bool = False) -> dict[str, Any]:
    """``{"text", "icon_custom_emoji_id"?}``: the icon goes to the field OR the label."""
    if not icon:
        return {"text": text}
    cid = icon_id(icon, plain=plain)
    if cid:
        return {"text": text, "icon_custom_emoji_id": cid}
    fb = fallback(icon)
    return {"text": f"{fb} {text}" if fb else text}


def inline_button(
    icon: str | None,
    text: str,
    *,
    callback_data: str | None = None,
    url: str | None = None,
    web_app: str | None = None,
    style: str | None = None,
    plain: bool = False,
) -> InlineKeyboardButton:
    """One inline button with exactly one action."""
    actions = [a for a in (callback_data, url, web_app) if a is not None]
    if len(actions) != 1:
        raise ValueError("inline_button needs exactly one of callback_data / url / web_app")
    if callback_data is not None and len(callback_data.encode("utf-8")) > CALLBACK_MAX_BYTES:
        raise ValueError(f"callback_data over {CALLBACK_MAX_BYTES} bytes: {callback_data!r}")
    if style is not None and style not in STYLES:
        raise ValueError(f"unknown button style {style!r}")
    kwargs: dict[str, Any] = labelled(icon, text, plain=plain)
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    elif url is not None:
        kwargs["url"] = url
    else:
        kwargs["web_app"] = WebAppInfo(url=web_app)
    if style:
        kwargs["style"] = style
    return InlineKeyboardButton(**kwargs)


def reply_button(
    icon: str | None, text: str, *, style: str | None = None, web_app: str | None = None
) -> KeyboardButton:
    """Reply-keyboard button; ``web_app`` makes it open a Mini App (no initData)."""
    if style is not None and style not in STYLES:
        raise ValueError(f"unknown button style {style!r}")
    kwargs: dict[str, Any] = labelled(icon, text)
    if web_app is not None:
        kwargs["web_app"] = WebAppInfo(url=web_app)
    if style:
        kwargs["style"] = style
    return KeyboardButton(**kwargs)


# ── Matching reply-keyboard taps ─────────────────────────────────────────

_JOINERS = {"‍", "️", "︎", "⃣"}


def _is_emoji_char(ch: str) -> bool:
    if ch.isspace() or ch in _JOINERS:
        return True
    cp = ord(ch)
    if 0x1F3FB <= cp <= 0x1F3FF or 0xE0020 <= cp <= 0xE007F:  # skin tones, tag chars
        return True
    return unicodedata.category(ch) == "So"


def strip_leading_emoji(text: Any) -> str:
    """``text`` without leading emoji / whitespace, trailing whitespace trimmed.

    A reply-keyboard tap sends the button label as the message text: with a
    custom emoji icon that is the bare label, with the fallback it is
    "<emoji> label", and old keyboards may still carry earlier labels
    ("📊Statistika"). Matching compares both sides through this function.
    """
    if not isinstance(text, str):
        return ""
    i = 0
    while i < len(text) and _is_emoji_char(text[i]):
        i += 1
    return text[i:].strip()
