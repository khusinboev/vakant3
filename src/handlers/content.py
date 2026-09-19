# ============================================================
# src/handlers/content.py
# Qonunchilik va HR maslahatlar bo'limlari (til bo'yicha).
# ============================================================
from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.data.hr_tips import get_tip, get_tips
from src.data.law_articles import get_article, get_articles
from src.filters.text_key import TextKey
from src.i18n import DEFAULT_LANG, t

router = Router(name="content")

# Botda ko'rsatish uchun maksimal belgilar soni
_MAX_CHARS = 3000


# ── Helpers ─────────────────────────────────────────────────


def _laws_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"⚖️ {a['title']}", callback_data=f"law:{a['id']}")]
        for a in get_articles(lang)
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _hr_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"💡 {tip['title']}", callback_data=f"hr:{tip['id']}")]
        for tip in get_tips(lang)
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _truncate(text: str, source_url: str, lang: str) -> str:
    """Matn juda uzun bo'lsa qisqartirib, manba havolasini qo'shadi."""
    if len(text) <= _MAX_CHARS:
        return text
    cut = text[:_MAX_CHARS].rsplit("\n", 1)[0]
    read_more = t(lang, "content.laws.read_more")
    return (
        f"{cut}\n\n{t(lang, 'content.truncated')}\n"
        f"🔗 <a href=\"{source_url}\">{read_more}</a>"
    )


# ── Handlers: Qonunchilik ───────────────────────────────────


@router.message(TextKey("menu.laws"))
async def laws_menu(message: Message, lang: str = DEFAULT_LANG) -> None:
    await message.answer(
        t(lang, "content.laws.header"),
        reply_markup=_laws_keyboard(lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("law:"))
async def law_detail(callback: CallbackQuery, lang: str = DEFAULT_LANG) -> None:
    article_id = callback.data.split(":", 1)[1]
    article = get_article(article_id, lang)
    if article is None:
        await callback.answer(t(lang, "content.laws.not_found"), show_alert=True)
        return

    text = _truncate(article["full_text"], article["source_url"], lang)
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "content.laws.read_more"), url=article["source_url"]
                )
            ],
            [InlineKeyboardButton(text=t(lang, "common.back"), callback_data="laws_back")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "laws_back")
async def laws_back(callback: CallbackQuery, lang: str = DEFAULT_LANG) -> None:
    await callback.message.edit_text(
        t(lang, "content.laws.header"),
        reply_markup=_laws_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Handlers: HR Maslahatlar ────────────────────────────────


@router.message(TextKey("menu.hr"))
async def hr_menu(message: Message, lang: str = DEFAULT_LANG) -> None:
    await message.answer(
        t(lang, "content.hr.header"),
        reply_markup=_hr_keyboard(lang),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("hr:"))
async def hr_detail(callback: CallbackQuery, lang: str = DEFAULT_LANG) -> None:
    tip_id = callback.data.split(":", 1)[1]
    tip = get_tip(tip_id, lang)
    if tip is None:
        await callback.answer(t(lang, "content.hr.not_found"), show_alert=True)
        return

    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "common.back"), callback_data="hr_back")]
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
        reply_markup=_hr_keyboard(lang),
        parse_mode="HTML",
    )
    await callback.answer()
