# ============================================
# src/handlers/admin.py - Aiogram 3.x
# Admin tekshiruvi router filtri orqali (IsAdmin), matn routing i18n kaliti bo'yicha.
# ============================================
import asyncio
import datetime
import logging
from typing import Awaitable, Callable

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from config import bot
from src.buttons.buttuns import back_btn, channel_btn, main_btn, reklama_btn
from src.core.timeutil import month_end, month_step_back, now_tz
from src.db.connection import connect
from src.filters.admin import IsAdmin
from src.filters.text_key import TextKey
from src.functions.functions import panel_func
from src.i18n import DEFAULT_LANG, key_for_text, t

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(IsAdmin())

PROGRESS_EVERY = 50
SEND_DELAY_SECONDS = 0.05


class AdminStates(StatesGroup):
    channel_add = State()
    channel_delete = State()
    send_msg = State()
    forward_msg = State()


@router.message(Command("admin", "panel"))
async def admin_panel(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    await state.clear()
    await message.answer(t(lang, "admin.hello"), reply_markup=main_btn(lang))


@router.message(TextKey("btn.admin.back"))
async def back_handler(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    await state.clear()
    await message.reply(t(lang, "admin.main_menu"), reply_markup=main_btn(lang))


# ── Statistika ──────────────────────────────────────────────────────────

@router.message(TextKey("btn.admin.stats"))
async def statistics_handler(message: Message, lang: str = DEFAULT_LANG):
    now = now_tz()

    async with connect() as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE blocked = 1")
        blocked_users = (await cursor.fetchone())[0]

        three_months_ago_ts = int((now - datetime.timedelta(days=90)).timestamp())
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM users WHERE date >= ?", (three_months_ago_ts,)
        )
        last_3_months_users = (await cursor.fetchone())[0]

        months_stats: list[tuple[str, int]] = []
        for i in range(3):
            first_day = month_step_back(now, i)
            last_day = month_end(first_day)
            month_name = t(lang, f"month.{first_day.month}")

            cursor = await conn.execute(
                "SELECT COUNT(*) FROM users WHERE date BETWEEN ? AND ?",
                (int(first_day.timestamp()), int(last_day.timestamp())),
            )
            months_stats.append((month_name, (await cursor.fetchone())[0]))

        last_7_days: list[tuple[str, int]] = []
        for i in range(7):
            date = now - datetime.timedelta(days=i)
            date_str = date.strftime("%d-%m-%Y")

            start_ts = int(date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
            end_ts = int(date.replace(hour=23, minute=59, second=59, microsecond=0).timestamp())

            cursor = await conn.execute(
                "SELECT COUNT(*) FROM users WHERE date BETWEEN ? AND ?", (start_ts, end_ts)
            )
            last_7_days.append((date_str, (await cursor.fetchone())[0]))

    lines = [
        t(lang, "admin.stats.header"),
        "",
        t(lang, "admin.stats.total", count=total_users),
        t(lang, "admin.stats.blocked", count=blocked_users),
        t(lang, "admin.stats.last3m", count=last_3_months_users),
    ]
    lines += [t(lang, "admin.stats.row", label=name, count=count) for name, count in months_stats]
    lines += ["", t(lang, "admin.stats.last7d", count=sum(c for _, c in last_7_days))]
    lines += [t(lang, "admin.stats.row", label=day, count=count) for day, count in last_7_days]

    await message.answer("\n".join(lines))


# ── Kanallar ────────────────────────────────────────────────────────────

@router.message(TextKey("btn.admin.channels"))
async def channels_menu(message: Message, lang: str = DEFAULT_LANG):
    await message.answer(t(lang, "admin.choose"), reply_markup=channel_btn(lang))


@router.message(TextKey("btn.admin.channel_add"))
async def channel_add_start(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    await message.reply(t(lang, "admin.channel_add_prompt"), reply_markup=back_btn(lang))
    await state.set_state(AdminStates.channel_add)


def _channel_username(message: Message) -> str | None:
    text = message.text
    if not isinstance(text, str):
        return None
    return text.strip().upper()


@router.message(AdminStates.channel_add)
async def channel_add_process(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    channel_username = _channel_username(message)
    if channel_username is None:
        await message.reply(t(lang, "admin.text_required"), reply_markup=back_btn(lang))
        return

    if key_for_text(message.text) == "btn.admin.back":
        await state.clear()
        await message.reply(t(lang, "admin.cancelled"), reply_markup=main_btn(lang))
        return

    if not channel_username.startswith("@"):
        await message.reply(
            t(lang, "admin.channel_bad_format"), reply_markup=channel_btn(lang)
        )
        await state.clear()
        return

    async with connect() as conn:
        cursor = await conn.execute(
            "SELECT id FROM channels WHERE id = ?", (channel_username,)
        )
        exists = await cursor.fetchone()

    if exists:
        await message.reply(t(lang, "admin.channel_exists"), reply_markup=channel_btn(lang))
    else:
        await panel_func.channel_add(channel_username)
        await message.reply(t(lang, "admin.channel_added"), reply_markup=channel_btn(lang))

    await state.clear()


@router.message(TextKey("btn.admin.channel_del"))
async def channel_delete_start(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    await message.reply(t(lang, "admin.channel_del_prompt"), reply_markup=back_btn(lang))
    await state.set_state(AdminStates.channel_delete)


@router.message(AdminStates.channel_delete)
async def channel_delete_process(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    channel_username = _channel_username(message)
    if channel_username is None:
        await message.reply(t(lang, "admin.text_required"), reply_markup=back_btn(lang))
        return

    if key_for_text(message.text) == "btn.admin.back":
        await state.clear()
        await message.reply(t(lang, "admin.cancelled"), reply_markup=main_btn(lang))
        return

    if not channel_username.startswith("@"):
        await message.reply(
            t(lang, "admin.channel_bad_format"), reply_markup=channel_btn(lang)
        )
        await state.clear()
        return

    async with connect() as conn:
        cursor = await conn.execute(
            "SELECT id FROM channels WHERE id = ?", (channel_username,)
        )
        exists = await cursor.fetchone()

    if not exists:
        await message.reply(t(lang, "admin.channel_missing"), reply_markup=channel_btn(lang))
    else:
        await panel_func.channel_delete(channel_username)
        await message.reply(t(lang, "admin.channel_deleted"), reply_markup=channel_btn(lang))

    await state.clear()


@router.message(TextKey("btn.admin.channel_list"))
async def channel_list_handler(message: Message, lang: str = DEFAULT_LANG):
    channels_info = await panel_func.channel_list(bot, lang)

    if channels_info.strip() and channels_info != t(lang, "admin.channels_none"):
        await message.reply(channels_info)
    else:
        await message.reply(t(lang, "admin.channels_empty"))


# ── Reklama (broadcast) ─────────────────────────────────────────────────

@router.message(TextKey("btn.admin.ads"))
async def broadcast_menu(message: Message, lang: str = DEFAULT_LANG):
    await message.reply(t(lang, "admin.broadcast_menu"), reply_markup=reklama_btn(lang))


@router.message(TextKey("btn.admin.forward"))
async def forward_broadcast_start(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    await message.answer(t(lang, "admin.forward_prompt"), reply_markup=back_btn(lang))
    await state.set_state(AdminStates.forward_msg)


@router.message(TextKey("btn.admin.copy"))
async def copy_broadcast_start(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    await message.answer(t(lang, "admin.copy_prompt"), reply_markup=back_btn(lang))
    await state.set_state(AdminStates.send_msg)


async def _mark_blocked(conn, user_id: int, blocked: bool) -> None:
    """users.blocked ni yangilaydi (faqat qiymat o'zgarganda yozadi)."""
    value = 1 if blocked else 0
    cursor = await conn.execute(
        "UPDATE users SET blocked = ? WHERE user_id = ? AND blocked != ?",
        (value, user_id, value),
    )
    if cursor.rowcount:
        await conn.commit()


async def _deliver(
    conn, send: Callable[[int], Awaitable[object]], user_id: int
) -> bool:
    """Bitta foydalanuvchiga yuborish. Flood wait bo'lsa kutib, BIR marta qayta uriladi."""
    try:
        await send(user_id)
        await _mark_blocked(conn, user_id, False)
        return True
    except TelegramRetryAfter as exc:
        logger.warning("Broadcast: flood wait %ss", exc.retry_after)
        await asyncio.sleep(exc.retry_after)
        try:
            await send(user_id)
            await _mark_blocked(conn, user_id, False)
            return True
        except TelegramForbiddenError:
            await _mark_blocked(conn, user_id, True)
            return False
        except Exception as retry_exc:
            logger.error("Broadcast retry xato user_id=%s: %s", user_id, retry_exc)
            return False
    except TelegramForbiddenError:
        await _mark_blocked(conn, user_id, True)
        return False
    except Exception as exc:
        logger.error("Broadcast xato user_id=%s: %s", user_id, exc)
        return False


async def _run_broadcast(
    message: Message,
    state: FSMContext,
    lang: str,
    send: Callable[[int], Awaitable[object]],
) -> None:
    await state.clear()

    async with connect() as conn:
        cursor = await conn.execute("SELECT user_id FROM users WHERE blocked = 0")
        users = [int(row[0]) for row in await cursor.fetchall()]

        total = len(users)
        success_count = 0
        failed_count = 0

        status_msg = await message.answer(t(lang, "admin.sending", done=0, total=total))

        for idx, user_id in enumerate(users, 1):
            if await _deliver(conn, send, user_id):
                success_count += 1
            else:
                failed_count += 1

            if idx % PROGRESS_EVERY == 0:
                try:
                    await status_msg.edit_text(
                        t(
                            lang,
                            "admin.progress",
                            done=idx,
                            total=total,
                            ok=success_count,
                            fail=failed_count,
                        )
                    )
                except TelegramBadRequest:
                    pass

            await asyncio.sleep(SEND_DELAY_SECONDS)

    await status_msg.edit_text(
        t(lang, "admin.finished", total=total, ok=success_count, fail=failed_count)
    )


def _is_back(message: Message) -> bool:
    """Har qanday tildagi «Orqaga» tugmasi."""
    return key_for_text(message.text) == "btn.admin.back"


@router.message(AdminStates.forward_msg)
async def forward_broadcast_send(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    if _is_back(message):
        await state.clear()
        await message.reply(t(lang, "admin.cancelled"), reply_markup=main_btn(lang))
        return

    chat_id = message.chat.id
    message_id = message.message_id

    async def send(user_id: int):
        return await bot.forward_message(user_id, chat_id, message_id)

    await _run_broadcast(message, state, lang, send)


@router.message(AdminStates.send_msg)
async def copy_broadcast_send(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    if _is_back(message):
        await state.clear()
        await message.reply(t(lang, "admin.cancelled"), reply_markup=main_btn(lang))
        return

    chat_id = message.chat.id
    message_id = message.message_id

    async def send(user_id: int):
        return await bot.copy_message(user_id, chat_id, message_id)

    await _run_broadcast(message, state, lang, send)
