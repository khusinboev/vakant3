# ============================================
# src/handlers/admin.py - Aiogram 3.x
# Admin tekshiruvi router filtri orqali (IsAdmin), matn routing i18n kaliti bo'yicha.
# ============================================
import asyncio
import datetime
import logging

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
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
from src.functions.broadcast_worker import broadcast_progress, create_broadcast, queue_broadcast
from src.functions.functions import panel_func, parse_channel_link
from src.i18n import DEFAULT_LANG, key_for_text, t

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(IsAdmin())

#: The bot no longer sends broadcasts itself — it queues them and watches the
#: counters the worker writes (src/functions/broadcast_worker.py).
PROGRESS_POLL_SECONDS = 5.0
#: Stop watching after this long; the worker keeps going either way.
PROGRESS_MAX_SECONDS = 6 * 60 * 60
TERMINAL_STATUSES = frozenset({"done", "cancelled", "failed"})


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


def _channel_input(message: Message) -> str | None:
    text = message.text
    if not isinstance(text, str):
        return None
    return text.strip()


async def _find_channel_row(parsed, chat_id: int | None = None):
    """Existing row for a parsed reference: by id, by username or by chat_id."""
    candidates = [parsed.target] if parsed.target else []
    if parsed.kind == "username":
        # Legacy rows were stored upper-cased, exactly as the admin typed them.
        candidates += [f"@{parsed.username.upper()}", parsed.username]
    async with connect() as conn:
        for candidate in candidates:
            cursor = await conn.execute(
                "SELECT id FROM channels WHERE id = ? COLLATE NOCASE", (candidate,)
            )
            row = await cursor.fetchone()
            if row:
                return row[0]
        if chat_id is not None:
            try:
                cursor = await conn.execute(
                    "SELECT id FROM channels WHERE chat_id = ?", (int(chat_id),)
                )
            except Exception:
                return None
            row = await cursor.fetchone()
            if row:
                return row[0]
    return None


@router.message(AdminStates.channel_add)
async def channel_add_process(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    raw = _channel_input(message)
    if raw is None:
        await message.reply(t(lang, "admin.text_required"), reply_markup=back_btn(lang))
        return

    if key_for_text(message.text) == "btn.admin.back":
        await state.clear()
        await message.reply(t(lang, "admin.cancelled"), reply_markup=main_btn(lang))
        return

    try:
        parsed = parse_channel_link(raw)
    except ValueError:
        await message.reply(
            t(lang, "admin.channel_bad_format"), reply_markup=channel_btn(lang)
        )
        await state.clear()
        return

    if parsed.kind == "invite":
        # getChat cannot resolve a private invite link — the numeric id is needed.
        await message.reply(
            t(lang, "admin.channel_bad_format"), reply_markup=channel_btn(lang)
        )
        await state.clear()
        return

    # Darhol tekshirish: kanal bormi va bot unda adminmi.
    try:
        chat = await bot.get_chat(chat_id=parsed.target)
        member = await bot.get_chat_member(chat_id=chat.id, user_id=bot.id)
        is_admin = member.status in ("administrator", "creator")
    except Exception as exc:
        logger.warning("channel_add tekshiruvi muvaffaqiyatsiz %s: %s", parsed.target, exc)
        await message.reply(
            t(lang, "admin.channel_no_admin", username=raw), reply_markup=channel_btn(lang)
        )
        await state.clear()
        return

    if not is_admin:
        await message.reply(
            t(lang, "admin.channel_no_admin", username=chat.title or raw),
            reply_markup=channel_btn(lang),
        )
        await state.clear()
        return

    existing = await _find_channel_row(parsed, chat.id)
    if existing:
        await message.reply(t(lang, "admin.channel_exists"), reply_markup=channel_btn(lang))
        await state.clear()
        return

    username = chat.username or parsed.username
    channel_id = f"@{username}" if username else str(chat.id)
    invite_link = chat.invite_link or (f"https://t.me/{username}" if username else None)
    await panel_func.channel_add(
        channel_id,
        title=chat.title,
        username=username,
        invite_link=invite_link,
        chat_id=chat.id,
        added_by=message.from_user.id,
        bot_is_admin=True,
    )
    await message.reply(t(lang, "admin.channel_added"), reply_markup=channel_btn(lang))
    await state.clear()


@router.message(TextKey("btn.admin.channel_del"))
async def channel_delete_start(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    await message.reply(t(lang, "admin.channel_del_prompt"), reply_markup=back_btn(lang))
    await state.set_state(AdminStates.channel_delete)


@router.message(AdminStates.channel_delete)
async def channel_delete_process(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    raw = _channel_input(message)
    if raw is None:
        await message.reply(t(lang, "admin.text_required"), reply_markup=back_btn(lang))
        return

    if key_for_text(message.text) == "btn.admin.back":
        await state.clear()
        await message.reply(t(lang, "admin.cancelled"), reply_markup=main_btn(lang))
        return

    try:
        parsed = parse_channel_link(raw)
    except ValueError:
        await message.reply(
            t(lang, "admin.channel_bad_format"), reply_markup=channel_btn(lang)
        )
        await state.clear()
        return

    existing = await _find_channel_row(parsed)
    if not existing:
        await message.reply(t(lang, "admin.channel_missing"), reply_markup=channel_btn(lang))
    else:
        await panel_func.channel_delete(existing)
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


async def _watch_progress(status_msg: Message, broadcast_id: int, lang: str) -> None:
    """Refresh the progress message from the DB until the job ends."""
    deadline = asyncio.get_running_loop().time() + PROGRESS_MAX_SECONDS
    last_line = ""

    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(PROGRESS_POLL_SECONDS)
        async with connect() as conn:
            progress = await broadcast_progress(conn, broadcast_id)
        if progress is None:
            return

        ok = progress["sent"]
        fail = progress["failed"] + progress["blocked"]
        if progress["status"] in TERMINAL_STATUSES:
            await _edit(
                status_msg,
                t(lang, "admin.finished", total=progress["total"], ok=ok, fail=fail),
            )
            return

        line = t(
            lang,
            "admin.progress",
            done=progress["done"],
            total=progress["total"],
            ok=ok,
            fail=fail,
        )
        if line != last_line:
            await _edit(status_msg, line)
            last_line = line


async def _edit(status_msg: Message, text: str) -> None:
    try:
        await status_msg.edit_text(text)
    except TelegramBadRequest:  # message unchanged or deleted
        pass


async def _queue_broadcast_from_message(
    message: Message, state: FSMContext, lang: str, mode: str
) -> None:
    """Turn the admin's message into a broadcast job and follow its progress.

    Both the bot flow and the admin panel write the same rows, so there is one
    worker, one rate limiter and one progress source.
    """
    await state.clear()

    async with connect() as conn:
        broadcast_id = await create_broadcast(
            conn,
            actor_id=message.from_user.id,
            kind="forward",
            forward_chat_id=message.chat.id,
            forward_message_id=message.message_id,
            target={"segment": "all", "exclude_blocked": True, "forward_mode": mode},
        )
        total = await queue_broadcast(conn, broadcast_id)
        await conn.commit()

    logger.info("broadcast %s queued by %s (%s users, mode=%s)", broadcast_id, message.from_user.id, total, mode)
    status_msg = await message.answer(t(lang, "admin.sending", done=0, total=total))
    await _watch_progress(status_msg, broadcast_id, lang)


def _is_back(message: Message) -> bool:
    """Har qanday tildagi «Orqaga» tugmasi."""
    return key_for_text(message.text) == "btn.admin.back"


@router.message(AdminStates.forward_msg)
async def forward_broadcast_send(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    if _is_back(message):
        await state.clear()
        await message.reply(t(lang, "admin.cancelled"), reply_markup=main_btn(lang))
        return

    await _queue_broadcast_from_message(message, state, lang, "forward")


@router.message(AdminStates.send_msg)
async def copy_broadcast_send(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    if _is_back(message):
        await state.clear()
        await message.reply(t(lang, "admin.cancelled"), reply_markup=main_btn(lang))
        return

    await _queue_broadcast_from_message(message, state, lang, "copy")
