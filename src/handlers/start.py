# ============================================
# src/handlers/start.py - Aiogram 3.x
# ============================================
import html
import logging
import time
from urllib.parse import quote

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import bot
from src.buttons.buttuns import key_inline, open_app_kb, referral_share_kb
from src.db.connection import connect
from src.filters.admin import IsAdmin
from src.functions.main_menu import send_main_menu
from src.functions.functions import channel_row_target, functions, load_channel_rows
from src.functions.referral_gate import get_referral_gate_state, referral_gate_message
from src.functions.scraping import fetch_osonish_detail
from src.functions.vacancy_format import format_vacancy_message_html, vacancy_app_url
from src.i18n import DEFAULT_LANG, LANGS, normalize_lang, t
from src.ui.emoji import clip

logger = logging.getLogger(__name__)

router = Router()


def _esc(value) -> str:
    return html.escape(str(value or ""), quote=False)


def referral_share_url(ref_link: str, lang: str = DEFAULT_LANG) -> str:
    """``t.me/share/url`` link that lets the user forward their referral link."""
    text = t(lang, "referral.share_text", plain_emoji=True)
    return f"https://t.me/share/url?url={quote(ref_link, safe='')}&text={quote(text, safe='')}"


def build_lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(code, f"lang.name.{code}"), callback_data=f"lang:{code}"
                )
                for code in LANGS
            ]
        ]
    )


async def mark_bot_started(user_id: int) -> None:
    """Record the /start press the Mini App entry gate requires.

    The Mini App can be opened without ever pressing /start (Main App button,
    ``t.me/<bot>/app``), so ``users.started_at`` is what tells the API this user
    really came through the bot. Set once — the first /start is the one we mean.
    """
    try:
        async with connect() as conn:
            await conn.execute(
                "UPDATE users SET started_at = ? WHERE user_id = ? AND started_at IS NULL",
                (int(time.time()), int(user_id)),
            )
            await conn.commit()
    except Exception as exc:  # eski baza / migratsiya hali ishlamagan
        logger.warning("started_at yozilmadi user_id=%s: %s", user_id, exc)


async def _send_main_menu(message: Message, user_id: int, lang: str, first_name: str | None) -> None:
    """ONE message: the greeting carries the persistent main reply keyboard.

    The Mini App buttons are reply-keyboard ``web_app`` buttons whose URLs hold
    the user's signed ``bt`` login link (reply-keyboard launches have no
    initData), so no second inline "app" message is needed any more.
    """
    await send_main_menu(message, user_id, lang, t(lang, "start.greeting", name=_esc(first_name)))


@router.message(CommandStart())
async def welcome(
    message: Message,
    state: FSMContext,
    lang: str = DEFAULT_LANG,
    is_new_user: bool = False,
):
    """Start handler. Referralni middleware ushlaydi."""
    await state.clear()
    user_id = message.from_user.id
    await mark_bot_started(user_id)

    args = (message.text or "").split()
    start_param = args[1] if len(args) > 1 else ""

    # Referral gate hamma tarmoqlardan oldin tekshiriladi (deeplink ham bypass qilmaydi).
    gate_state = await get_referral_gate_state(user_id)
    if not bool(gate_state.get("unlocked")):
        share = referral_share_url(str(gate_state.get("ref_link") or ""), lang)
        await message.answer(
            referral_gate_message(gate_state, lang), reply_markup=referral_share_kb(lang, share)
        )
        return

    # ── Vakansiya deeplink: /start vacancy_osonish_12345 ────────────────
    if start_param.startswith("vacancy_osonish_"):
        uid = start_param[len("vacancy_"):]   # "osonish_12345"
        try:
            raw_id = int(uid.split("_", 1)[1])
        except (IndexError, ValueError):
            await message.answer(t(lang, "start.bad_vacancy_link"))
            return

        await message.answer(t(lang, "start.loading_vacancy"))
        detail = await fetch_osonish_detail(raw_id)
        if not isinstance(detail, dict):
            await message.answer(t(lang, "start.vacancy_not_found"))
            return

        text = format_vacancy_message_html(uid, detail, lang)
        await message.answer(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=open_app_kb(lang, vacancy_app_url(uid)),
        )
        return
    # ────────────────────────────────────────────────────────────────────

    if is_new_user:
        await message.answer(t(lang, "lang.choose"), reply_markup=build_lang_keyboard())

    is_subscribed = await functions.check_on_start(user_id, bot)

    if is_subscribed:
        await _send_main_menu(message, user_id, lang, message.from_user.first_name)
        return

    join_keyboard = await build_channel_keyboard(lang)
    if join_keyboard:
        await message.answer(t(lang, "start.subscribe_prompt"), reply_markup=join_keyboard)
    else:
        await _send_main_menu(message, user_id, lang, message.from_user.first_name)


# ── Til tanlash ─────────────────────────────────────────────────────────

@router.message(Command("lang", "til", "language"))
async def choose_language(message: Message, lang: str = DEFAULT_LANG):
    await message.answer(t(lang, "lang.choose"), reply_markup=build_lang_keyboard())


@router.callback_query(F.data.startswith("lang:"))
async def set_language(call: CallbackQuery):
    new_lang = normalize_lang(call.data.split(":", 1)[1])

    async with connect() as conn:
        await conn.execute(
            "UPDATE users SET lang = ? WHERE user_id = ?", (new_lang, call.from_user.id)
        )
        await conn.commit()

    await call.answer()
    try:
        await call.message.edit_text(t(new_lang, "lang.saved"))
    except Exception:
        await call.message.answer(t(new_lang, "lang.saved"))

    # Re-send the whole menu so the reply keyboard and buttons switch language too.
    await _send_main_menu(call.message, call.from_user.id, new_lang, call.from_user.first_name)


# ── Kanal obunasi ───────────────────────────────────────────────────────

async def build_channel_keyboard(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup | None:
    """Kanallar keyboard (bazadagi havola/sarlavha ustun, yo'q bo'lsa getChat)."""
    async with connect() as conn:
        channels = await load_channel_rows(conn)

    if not channels:
        return None

    buttons = []
    for idx, row in enumerate(channels, 1):
        data = dict(row)
        target = channel_row_target(row)
        invite_link = data.get("invite_link")
        title = data.get("title")
        if not invite_link and data.get("username"):
            invite_link = f"https://t.me/{str(data['username']).lstrip('@')}"

        if not invite_link or not title:
            try:
                chat = await bot.get_chat(chat_id=target)
                invite_link = invite_link or chat.invite_link
                title = title or chat.title
                if not invite_link:
                    invite_link = await bot.export_chat_invite_link(target)
            except Exception as exc:
                logger.debug("kanal tugmasi qurilmadi id=%s: %s", target, exc)
                continue

        if not invite_link:
            continue

        label = clip(f"{idx}. {title or t(lang, 'start.channel_fallback')}", 60)
        buttons.append([InlineKeyboardButton(text=label, url=invite_link)])

    if not buttons:
        return None

    buttons.append([key_inline(lang, "start.btn.subscribed", callback_data="check", style="success")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "check")
async def check_subscription(call: CallbackQuery, lang: str = DEFAULT_LANG):
    """Obuna tekshirish"""
    is_subscribed = await functions.check_on_start(call.from_user.id, bot)

    if not is_subscribed:
        await call.answer(t(lang, "start.check.fail"), show_alert=True)
        return

    await call.answer(t(lang, "start.check.ok"), show_alert=False)

    try:
        await call.message.delete()
    except Exception:
        pass

    # The reply keyboard was never sent to a user who had to subscribe first.
    await send_main_menu(
        call.message,
        call.from_user.id,
        lang,
        t(lang, "start.check.welcome", name=_esc(call.from_user.first_name)),
    )


# ── Admin diagnostikasi ─────────────────────────────────────────────────

@router.message(Command("check_channels"), IsAdmin())
async def diagnose_channels(message: Message, lang: str = DEFAULT_LANG):
    """Kanallar diagnostikasi"""
    async with connect() as conn:
        channels = await load_channel_rows(conn, enabled_only=False)

    if not channels:
        await message.answer(t(lang, "admin.channels_db_empty"))
        return

    lines = [t(lang, "admin.channels_status_header"), ""]

    for idx, row in enumerate(channels, 1):
        channel_id = channel_row_target(row)
        try:
            chat = await bot.get_chat(chat_id=channel_id)
            bot_member = await bot.get_chat_member(chat_id=channel_id, user_id=bot.id)
            is_admin = bot_member.status in ("administrator", "creator")

            yes, no = t(lang, "common.yes"), t(lang, "common.no")
            lines.append(f"{idx}. ✅ {_esc(chat.title)}")
            lines.append(f"   {t(lang, 'admin.diag.id')}: {_esc(channel_id)}")
            lines.append(f"   {t(lang, 'admin.diag.admin')}: {yes if is_admin else no}")
            lines.append(
                f"   {t(lang, 'admin.diag.link')}: "
                f"{t(lang, 'common.available') if chat.invite_link else t(lang, 'common.unavailable')}"
            )
            lines.append("")
        except Exception as exc:
            lines.append(f"{idx}. ❌ {_esc(channel_id)}")
            lines.append(f"   {t(lang, 'admin.diag.error')}: {_esc(str(exc)[:50])}")
            lines.append("")

    await message.answer("\n".join(lines))


@router.message(Command("developer", "coder", "programmer"))
async def coder(message: Message, lang: str = DEFAULT_LANG):
    await message.reply(t(lang, "start.developer"))
