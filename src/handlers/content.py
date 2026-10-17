# ============================================================
# src/handlers/content.py
# Qonunchilik va HR maslahatlar bo'limlari (til bo'yicha).
# ============================================================
import html
import re
from urllib.parse import urlparse

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.buttons.buttuns import key_inline
from src.data.content_repo import get_article, get_articles, get_tip, get_tips
from src.filters.text_key import TextKey
from src.functions.main_menu import refresh_if_stale
from src.i18n import DEFAULT_LANG, t
from src.ui.emoji import CALLBACK_MAX_BYTES, clip, e, inline_button

router = Router(name="content")

# Botda ko'rsatish uchun maksimal belgilar soni
_MAX_CHARS = 3000

_TAG_RE = re.compile(r"<(/?)([a-zA-Z]+)\b[^>]*>")
_VOID_TAGS = {"br"}


# ── Helpers ─────────────────────────────────────────────────


def _fits_callback(data: str) -> bool:
    """An admin-made id too long for callback_data is left out of the menu
    instead of making Telegram reject the whole keyboard."""
    return len(data.encode("utf-8")) <= CALLBACK_MAX_BYTES


async def _laws_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [
        [inline_button("laws", clip(a["title"], 60), callback_data=f"law:{a['id']}")]
        for a in await get_articles(lang)
        if _fits_callback(f"law:{a['id']}")
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _hr_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [
        [inline_button("tips", clip(tip["title"], 60), callback_data=f"hr:{tip['id']}")]
        for tip in await get_tips(lang)
        if _fits_callback(f"hr:{tip['id']}")
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def safe_source_url(url: str | None) -> str | None:
    """``url`` when it is an http(s) link with a host, else None.

    ``source_url`` is admin input with no scheme check on the API side; a
    ``javascript:`` or malformed value must not reach an href or a URL button
    (Telegram rejects the whole message for a bad button URL).
    """
    value = str(url or "").strip()
    parsed = urlparse(value)
    if parsed.scheme.lower() in ("http", "https") and parsed.netloc:
        return value
    return None


def _close_open_tags(fragment: str) -> str:
    """Drop a tag cut in half and close the tags a cut left open."""
    last_open = fragment.rfind("<")
    if last_open > fragment.rfind(">"):
        fragment = fragment[:last_open]
    stack: list[str] = []
    for match in _TAG_RE.finditer(fragment):
        closing, name = match.group(1), match.group(2).lower()
        if name in _VOID_TAGS:
            continue
        if not closing:
            stack.append(name)
        elif name in stack:
            while stack and stack.pop() != name:
                pass
    return fragment + "".join(f"</{name}>" for name in reversed(stack))


def _truncate(text: str, source_url: str, lang: str) -> str:
    """Matn juda uzun bo'lsa qisqartirib, manba havolasini qo'shadi."""
    if len(text) <= _MAX_CHARS:
        return text
    cut = _close_open_tags(text[:_MAX_CHARS].rsplit("\n", 1)[0])
    # content.truncated is trusted dictionary HTML (<i>...</i>).
    result = f"{cut}\n\n{t(lang, 'content.truncated')}"
    url = safe_source_url(source_url)
    if url:
        read_more = html.escape(t(lang, "content.laws.read_more"), quote=False)
        result += f"\n{e('link')} <a href=\"{html.escape(url, quote=True)}\">{read_more}</a>"
    return result


# ── Handlers: Qonunchilik ───────────────────────────────────


@router.message(TextKey("menu.laws"))
async def laws_menu(message: Message, lang: str = DEFAULT_LANG) -> None:
    await refresh_if_stale(message, message.from_user.id, lang)
    await message.answer(
        t(lang, "content.laws.header"),
        reply_markup=await _laws_keyboard(lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("law:"))
async def law_detail(callback: CallbackQuery, lang: str = DEFAULT_LANG) -> None:
    article_id = callback.data.split(":", 1)[1]
    article = await get_article(article_id, lang)
    if article is None:
        await callback.answer(t(lang, "content.laws.not_found"), show_alert=True)
        return

    text = _truncate(article["full_text"], article["source_url"], lang)
    rows: list[list[InlineKeyboardButton]] = []
    source_url = safe_source_url(article["source_url"])
    if source_url:
        rows.append(
            [key_inline(lang, "content.laws.read_more", url=source_url)]
        )
    rows.append([key_inline(lang, "common.back", callback_data="laws_back")])
    back_kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "laws_back")
async def laws_back(callback: CallbackQuery, lang: str = DEFAULT_LANG) -> None:
    await callback.message.edit_text(
        t(lang, "content.laws.header"),
        reply_markup=await _laws_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Handlers: HR Maslahatlar ────────────────────────────────


@router.message(TextKey("menu.hr"))
async def hr_menu(message: Message, lang: str = DEFAULT_LANG) -> None:
    await refresh_if_stale(message, message.from_user.id, lang)
    await message.answer(
        t(lang, "content.hr.header"),
        reply_markup=await _hr_keyboard(lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("hr:"))
async def hr_detail(callback: CallbackQuery, lang: str = DEFAULT_LANG) -> None:
    tip_id = callback.data.split(":", 1)[1]
    tip = await get_tip(tip_id, lang)
    if tip is None:
        await callback.answer(t(lang, "content.hr.not_found"), show_alert=True)
        return

    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [key_inline(lang, "common.back", callback_data="hr_back")]
        ]
    )
    await callback.message.edit_text(
        tip["full_text"], reply_markup=back_kb, parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "hr_back")
async def hr_back(callback: CallbackQuery, lang: str = DEFAULT_LANG) -> None:
    await callback.message.edit_text(
        t(lang, "content.hr.header"),
        reply_markup=await _hr_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()
