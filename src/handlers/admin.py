# ============================================================
# src/handlers/admin.py - Aiogram 3.x
# Bot admin panel: statistics, channels and the broadcast wizard.
#
# Access: the role comes from the ``admins`` table on EVERY message and every
# callback (src/filters/admin.py, src/functions/admin_roles.py), the same rule
# as the API. Users outside a 30 s candidate set (enabled rows + ADMIN_IDS) are
# refused without a query, so ordinary users' messages cost no connection here. Permissions mirror the API routers: statistics and the channel
# list are viewer+, channel add/delete and broadcasts are admin+.
#
# Every mutation writes an ``admin_audit_log`` row (source=bot) in the same
# transaction (src/functions/admin_audit.py).
#
# Broadcast wizard (private chat only):
#   content message -> optional URL button -> audience (count shown)
#   -> draft row + preview copied to the admin -> test to me / send to N
#   -> queued for the worker -> one progress card with pause/resume/stop.
# The draft lives in ``broadcasts`` (status 'draft'), so the card's buttons
# work from the database alone: a second "send" tap finds the row no longer
# in 'draft' and queues nothing.
# ============================================================
from __future__ import annotations

import asyncio
import datetime
import html
import json
import logging
import secrets
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import WEBAPP_URL, bot
from src.buttons.buttuns import (
    BROADCAST_SEGMENTS,
    CB_BROADCAST,
    CB_WIZARD,
    admin_webapp_kb,
    back_btn,
    bc_audience_kb,
    bc_button_step_kb,
    bc_list_kb,
    bc_preview_kb,
    bc_progress_kb,
    channel_btn,
    main_btn,
    reklama_btn,
    segment_label,
)
from src.core.timeutil import month_end, month_step_back, now_tz
from src.db.connection import connect
from src.filters.admin import IsAdmin, current_admin_role
from src.filters.text_key import TextKey
from src.functions.admin_audit import log_bot_action
from src.functions.admin_roles import broadcast_admin_ids, has_role
from src.functions.broadcast_control import set_broadcast_state
from src.functions.broadcast_worker import (
    broadcast_progress,
    create_broadcast,
    is_valid_segment,
    materialize_targets,
    queue_broadcast,
)
from src.functions.functions import panel_func, parse_channel_link
from src.i18n import DEFAULT_LANG, key_for_text, t

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(F.chat.type == ChatType.PRIVATE, IsAdmin())
# Callbacks are not filtered by role at router level: a revoked admin tapping
# an old card must get an answer ("not allowed"), not a spinning button.
router.callback_query.filter(F.data.startswith("adm:"))

#: The bot does not send broadcasts itself — it queues them and watches the
#: counters the worker writes (src/functions/broadcast_worker.py).
PROGRESS_POLL_SECONDS = 5.0
#: Stop watching after this long; the worker keeps going either way.
PROGRESS_MAX_SECONDS = 6 * 60 * 60
TERMINAL_STATUSES = frozenset({"done", "cancelled", "failed"})
ACTIVE_STATUSES = frozenset({"queued", "running", "paused"})
#: A draft card older than this can no longer be tested or sent from the bot.
DRAFT_TTL_SECONDS = 30 * 60
#: Message kinds the wizard accepts; all are delivered with copyMessage, which
#: keeps formatting and custom-emoji entities.
CONTENT_TYPES = frozenset({"text", "photo", "video", "document", "animation"})
BUTTON_TEXT_MAX = 64
BUTTON_URL_MAX = 1024
LIST_LIMIT = 5
WIZARD_SEGMENTS = frozenset(segment for segment, _ in BROADCAST_SEGMENTS)
#: An album arrives as one update per item, all within about a second; its
#: ``media_group_id`` is remembered this long so only the first part is answered.
ALBUM_MEMORY_SECONDS = 60.0
#: (chat id, media_group_id) -> when the first part was seen (monotonic).
_albums_seen: dict[tuple[int, str], float] = {}


class AdminStates(StatesGroup):
    channel_add = State()
    channel_delete = State()


class BroadcastWizard(StatesGroup):
    content = State()
    button = State()
    audience = State()
    creating = State()  # the draft is being written; a second tap is stale


def admin_webapp_url() -> str:
    """The Mini App admin route.

    The SPA mounts its routes at the origin root (``/app`` is the user entry,
    ``/admin/*`` the panel; see ``webapp/frontend/src/App.tsx``), so the panel
    is ``<origin>/admin``. ``WEBAPP_URL + "/admin"`` would be ``/app/admin``,
    which the router redirects back to ``/app``.
    """
    parts = urlsplit(WEBAPP_URL)
    return urlunsplit((parts.scheme, parts.netloc, "/admin", "", ""))


def _first_album_part(message: Message) -> bool:
    """True for the first update of an album in this chat, False for the others.

    Check-and-set with no await in between, so parts handled concurrently
    cannot both count as the first.
    """
    now = time.monotonic()
    for key, seen in list(_albums_seen.items()):
        if now - seen > ALBUM_MEMORY_SECONDS:
            del _albums_seen[key]
    key = (message.chat.id, str(message.media_group_id))
    if key in _albums_seen:
        return False
    _albums_seen[key] = now
    return True


def _is_back(message: Message) -> bool:
    """Har qanday tildagi «Orqaga» tugmasi."""
    return key_for_text(getattr(message, "text", None)) == "btn.admin.back"


# ── Menu ────────────────────────────────────────────────────────────────

@router.message(Command("admin", "panel"))
async def admin_panel(
    message: Message, state: FSMContext, lang: str = DEFAULT_LANG, admin_role: str | None = None
):
    await state.clear()
    await message.answer(t(lang, "admin.hello"), reply_markup=main_btn(lang, admin_role))
    await message.answer(
        t(lang, "admin.webapp_hint"), reply_markup=admin_webapp_kb(lang, admin_webapp_url())
    )


@router.message(TextKey("btn.admin.back"))
async def back_handler(
    message: Message, state: FSMContext, lang: str = DEFAULT_LANG, admin_role: str | None = None
):
    await state.clear()
    await message.reply(t(lang, "admin.main_menu"), reply_markup=main_btn(lang, admin_role))


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
async def channels_menu(message: Message, lang: str = DEFAULT_LANG, admin_role: str | None = None):
    await message.answer(t(lang, "admin.choose"), reply_markup=channel_btn(lang, admin_role))


@router.message(TextKey("btn.admin.channel_list"))
async def channel_list_handler(message: Message, lang: str = DEFAULT_LANG):
    channels_info = await panel_func.channel_list(bot, lang)

    if channels_info.strip() and channels_info != t(lang, "admin.channels_none"):
        await message.reply(channels_info)
    else:
        await message.reply(t(lang, "admin.channels_empty"))


@router.message(TextKey("btn.admin.channel_add"), IsAdmin("admin"))
async def channel_add_start(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    await message.reply(t(lang, "admin.channel_add_prompt"), reply_markup=back_btn(lang))
    await state.set_state(AdminStates.channel_add)


@router.message(TextKey("btn.admin.channel_del"), IsAdmin("admin"))
async def channel_delete_start(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    await message.reply(t(lang, "admin.channel_del_prompt"), reply_markup=back_btn(lang))
    await state.set_state(AdminStates.channel_delete)


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


async def _insert_channel(conn, channel_id: str, *, chat, username, invite_link, added_by) -> None:
    """Same upsert as ``panel_func.channel_add`` but on the caller's transaction."""
    now = int(time.time())
    await conn.execute(
        """
        INSERT INTO channels
            (id, title, username, invite_link, chat_id, enabled,
             added_by, added_at, last_check_ok, last_check_at)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?, 1, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = COALESCE(excluded.title, channels.title),
            username = COALESCE(excluded.username, channels.username),
            invite_link = COALESCE(excluded.invite_link, channels.invite_link),
            chat_id = COALESCE(excluded.chat_id, channels.chat_id),
            enabled = 1,
            last_check_ok = excluded.last_check_ok,
            last_check_at = excluded.last_check_at
        """,
        (channel_id, chat.title, username, invite_link, chat.id, added_by, now, now),
    )


@router.message(AdminStates.channel_add, IsAdmin("admin"))
async def channel_add_process(
    message: Message, state: FSMContext, lang: str = DEFAULT_LANG, admin_role: str | None = None
):
    raw = _channel_input(message)
    if raw is None:
        await message.reply(t(lang, "admin.text_required"), reply_markup=back_btn(lang))
        return

    if key_for_text(message.text) == "btn.admin.back":
        await state.clear()
        await message.reply(t(lang, "admin.cancelled"), reply_markup=main_btn(lang, admin_role))
        return

    keyboard = channel_btn(lang, admin_role)
    try:
        parsed = parse_channel_link(raw)
    except ValueError:
        await message.reply(t(lang, "admin.channel_bad_format"), reply_markup=keyboard)
        await state.clear()
        return

    if parsed.kind == "invite":
        # getChat cannot resolve a private invite link — the numeric id is needed.
        await message.reply(t(lang, "admin.channel_bad_format"), reply_markup=keyboard)
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
            t(lang, "admin.channel_no_admin", username=html.escape(raw)), reply_markup=keyboard
        )
        await state.clear()
        return

    if not is_admin:
        await message.reply(
            t(lang, "admin.channel_no_admin", username=html.escape(chat.title or raw)),
            reply_markup=keyboard,
        )
        await state.clear()
        return

    existing = await _find_channel_row(parsed, chat.id)
    if existing:
        await message.reply(t(lang, "admin.channel_exists"), reply_markup=keyboard)
        await state.clear()
        return

    username = chat.username or parsed.username
    channel_id = f"@{username}" if username else str(chat.id)
    invite_link = chat.invite_link or (f"https://t.me/{username}" if username else None)
    async with connect() as conn:
        await _insert_channel(
            conn, channel_id, chat=chat, username=username, invite_link=invite_link,
            added_by=message.from_user.id,
        )
        await log_bot_action(
            conn,
            actor_id=message.from_user.id,
            action="channels.add",
            target_type="channel",
            target_id=channel_id,
            payload={"chat_id": chat.id, "title": chat.title},
        )
        await conn.commit()
    await message.reply(t(lang, "admin.channel_added"), reply_markup=keyboard)
    await state.clear()


@router.message(AdminStates.channel_delete, IsAdmin("admin"))
async def channel_delete_process(
    message: Message, state: FSMContext, lang: str = DEFAULT_LANG, admin_role: str | None = None
):
    raw = _channel_input(message)
    if raw is None:
        await message.reply(t(lang, "admin.text_required"), reply_markup=back_btn(lang))
        return

    if key_for_text(message.text) == "btn.admin.back":
        await state.clear()
        await message.reply(t(lang, "admin.cancelled"), reply_markup=main_btn(lang, admin_role))
        return

    keyboard = channel_btn(lang, admin_role)
    try:
        parsed = parse_channel_link(raw)
    except ValueError:
        await message.reply(t(lang, "admin.channel_bad_format"), reply_markup=keyboard)
        await state.clear()
        return

    existing = await _find_channel_row(parsed)
    if not existing:
        await message.reply(t(lang, "admin.channel_missing"), reply_markup=keyboard)
    else:
        async with connect() as conn:
            await conn.execute("DELETE FROM channels WHERE id = ?", (existing,))
            # Cached verdicts were computed against the old channel set (as in the API).
            await conn.execute("DELETE FROM subscription_checks")
            await log_bot_action(
                conn,
                actor_id=message.from_user.id,
                action="channels.delete",
                target_type="channel",
                target_id=existing,
            )
            await conn.commit()
        await message.reply(t(lang, "admin.channel_deleted"), reply_markup=keyboard)

    await state.clear()


# ── Reklama (broadcast wizard) ──────────────────────────────────────────

@router.message(TextKey("btn.admin.ads"), IsAdmin("admin"))
async def broadcast_menu(message: Message, lang: str = DEFAULT_LANG):
    await message.reply(t(lang, "admin.broadcast_menu"), reply_markup=reklama_btn(lang))


@router.message(TextKey("btn.admin.bc_new"), IsAdmin("admin"))
async def wizard_start(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    await state.clear()
    await state.set_state(BroadcastWizard.content)
    await state.update_data(nonce=secrets.token_hex(4))
    await message.answer(t(lang, "bc.prompt_content"), reply_markup=back_btn(lang))


@router.message(TextKey("btn.admin.bc_list"), IsAdmin("admin"))
async def broadcast_list(message: Message, lang: str = DEFAULT_LANG):
    """The last broadcasts worth opening.

    Skipped: drafts past ``DRAFT_TTL_SECONDS`` (they can no longer be sent) and
    broadcasts cancelled while still drafts (never queued, so ``total`` is 0).
    """
    async with connect() as conn:
        cursor = await conn.execute(
            "SELECT id, status, total, sent, failed, blocked FROM broadcasts "
            "WHERE NOT (status = 'draft' AND COALESCE(created_at, 0) < ?) "
            "AND NOT (status = 'cancelled' AND COALESCE(total, 0) = 0) "
            "ORDER BY id DESC LIMIT ?",
            (int(time.time()) - DRAFT_TTL_SECONDS, LIST_LIMIT),
        )
        rows = await cursor.fetchall()
    if not rows:
        await message.answer(t(lang, "bc.list_empty"))
        return
    lines = [t(lang, "bc.list_header"), ""]
    buttons: list[tuple[int, str]] = []
    for row in rows:
        line = t(
            lang,
            "bc.list_row",
            id=int(row[0]),
            status=_status_label(lang, row[1]),
            done=int(row[3]) + int(row[4]) + int(row[5]),
            total=int(row[2]),
        )
        lines.append(line)
        buttons.append((int(row[0]), line))
    await message.answer("\n".join(lines), reply_markup=bc_list_kb(buttons))


@router.message(BroadcastWizard.content, IsAdmin("admin"))
async def wizard_content(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    if message.media_group_id:
        # copyMessage sends one message; the album's other parts would reach
        # the button step. Refuse once, stay here and drop the remaining parts.
        if _first_album_part(message):
            await message.answer(t(lang, "bc.album_unsupported"))
        return
    if message.content_type not in CONTENT_TYPES:
        await message.answer(t(lang, "bc.bad_content"))
        return
    data = await state.get_data()
    nonce = data.get("nonce") or secrets.token_hex(4)
    await state.update_data(
        nonce=nonce, src_chat=message.chat.id, src_msg=message.message_id, button=None
    )
    await state.set_state(BroadcastWizard.button)
    await message.answer(t(lang, "bc.prompt_button"), reply_markup=bc_button_step_kb(lang, nonce))


def parse_button(text: Any) -> dict[str, str] | None:
    """``"Text | https://..."`` -> ``{"text", "url"}``; None when invalid."""
    if not isinstance(text, str) or "|" not in text:
        return None
    label, _, url = text.partition("|")
    label, url = label.strip(), url.strip()
    if not 1 <= len(label) <= BUTTON_TEXT_MAX:
        return None
    if not url or len(url) > BUTTON_URL_MAX or any(ch.isspace() for ch in url):
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        return None
    return {"text": label, "url": url}


@router.message(BroadcastWizard.button, IsAdmin("admin"))
async def wizard_button(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    if message.media_group_id and not _first_album_part(message):
        return  # one answer per album, not one per item
    button = parse_button(message.text)
    if button is None:
        data = await state.get_data()
        await message.answer(
            t(lang, "bc.bad_button"), reply_markup=bc_button_step_kb(lang, data.get("nonce", ""))
        )
        return
    await state.update_data(button=button)
    await state.set_state(BroadcastWizard.audience)
    data = await state.get_data()
    await message.answer(t(lang, "bc.prompt_audience"), reply_markup=bc_audience_kb(lang, data["nonce"]))


@router.message(StateFilter(BroadcastWizard.audience, BroadcastWizard.creating), IsAdmin("admin"))
async def wizard_audience_text(message: Message, state: FSMContext, lang: str = DEFAULT_LANG):
    if message.media_group_id and not _first_album_part(message):
        return
    data = await state.get_data()
    await message.answer(
        t(lang, "bc.prompt_audience"), reply_markup=bc_audience_kb(lang, data.get("nonce", ""))
    )


# ── Denials for viewer / moderator ──────────────────────────────────────
# Registered after the admin+ handlers, so they only see what those refused.

@router.message(
    TextKey(
        "btn.admin.channel_add", "btn.admin.channel_del", "btn.admin.ads",
        "btn.admin.bc_new", "btn.admin.bc_list",
    )
)
@router.message(
    StateFilter(
        AdminStates.channel_add, AdminStates.channel_delete, BroadcastWizard.content,
        BroadcastWizard.button, BroadcastWizard.audience, BroadcastWizard.creating,
    )
)
async def denied_handler(
    message: Message, state: FSMContext, lang: str = DEFAULT_LANG, admin_role: str | None = None
):
    await state.clear()
    await message.answer(t(lang, "admin.denied"), reply_markup=main_btn(lang, admin_role))


# ── Cards ───────────────────────────────────────────────────────────────

def _status_label(lang: str, status: str) -> str:
    label = t(lang, f"bc.status.{status}")
    return label if label != f"bc.status.{status}" else html.escape(str(status))


def _segment_text(lang: str, segment: str) -> str:
    return segment_label(lang, segment) or html.escape(str(segment))


def _target_segment(target_json: str | None) -> str:
    try:
        target = json.loads(target_json or "{}")
    except json.JSONDecodeError:
        target = {}
    return str(target.get("segment") or "all")


def _url_keyboard(buttons_json: str | None) -> InlineKeyboardMarkup | None:
    """The broadcast's own URL button(s), exactly as recipients get them."""
    try:
        buttons = json.loads(buttons_json or "[]")
    except json.JSONDecodeError:
        return None
    rows = [
        [InlineKeyboardButton(text=str(b["text"]), url=str(b["url"]))]
        for b in buttons
        if isinstance(b, dict) and b.get("text") and b.get("url")
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def _load_broadcast(conn, broadcast_id: int):
    cursor = await conn.execute(
        "SELECT id, actor_id, status, created_at, forward_chat_id, forward_message_id, "
        "buttons_json, target_json FROM broadcasts WHERE id = ?",
        (broadcast_id,),
    )
    return await cursor.fetchone()


async def _card(broadcast_id: int, lang: str) -> tuple[str, str] | None:
    """(card text, status) from the DB, or None when the broadcast is gone."""
    async with connect() as conn:
        progress = await broadcast_progress(conn, broadcast_id)
        row = await _load_broadcast(conn, broadcast_id)
    if progress is None or row is None:
        return None
    ok = int(progress["sent"])
    fail = int(progress["failed"]) + int(progress["blocked"])
    status = progress["status"]
    if status in TERMINAL_STATUSES:
        body = t(lang, "admin.finished", total=progress["total"], ok=ok, fail=fail)
    else:
        body = t(lang, "admin.progress", done=progress["done"], total=progress["total"], ok=ok, fail=fail)
    text = t(
        lang,
        "bc.card",
        id=int(progress["id"]),
        status=_status_label(lang, status),
        segment=_segment_text(lang, _target_segment(row[7])),
        body=body,
    )
    return text, status


#: One progress card: (broadcast id, chat id, message id). Several admins (or
#: one admin from the list) may each have a card of the same broadcast.
CardKey = tuple[int, int, int]
#: At most this many live cards per broadcast; opening one more stops the
#: watcher of the oldest card (its buttons keep working, it just stops ticking).
MAX_WATCHERS_PER_BROADCAST = 5

#: card -> watcher task (one per card).
_watchers: dict[CardKey, asyncio.Task] = {}
#: cards that currently show the "really stop?" question.
_stop_pending: set[CardKey] = set()


def _forget_broadcast(broadcast_id: int) -> None:
    """Drop every pending stop question of a broadcast that has ended."""
    for key in [k for k in _stop_pending if k[0] == broadcast_id]:
        _stop_pending.discard(key)


def _watching(key: CardKey) -> bool:
    task = _watchers.get(key)
    return task is not None and not task.done()


async def _edit(chat_id: int, message_id: int, text: str, markup=None) -> None:
    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup)
    except TelegramBadRequest:  # message unchanged or deleted
        pass


async def _render(chat_id: int, message_id: int, broadcast_id: int, lang: str) -> str | None:
    """Redraw one card in place; returns the status (None if the row is gone)."""
    key = (broadcast_id, chat_id, message_id)
    card = await _card(broadcast_id, lang)
    if card is None:
        _stop_pending.discard(key)
        return None
    text, status = card
    if status not in ACTIVE_STATUSES:
        _forget_broadcast(broadcast_id)
    confirm = key in _stop_pending
    if confirm:
        text += t(lang, "bc.stop_confirm")
    await _edit(chat_id, message_id, text, bc_progress_kb(lang, broadcast_id, status, confirm_stop=confirm))
    return status


async def _watch_progress(chat_id: int, message_id: int, broadcast_id: int, lang: str) -> None:
    """Refresh the card from the DB until the job ends (or the deadline)."""
    key = (broadcast_id, chat_id, message_id)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + PROGRESS_MAX_SECONDS
    last: tuple[str, bool] | None = None
    while loop.time() < deadline:
        await asyncio.sleep(PROGRESS_POLL_SECONDS)
        card = await _card(broadcast_id, lang)
        if card is None:
            return
        text, status = card
        confirm = key in _stop_pending and status in ACTIVE_STATUSES
        if (text, confirm) != last:
            shown = text + (t(lang, "bc.stop_confirm") if confirm else "")
            await _edit(chat_id, message_id, shown, bc_progress_kb(lang, broadcast_id, status, confirm_stop=confirm))
            last = (text, confirm)
        if status in TERMINAL_STATUSES:
            _forget_broadcast(broadcast_id)
            return
    _stop_pending.discard(key)  # deadline: the card stops asking as well


def _start_watcher(chat_id: int, message_id: int, broadcast_id: int, lang: str) -> asyncio.Task:
    """Watch one card; other cards of the same broadcast keep their watchers."""
    key = (broadcast_id, chat_id, message_id)
    previous = _watchers.pop(key, None)
    if previous is not None and not previous.done():
        previous.cancel()
    live = [k for k, task in _watchers.items() if k[0] == broadcast_id and not task.done()]
    for oldest in live[: max(0, len(live) - MAX_WATCHERS_PER_BROADCAST + 1)]:
        _watchers.pop(oldest).cancel()  # dicts keep insertion order: oldest first
        _stop_pending.discard(oldest)
    task = asyncio.create_task(_watch_progress(chat_id, message_id, broadcast_id, lang))
    _watchers[key] = task

    def _forget(done: asyncio.Task) -> None:
        if _watchers.get(key) is done:
            _watchers.pop(key, None)

    task.add_done_callback(_forget)
    return task


# ── Callbacks ───────────────────────────────────────────────────────────

@router.callback_query()
async def admin_callback(call: CallbackQuery, state: FSMContext, lang: str = DEFAULT_LANG):
    """Single entry for every ``adm:`` button: the role is re-read on each tap."""
    message = call.message
    chat = getattr(message, "chat", None)
    if message is None or getattr(chat, "type", None) != ChatType.PRIVATE:
        await call.answer(t(lang, "bc.expired"), show_alert=True)
        return
    role = await current_admin_role(call.from_user.id)
    if not has_role(role, "admin"):
        await call.answer(t(lang, "admin.denied"), show_alert=True)
        return

    data = call.data or ""
    if data.startswith(CB_WIZARD):
        parts = data[len(CB_WIZARD):].split(":", 2)
        if len(parts) >= 2:
            await _wizard_callback(call, state, lang, role, parts[0], parts[1], parts[2] if len(parts) > 2 else None)
            return
    elif data.startswith(CB_BROADCAST):
        broadcast_id, _, action = data[len(CB_BROADCAST):].partition(":")
        if broadcast_id.isdigit() and action:
            await _broadcast_callback(call, lang, role, int(broadcast_id), action)
            return
    await call.answer(t(lang, "bc.expired"), show_alert=True)


async def _wizard_callback(
    call: CallbackQuery, state: FSMContext, lang: str, role: str,
    nonce: str, action: str, arg: str | None,
) -> None:
    chat_id = call.message.chat.id
    data = await state.get_data()
    current = await state.get_state()
    if not nonce or data.get("nonce") != nonce:
        await call.answer(t(lang, "bc.expired"), show_alert=True)
        return

    if action == "x":
        await state.clear()
        await _edit(chat_id, call.message.message_id, t(lang, "admin.cancelled"))
        await bot.send_message(chat_id, t(lang, "admin.main_menu"), reply_markup=main_btn(lang, role))
        await call.answer()
        return

    if action == "skip" and current == BroadcastWizard.button.state:
        await state.update_data(button=None)
        await state.set_state(BroadcastWizard.audience)
        await _edit(chat_id, call.message.message_id, t(lang, "bc.prompt_audience"), bc_audience_kb(lang, nonce))
        await call.answer()
        return

    if action == "seg" and current == BroadcastWizard.audience.state:
        if arg not in WIZARD_SEGMENTS or not is_valid_segment(arg):
            await call.answer(t(lang, "bc.expired"), show_alert=True)
            return
        # Claimed before any await that can suspend: a second tap now sees
        # 'creating' and is stale, so one tap makes at most one draft.
        await state.set_state(BroadcastWizard.creating)
        try:
            await _create_draft_and_preview(call, state, lang, data, arg)
        except Exception:
            if await state.get_state() == BroadcastWizard.creating.state:
                await state.set_state(BroadcastWizard.audience)  # let the admin retry
            raise
        return

    await call.answer(t(lang, "bc.expired"), show_alert=True)


async def _create_draft(conn, *, actor_id: int, data: dict, segment: str) -> tuple[int, int]:
    """Draft row + recipient count + audit, in the caller's transaction.

    The count is what ``queue_broadcast`` would materialize right now: the
    targets are inserted with the worker's own segment SQL, counted and
    deleted again, so an abandoned draft leaves no target rows behind.
    """
    button = data.get("button")
    target = {"segment": segment, "exclude_blocked": True, "forward_mode": "copy"}
    broadcast_id = await create_broadcast(
        conn,
        actor_id=actor_id,
        kind="forward",
        forward_chat_id=int(data["src_chat"]),
        forward_message_id=int(data["src_msg"]),
        buttons=[button] if button else [],
        target=target,
        status="draft",
    )
    count = await materialize_targets(conn, broadcast_id, target, await broadcast_admin_ids(conn))
    await conn.execute("DELETE FROM broadcast_targets WHERE broadcast_id = ?", (broadcast_id,))
    await log_bot_action(
        conn,
        actor_id=actor_id,
        action="broadcast.create",
        target_type="broadcast",
        target_id=broadcast_id,
        payload={"kind": "copy", "segment": segment, "count": count, "buttons": 1 if button else 0},
    )
    return broadcast_id, count


async def _create_draft_and_preview(
    call: CallbackQuery, state: FSMContext, lang: str, data: dict, segment: str
) -> None:
    chat_id = call.message.chat.id
    actor_id = call.from_user.id
    async with connect() as conn:
        broadcast_id, count = await _create_draft(conn, actor_id=actor_id, data=data, segment=segment)
        if count == 0:
            await conn.rollback()
        else:
            await conn.commit()
    if count == 0:
        await state.set_state(BroadcastWizard.audience)
        await call.answer(t(lang, "bc.empty_segment"), show_alert=True)
        return

    await state.clear()
    # From here on the draft exists but the admin has no card for it yet: if
    # any step fails, the draft is cancelled so it cannot linger as 'draft'.
    button = data.get("button")
    try:
        await _edit(chat_id, call.message.message_id, t(lang, "bc.prompt_audience") + " " + _segment_text(lang, segment))
        await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=int(data["src_chat"]),
            message_id=int(data["src_msg"]),
            reply_markup=_url_keyboard(json.dumps([button] if button else [])),
        )
        card = t(
            lang,
            "bc.preview_card",
            segment=_segment_text(lang, segment),
            count=count,
            button=html.escape(button["text"]) if button else t(lang, "bc.no_button"),
        )
        await bot.send_message(chat_id, card, reply_markup=bc_preview_kb(lang, broadcast_id, count))
    except Exception as exc:  # deleted source, bad button URL, network, ...
        logger.warning("broadcast %s preview failed: %s", broadcast_id, exc)
        await _discard_draft(broadcast_id, actor_id, reason="preview_failed")
        try:
            await bot.send_message(chat_id, t(lang, "bc.preview_failed"))
            await call.answer()
        except Exception as notify_exc:
            logger.warning("broadcast %s preview failure notice failed: %s", broadcast_id, notify_exc)
        return
    await call.answer()


async def _discard_draft(broadcast_id: int, actor_id: int, *, reason: str) -> None:
    """Cancel a bot-created draft whose preview never reached the admin. Never raises.

    Only a row still in 'draft' changes (a card that did arrive despite an
    error may already have queued it), and the cancel is audited.
    """
    try:
        async with connect() as conn:
            cursor = await conn.execute(
                "UPDATE broadcasts SET status = 'cancelled', finished_at = ? "
                "WHERE id = ? AND status = 'draft'",
                (int(time.time()), broadcast_id),
            )
            if cursor.rowcount == 1:
                await log_bot_action(
                    conn, actor_id=actor_id, action="broadcast.cancel", target_type="broadcast",
                    target_id=broadcast_id, payload={"from": "draft", "reason": reason},
                )
            await conn.commit()
    except Exception as exc:
        logger.warning("broadcast %s draft cleanup failed: %s", broadcast_id, exc)


def _draft_usable(row, actor_id: int) -> bool:
    return (
        row is not None
        and int(row[1]) == int(actor_id)
        and row[2] == "draft"
        and int(row[3] or 0) >= int(time.time()) - DRAFT_TTL_SECONDS
    )


async def _broadcast_callback(
    call: CallbackQuery, lang: str, role: str, broadcast_id: int, action: str
) -> None:
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    actor_id = call.from_user.id
    key = (broadcast_id, chat_id, message_id)

    if action == "test":
        async with connect() as conn:
            row = await _load_broadcast(conn, broadcast_id)
        if not _draft_usable(row, actor_id):
            await call.answer(t(lang, "bc.expired"), show_alert=True)
            return
        try:
            await bot.copy_message(
                chat_id=actor_id, from_chat_id=int(row[4]), message_id=int(row[5]),
                reply_markup=_url_keyboard(row[6]),
            )
        except Exception as exc:
            logger.warning("broadcast %s test failed: %s", broadcast_id, exc)
            await call.answer(t(lang, "bc.test_failed"), show_alert=True)
            return
        async with connect() as conn:
            await log_bot_action(
                conn, actor_id=actor_id, action="broadcast.test", target_type="broadcast",
                target_id=broadcast_id,
            )
            await conn.commit()
        await call.answer(t(lang, "bc.test_sent"))
        return

    if action == "send":
        await _queue_draft(call, lang, broadcast_id)
        return

    if action == "drop":
        async with connect() as conn:
            row = await _load_broadcast(conn, broadcast_id)
            changed = None
            if row is not None and int(row[1]) == int(actor_id) and row[2] == "draft":
                changed = await set_broadcast_state(conn, broadcast_id, "cancel")
            if changed:
                await log_bot_action(
                    conn, actor_id=actor_id, action="broadcast.cancel", target_type="broadcast",
                    target_id=broadcast_id, payload={"from": changed[0], "to": changed[1]},
                )
            await conn.commit()
        if not changed:
            await call.answer(t(lang, "bc.expired"), show_alert=True)
            return
        await _edit(chat_id, message_id, t(lang, "admin.cancelled"))
        await call.answer()
        return

    if action in ("pause", "resume", "stopok"):
        state_action = "cancel" if action == "stopok" else action
        async with connect() as conn:
            row = await _load_broadcast(conn, broadcast_id)
            changed = None
            # Drafts are cancelled through "drop" by their author only.
            if row is not None and row[2] != "draft":
                changed = await set_broadcast_state(conn, broadcast_id, state_action)
            if changed:
                await log_bot_action(
                    conn, actor_id=actor_id, action=f"broadcast.{state_action}",
                    target_type="broadcast", target_id=broadcast_id,
                    payload={"from": changed[0], "to": changed[1]},
                )
            await conn.commit()
        _stop_pending.discard(key)
        status = await _render(chat_id, message_id, broadcast_id, lang)
        if not changed:
            await call.answer(t(lang, "bc.state_unchanged"), show_alert=True)
            return
        if status in ACTIVE_STATUSES and not _watching(key):
            _start_watcher(chat_id, message_id, broadcast_id, lang)
        await call.answer(t(lang, "bc.state_changed", status=_status_label(lang, changed[1])))
        return

    if action == "stop":
        _stop_pending.add(key)
        # _render drops the question again when the job already ended.
        if await _render(chat_id, message_id, broadcast_id, lang) is None:
            await call.answer(t(lang, "bc.expired"), show_alert=True)
            return
        await call.answer()
        return

    if action == "view":
        _stop_pending.discard(key)
        if await _render(chat_id, message_id, broadcast_id, lang) is None:
            await call.answer(t(lang, "bc.expired"), show_alert=True)
            return
        await call.answer()
        return

    if action == "open":
        card = await _card(broadcast_id, lang)
        if card is None:
            await call.answer(t(lang, "bc.expired"), show_alert=True)
            return
        text, status = card
        sent = await bot.send_message(chat_id, text, reply_markup=bc_progress_kb(lang, broadcast_id, status))
        if status in ACTIVE_STATUSES:
            _start_watcher(chat_id, sent.message_id, broadcast_id, lang)
        await call.answer()
        return

    await call.answer(t(lang, "bc.expired"), show_alert=True)


async def _queue_draft(call: CallbackQuery, lang: str, broadcast_id: int) -> None:
    """Queue a draft exactly once.

    The conditional ``UPDATE ... WHERE status = 'draft'`` is the claim: a
    second tap (or a concurrent one, which waits on the write lock) finds the
    row already queued and changes nothing.
    """
    chat_id = call.message.chat.id
    actor_id = call.from_user.id
    async with connect() as conn:
        row = await _load_broadcast(conn, broadcast_id)
        if row is not None and row[2] in ("queued", "running", "paused", "done"):
            await call.answer(t(lang, "bc.already_queued"), show_alert=True)
            return
        if not _draft_usable(row, actor_id):
            await call.answer(t(lang, "bc.expired"), show_alert=True)
            return
        cursor = await conn.execute(
            "UPDATE broadcasts SET status = 'queued' WHERE id = ? AND status = 'draft' AND actor_id = ?",
            (broadcast_id, actor_id),
        )
        if cursor.rowcount != 1:
            await conn.rollback()
            await call.answer(t(lang, "bc.already_queued"), show_alert=True)
            return
        total = await queue_broadcast(conn, broadcast_id, await broadcast_admin_ids(conn))
        if total == 0:
            await conn.rollback()
            await call.answer(t(lang, "bc.empty_segment"), show_alert=True)
            return
        segment = _target_segment(row[7])
        await log_bot_action(
            conn, actor_id=actor_id, action="broadcast.queue", target_type="broadcast",
            target_id=broadcast_id, payload={"total": total, "segment": segment},
        )
        await conn.commit()

    logger.info("broadcast %s queued by %s (%s users)", broadcast_id, actor_id, total)
    await call.answer(t(lang, "bc.queued", total=total))
    await _render(chat_id, call.message.message_id, broadcast_id, lang)
    _start_watcher(chat_id, call.message.message_id, broadcast_id, lang)
