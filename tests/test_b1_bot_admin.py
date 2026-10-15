"""Bot admin panel v2: permissions, the broadcast wizard, the progress card.

Updates go through a real aiogram ``Dispatcher`` with the admin router, so the
router filters (private chat, role from the ``admins`` table), the handler
order (admin+ handlers before the denial fallbacks) and the callback parsing
are exercised as in production. The ``Bot`` uses a recording session: no
request ever leaves the process. Synthetic ids only (900000000000+).
"""
from __future__ import annotations

import asyncio
import functools
import itertools
import json
import time
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, CopyMessage, EditMessageText, SendMessage
from aiogram.types import (
    CallbackQuery,
    Chat,
    InlineKeyboardMarkup,
    Message,
    MessageEntity,
    MessageId,
    PhotoSize,
    Sticker,
    Update,
    User,
)

from src.db.connection import connect as real_connect
from src.db.migrate import run_migrations
from src.filters import admin as admin_filter
from src.handlers import admin as admin_handlers
from src.i18n import t

OWNER = 900000000010
ADMIN = 900000000011
MODERATOR = 900000000012
VIEWER = 900000000013
STRANGER = 900000000099
TOKEN = "123456789:TEST-dummy-token-never-valid-on-telegram"

USERS_DDL = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    date INTEGER,
    lang TEXT,
    region TEXT,
    user_pro INTEGER NOT NULL DEFAULT 0,
    blocked INTEGER NOT NULL DEFAULT 0
)
"""
NOW = int(time.time())
# user_id, lang, pro, blocked
USERS = [
    (900000000101, "uz", 0, 0),
    (900000000102, "uz", 0, 1),  # blocked the bot: never a recipient
    (900000000103, "ru", 0, 0),
    (900000000104, "uz", 1, 0),
    (OWNER, "en", 0, 0),
    (ADMIN, "en", 0, 0),
]
UZ_RECIPIENTS = 2  # 101 and 104


# ─── fakes ──────────────────────────────────────────────────────────────────

class RecordingSession(BaseSession):
    """Records every Bot API call and returns a plausible result."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list = []
        self._ids = itertools.count(1000)
        self.fail_copy = False

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=next(self._ids),
                date=datetime.now(),
                chat=Chat(id=int(method.chat_id), type="private"),
                text=method.text,
            )
        if isinstance(method, CopyMessage):
            if self.fail_copy:
                from aiogram.exceptions import TelegramBadRequest

                raise TelegramBadRequest(method=method, message="message to copy not found")
            return MessageId(message_id=next(self._ids))
        return True

    async def close(self) -> None:
        pass

    async def stream_content(self, *args, **kwargs):  # pragma: no cover - unused
        yield b""

    def of(self, kind):
        return [r for r in self.requests if isinstance(r, kind)]


class Harness:
    def __init__(self, bot: Bot, dp: Dispatcher, session: RecordingSession, db_path) -> None:
        self.bot, self.dp, self.session, self.db_path = bot, dp, session, db_path
        self._update_ids = itertools.count(1)
        self._message_ids = itertools.count(50)

    def _user(self, user_id):
        return User(id=user_id, is_bot=False, first_name="Admin")

    def message(self, user_id, text=None, chat_type="private", **fields) -> Message:
        return Message(
            message_id=next(self._message_ids),
            date=datetime.now(),
            chat=Chat(id=user_id if chat_type == "private" else -100500, type=chat_type),
            from_user=self._user(user_id),
            text=text,
            **fields,
        )

    async def send(self, user_id, text=None, **kwargs):
        message = self.message(user_id, text, **kwargs)
        await self.dp.feed_update(self.bot, Update(update_id=next(self._update_ids), message=message))
        return message

    async def tap(self, user_id, data, message_id=777):
        call = CallbackQuery(
            id=str(next(self._update_ids)),
            from_user=self._user(user_id),
            chat_instance="ci",
            data=data,
            message=Message(
                message_id=message_id, date=datetime.now(),
                chat=Chat(id=user_id, type="private"), text="card",
            ),
        )
        await self.dp.feed_update(self.bot, Update(update_id=next(self._update_ids), callback_query=call))

    def last_answer(self) -> AnswerCallbackQuery:
        return self.session.of(AnswerCallbackQuery)[-1]

    def texts(self):
        return [r.text for r in self.session.of(SendMessage)]

    async def rows(self, sql, params=()):
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(sql, params)
            return await cursor.fetchall()

    async def audit(self, action=None):
        sql = "SELECT actor_id, action, target_id, payload_json FROM admin_audit_log"
        params = ()
        if action:
            sql += " WHERE action = ?"
            params = (action,)
        return await self.rows(sql + " ORDER BY id", params)

    async def nonce(self) -> str:
        state = FSMContext(self.dp.storage, StorageKey(bot_id=self.bot.id, chat_id=OWNER, user_id=OWNER))
        return (await state.get_data())["nonce"]


def _markups(session):
    for request in session.requests:
        markup = getattr(request, "reply_markup", None)
        if isinstance(markup, InlineKeyboardMarkup):
            yield markup


def _callback_data(markup: InlineKeyboardMarkup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data]


@pytest.fixture
async def harness(tmp_path):
    db_path = tmp_path / "bot_admin.sqlite3"
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(USERS_DDL)
        await conn.executemany(
            "INSERT INTO users (user_id, lang, user_pro, blocked, date) VALUES (?, ?, ?, ?, ?)",
            [(u, lang, pro, blocked, NOW) for u, lang, pro, blocked in USERS],
        )
        await conn.commit()
        await run_migrations(conn)
        await conn.executemany(
            "INSERT INTO admins (user_id, role, added_by, added_at, disabled) VALUES (?, ?, NULL, 0, 0)",
            [(OWNER, "owner"), (ADMIN, "admin"), (MODERATOR, "moderator"), (VIEWER, "viewer")],
        )
        await conn.commit()

    session = RecordingSession()
    bot = Bot(TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_handlers.router)
    bound = functools.partial(real_connect, str(db_path))
    with patch.object(admin_handlers, "connect", bound), patch.object(admin_filter, "connect", bound), \
            patch.object(admin_handlers, "bot", bot):
        yield Harness(bot, dp, session, db_path)
    admin_handlers.router._parent_router = None  # let the next test attach it again
    for task in list(admin_handlers._watchers.values()):
        task.cancel()
    admin_handlers._watchers.clear()
    admin_handlers._stop_pending.clear()


async def _wizard_to_audience(h: Harness, user_id=OWNER):
    await h.send(user_id, t("uz", "btn.admin.bc_new"))
    content = await h.send(
        user_id,
        photo=[PhotoSize(file_id="ph1", file_unique_id="u1", width=10, height=10)],
        caption="Yangi ish 🔥",
        caption_entities=[MessageEntity(type="custom_emoji", offset=10, length=2, custom_emoji_id="5368324170671202286")],
    )
    await h.send(user_id, "Batafsil | https://bandlik.uz/jobs")
    return content


async def _draft(h: Harness, segment="lang:uz", user_id=OWNER) -> int:
    content = await _wizard_to_audience(h, user_id)
    nonce = (await FSMContext(h.dp.storage, StorageKey(bot_id=h.bot.id, chat_id=user_id, user_id=user_id)).get_data())["nonce"]
    await h.tap(user_id, f"adm:w:{nonce}:seg:{segment}")
    rows = await h.rows("SELECT id FROM broadcasts ORDER BY id DESC LIMIT 1")
    return int(rows[0][0]), content


# ─── menu and permissions ───────────────────────────────────────────────────

async def test_admin_menu_has_the_mini_app_button(harness):
    await harness.send(OWNER, "/admin")
    sent = harness.session.of(SendMessage)
    assert sent[0].text == t("uz", "admin.hello")
    button = sent[1].reply_markup.inline_keyboard[0][0]
    assert button.web_app.url == "https://abitur24.uz/admin"
    labels = [b.text for row in sent[0].reply_markup.keyboard for b in row]
    assert t("uz", "btn.admin.ads") in labels


async def test_viewer_menu_hides_admin_actions(harness):
    await harness.send(VIEWER, "/admin")
    labels = [b.text for row in harness.session.of(SendMessage)[0].reply_markup.keyboard for b in row]
    assert t("uz", "btn.admin.stats") in labels
    assert t("uz", "btn.admin.ads") not in labels
    await harness.send(VIEWER, t("uz", "btn.admin.channels"))
    labels = [b.text for row in harness.session.of(SendMessage)[-1].reply_markup.keyboard for b in row]
    assert t("uz", "btn.admin.channel_add") not in labels
    assert t("uz", "btn.admin.channel_list") in labels


@pytest.mark.parametrize("user_id", [VIEWER, MODERATOR])
@pytest.mark.parametrize(
    "key", ["btn.admin.ads", "btn.admin.bc_new", "btn.admin.bc_list", "btn.admin.channel_add", "btn.admin.channel_del"]
)
async def test_admin_actions_are_denied_below_admin(harness, user_id, key):
    await harness.send(user_id, t("uz", key))
    assert harness.texts() == [t("uz", "admin.denied")]


@pytest.mark.parametrize("user_id", [VIEWER, MODERATOR, ADMIN, OWNER])
async def test_stats_are_viewer_plus(harness, user_id):
    await harness.send(user_id, t("uz", "btn.admin.stats"))
    assert harness.texts()[0].startswith(t("uz", "admin.stats.header"))


async def test_strangers_and_groups_get_nothing(harness):
    await harness.send(STRANGER, "/admin")
    await harness.send(STRANGER, t("uz", "btn.admin.stats"))
    await harness.send(OWNER, "/admin", chat_type="group")
    assert harness.session.requests == []


async def test_admin_role_can_open_the_wizard(harness):
    await harness.send(ADMIN, t("uz", "btn.admin.bc_new"))
    assert harness.texts() == [t("uz", "bc.prompt_content")]


@pytest.mark.parametrize("user_id", [VIEWER, MODERATOR, STRANGER])
async def test_callbacks_are_denied_below_admin(harness, user_id):
    await harness.tap(user_id, "adm:b:1:pause")
    answer = harness.last_answer()
    assert answer.text == t("uz", "admin.denied") and answer.show_alert is True


async def test_a_revoked_owner_loses_the_panel_on_the_next_message(harness):
    await harness.send(OWNER, "/admin")
    async with aiosqlite.connect(harness.db_path) as conn:
        await conn.execute("UPDATE admins SET disabled = 1 WHERE user_id = ?", (OWNER,))
        await conn.commit()
    before = len(harness.session.requests)
    await harness.send(OWNER, t("uz", "btn.admin.stats"))
    assert len(harness.session.requests) == before


# ─── wizard ─────────────────────────────────────────────────────────────────

async def test_wizard_rejects_unsupported_content_and_bad_buttons(harness):
    await harness.send(OWNER, t("uz", "btn.admin.bc_new"))
    await harness.send(
        OWNER,
        sticker=Sticker(file_id="s", file_unique_id="s", type="regular", width=1, height=1, is_animated=False, is_video=False),
    )
    assert harness.texts()[-1] == t("uz", "bc.bad_content")
    await harness.send(OWNER, "plain text broadcast")
    for bad in ("no separator", "Text | javascript:alert(1)", " | https://x.uz", "x" * 65 + " | https://x.uz", "Go | https://"):
        await harness.send(OWNER, bad)
        assert harness.texts()[-1] == t("uz", "bc.bad_button"), bad
    await harness.send(OWNER, "Go | https://x.uz")
    assert harness.texts()[-1] == t("uz", "bc.prompt_audience")


async def test_full_wizard_preview_count_then_queue_once(harness):
    broadcast_id, content = await _draft(harness)
    session = harness.session

    # Preview: the admin's own message copied back with its URL button.
    copies = session.of(CopyMessage)
    assert len(copies) == 1
    preview = copies[0]
    assert (preview.chat_id, preview.from_chat_id, preview.message_id) == (OWNER, OWNER, content.message_id)
    url_button = preview.reply_markup.inline_keyboard[0][0]
    assert (url_button.text, url_button.url) == ("Batafsil", "https://bandlik.uz/jobs")

    # The recipient count is shown before anything is queued.
    card = session.of(SendMessage)[-1]
    assert f"<b>{UZ_RECIPIENTS}</b>" in card.text
    assert t("uz", "bc.btn.send", count=UZ_RECIPIENTS) in [b.text for row in card.reply_markup.inline_keyboard for b in row]
    rows = await harness.rows("SELECT status, kind, target_json, buttons_json FROM broadcasts WHERE id = ?", (broadcast_id,))
    status, kind, target_json, buttons_json = rows[0]
    assert status == "draft" and kind == "forward"
    assert json.loads(target_json) == {"segment": "lang:uz", "exclude_blocked": True, "forward_mode": "copy"}
    assert json.loads(buttons_json) == [{"text": "Batafsil", "url": "https://bandlik.uz/jobs"}]
    assert await harness.rows("SELECT * FROM broadcast_targets") == []
    created = await harness.audit("broadcast.create")
    assert len(created) == 1 and json.loads(created[0][3])["source"] == "bot"
    assert json.loads(created[0][3])["count"] == UZ_RECIPIENTS

    # Test to me: one more copy, still a draft, audited.
    await harness.tap(OWNER, f"adm:b:{broadcast_id}:test")
    assert len(session.of(CopyMessage)) == 2
    assert session.of(CopyMessage)[-1].reply_markup.inline_keyboard[0][0].url == "https://bandlik.uz/jobs"
    assert (await harness.rows("SELECT status FROM broadcasts WHERE id = ?", (broadcast_id,)))[0][0] == "draft"
    assert len(await harness.audit("broadcast.test")) == 1

    # Confirm queues; the second tap queues nothing.
    await harness.tap(OWNER, f"adm:b:{broadcast_id}:send")
    assert harness.last_answer().text == t("uz", "bc.queued", total=UZ_RECIPIENTS)
    await harness.tap(OWNER, f"adm:b:{broadcast_id}:send")
    assert harness.last_answer().text == t("uz", "bc.already_queued")
    rows = await harness.rows("SELECT status, total FROM broadcasts WHERE id = ?", (broadcast_id,))
    assert rows[0] == ("queued", UZ_RECIPIENTS)
    targets = await harness.rows("SELECT user_id FROM broadcast_targets WHERE broadcast_id = ? ORDER BY user_id", (broadcast_id,))
    assert [r[0] for r in targets] == [900000000101, 900000000104]
    queued = await harness.audit("broadcast.queue")
    assert len(queued) == 1 and json.loads(queued[0][3]) == {"total": UZ_RECIPIENTS, "segment": "lang:uz", "source": "bot"}

    # Only the admin ever received a message: no copy went to a user.
    assert {c.chat_id for c in session.of(CopyMessage)} == {OWNER}
    for markup in _markups(session):
        assert all(len(d.encode()) <= 64 for d in _callback_data(markup))


async def test_concurrent_confirm_taps_queue_once(harness):
    broadcast_id, _ = await _draft(harness)
    await asyncio.gather(
        harness.tap(OWNER, f"adm:b:{broadcast_id}:send"),
        harness.tap(OWNER, f"adm:b:{broadcast_id}:send"),
    )
    assert len(await harness.audit("broadcast.queue")) == 1
    answers = sorted(a.text for a in harness.session.of(AnswerCallbackQuery)[-2:])
    assert answers == sorted([t("uz", "bc.queued", total=UZ_RECIPIENTS), t("uz", "bc.already_queued")])


async def test_dry_run_segment_targets_admins_only(harness):
    broadcast_id, _ = await _draft(harness, segment="test_admins")
    await harness.tap(OWNER, f"adm:b:{broadcast_id}:send")
    targets = await harness.rows("SELECT user_id FROM broadcast_targets WHERE broadcast_id = ? ORDER BY user_id", (broadcast_id,))
    assert [r[0] for r in targets] == [OWNER, ADMIN]  # the admins that are bot users


async def test_skip_button_and_empty_segment(harness):
    await harness.send(OWNER, t("uz", "btn.admin.bc_new"))
    await harness.send(OWNER, "hello")
    nonce = await harness.nonce()
    await harness.tap(OWNER, f"adm:w:{nonce}:skip")
    async with aiosqlite.connect(harness.db_path) as conn:
        await conn.execute("UPDATE users SET user_pro = 0")
        await conn.commit()
    await harness.tap(OWNER, f"adm:w:{nonce}:seg:pro")
    assert harness.last_answer().text == t("uz", "bc.empty_segment")
    assert await harness.rows("SELECT * FROM broadcasts") == []
    assert await harness.audit() == []
    # Still on the audience step: another segment works, without a button.
    await harness.tap(OWNER, f"adm:w:{nonce}:seg:all")
    rows = await harness.rows("SELECT buttons_json FROM broadcasts")
    assert json.loads(rows[0][0]) == []
    assert harness.session.of(CopyMessage)[-1].reply_markup is None


async def test_stale_wizard_taps_are_safe(harness):
    await _wizard_to_audience(harness)
    nonce = await harness.nonce()
    await harness.tap(OWNER, "adm:w:deadbeef:seg:all")  # wrong nonce
    assert harness.last_answer().text == t("uz", "bc.expired")
    await harness.tap(OWNER, f"adm:w:{nonce}:skip")  # not the button step any more
    assert harness.last_answer().text == t("uz", "bc.expired")
    await harness.tap(OWNER, f"adm:w:{nonce}:seg:region:1703")  # not offered by the wizard
    assert harness.last_answer().text == t("uz", "bc.expired")
    await harness.tap(OWNER, f"adm:w:{nonce}:seg:all")
    await harness.tap(OWNER, f"adm:w:{nonce}:seg:all")  # double tap on the picker
    assert len(await harness.rows("SELECT id FROM broadcasts")) == 1
    assert harness.last_answer().text == t("uz", "bc.expired")


async def test_expired_or_foreign_draft_cannot_be_sent(harness):
    broadcast_id, _ = await _draft(harness)
    await harness.tap(ADMIN, f"adm:b:{broadcast_id}:send")  # not the author
    assert harness.last_answer().text == t("uz", "bc.expired")
    async with aiosqlite.connect(harness.db_path) as conn:
        await conn.execute(
            "UPDATE broadcasts SET created_at = ? WHERE id = ?",
            (NOW - admin_handlers.DRAFT_TTL_SECONDS - 5, broadcast_id),
        )
        await conn.commit()
    await harness.tap(OWNER, f"adm:b:{broadcast_id}:send")
    assert harness.last_answer().text == t("uz", "bc.expired")
    await harness.tap(OWNER, f"adm:b:{broadcast_id}:test")
    assert harness.last_answer().text == t("uz", "bc.expired")
    assert (await harness.rows("SELECT status FROM broadcasts"))[0][0] == "draft"
    assert await harness.audit("broadcast.queue") == []


async def test_drop_cancels_the_draft(harness):
    broadcast_id, _ = await _draft(harness)
    await harness.tap(OWNER, f"adm:b:{broadcast_id}:drop")
    assert (await harness.rows("SELECT status FROM broadcasts"))[0][0] == "cancelled"
    cancelled = await harness.audit("broadcast.cancel")
    assert len(cancelled) == 1 and json.loads(cancelled[0][3])["from"] == "draft"
    await harness.tap(OWNER, f"adm:b:{broadcast_id}:send")
    assert harness.last_answer().text == t("uz", "bc.expired")
    assert await harness.rows("SELECT * FROM broadcast_targets") == []


async def test_a_failed_preview_cancels_the_draft(harness):
    await _wizard_to_audience(harness)
    nonce = await harness.nonce()
    harness.session.fail_copy = True
    await harness.tap(OWNER, f"adm:w:{nonce}:seg:all")
    assert harness.texts()[-1] == t("uz", "bc.preview_failed")
    assert (await harness.rows("SELECT status FROM broadcasts"))[0][0] == "cancelled"


async def test_queue_and_audit_share_one_transaction(harness):
    broadcast_id, _ = await _draft(harness)
    async with aiosqlite.connect(harness.db_path) as conn:
        await conn.execute("DROP TABLE admin_audit_log")
        await conn.commit()
    with pytest.raises(Exception):
        await harness.dp.feed_update(
            harness.bot,
            Update(update_id=999, callback_query=CallbackQuery(
                id="x", from_user=User(id=OWNER, is_bot=False, first_name="A"), chat_instance="ci",
                data=f"adm:b:{broadcast_id}:send",
                message=Message(message_id=1, date=datetime.now(), chat=Chat(id=OWNER, type="private")),
            )),
        )
    assert (await harness.rows("SELECT status FROM broadcasts"))[0][0] == "draft"
    assert await harness.rows("SELECT * FROM broadcast_targets") == []


# ─── progress card ──────────────────────────────────────────────────────────

async def _queued(harness, user_id=OWNER) -> int:
    broadcast_id, _ = await _draft(harness, user_id=user_id)
    await harness.tap(user_id, f"adm:b:{broadcast_id}:send")
    return broadcast_id


async def _status(harness, broadcast_id):
    return (await harness.rows("SELECT status FROM broadcasts WHERE id = ?", (broadcast_id,)))[0][0]


async def test_pause_resume_stop_from_the_card(harness):
    broadcast_id = await _queued(harness)
    card = harness.session.of(EditMessageText)[-1]
    assert _callback_data(card.reply_markup)[:2] == [f"adm:b:{broadcast_id}:pause", f"adm:b:{broadcast_id}:stop"]

    await harness.tap(OWNER, f"adm:b:{broadcast_id}:pause")
    assert await _status(harness, broadcast_id) == "paused"
    edited = harness.session.of(EditMessageText)[-1]
    assert _callback_data(edited.reply_markup)[0] == f"adm:b:{broadcast_id}:resume"

    await harness.tap(OWNER, f"adm:b:{broadcast_id}:pause")  # already paused
    assert harness.last_answer().text == t("uz", "bc.state_unchanged")

    await harness.tap(ADMIN, f"adm:b:{broadcast_id}:resume")  # any admin+ may control it
    assert await _status(harness, broadcast_id) == "queued"

    await harness.tap(OWNER, f"adm:b:{broadcast_id}:stop")  # asks first
    assert await _status(harness, broadcast_id) == "queued"
    asked = harness.session.of(EditMessageText)[-1]
    assert _callback_data(asked.reply_markup) == [f"adm:b:{broadcast_id}:stopok", f"adm:b:{broadcast_id}:view"]

    await harness.tap(OWNER, f"adm:b:{broadcast_id}:stopok")
    assert await _status(harness, broadcast_id) == "cancelled"
    assert harness.session.of(EditMessageText)[-1].reply_markup is None

    actions = [(row[0], row[1]) for row in await harness.audit() if row[1].startswith("broadcast.") and row[1] not in ("broadcast.create", "broadcast.queue")]
    assert actions == [(OWNER, "broadcast.pause"), (ADMIN, "broadcast.resume"), (OWNER, "broadcast.cancel")]
    for row in await harness.audit("broadcast.pause"):
        assert json.loads(row[3]) == {"from": "queued", "to": "paused", "source": "bot"}


async def test_a_revoked_admin_tapping_a_stale_card_changes_nothing(harness):
    broadcast_id = await _queued(harness, user_id=ADMIN)
    async with aiosqlite.connect(harness.db_path) as conn:
        await conn.execute("UPDATE admins SET disabled = 1 WHERE user_id = ?", (ADMIN,))
        await conn.commit()
    audit_before = await harness.audit()
    for action in ("pause", "stopok", "resume"):
        await harness.tap(ADMIN, f"adm:b:{broadcast_id}:{action}")
        answer = harness.last_answer()
        assert answer.text == t("uz", "admin.denied") and answer.show_alert is True
    assert await _status(harness, broadcast_id) == "queued"
    assert await harness.audit() == audit_before


async def test_a_demoted_admin_cannot_control_a_broadcast(harness):
    broadcast_id = await _queued(harness, user_id=ADMIN)
    async with aiosqlite.connect(harness.db_path) as conn:
        await conn.execute("UPDATE admins SET role = 'moderator' WHERE user_id = ?", (ADMIN,))
        await conn.commit()
    await harness.tap(ADMIN, f"adm:b:{broadcast_id}:pause")
    assert harness.last_answer().text == t("uz", "admin.denied")
    assert await _status(harness, broadcast_id) == "queued"


async def test_the_watcher_follows_the_job_to_the_end(harness, monkeypatch):
    monkeypatch.setattr(admin_handlers, "PROGRESS_POLL_SECONDS", 0.01)
    broadcast_id = await _queued(harness)
    watcher = admin_handlers._watchers[broadcast_id]
    async with aiosqlite.connect(harness.db_path) as conn:
        await conn.execute(
            "UPDATE broadcasts SET status = 'done', sent = 2 WHERE id = ?", (broadcast_id,)
        )
        await conn.commit()
    await asyncio.wait_for(watcher, timeout=2)
    last = harness.session.of(EditMessageText)[-1]
    assert t("uz", "admin.finished", total=UZ_RECIPIENTS, ok=2, fail=0) in last.text
    assert last.reply_markup is None


async def test_broadcast_list_shows_the_last_five(harness):
    async with aiosqlite.connect(harness.db_path) as conn:
        for i in range(7):
            await conn.execute(
                "INSERT INTO broadcasts (actor_id, status, kind, created_at, total, sent) VALUES (?, ?, 'forward', ?, 10, ?)",
                (OWNER, "done" if i % 2 else "paused", NOW, i),
            )
        await conn.commit()
    await harness.send(OWNER, t("uz", "btn.admin.bc_list"))
    message = harness.session.of(SendMessage)[-1]
    data = _callback_data(message.reply_markup)
    assert data == [f"adm:b:{i}:open" for i in (7, 6, 5, 4, 3)]
    assert t("uz", "bc.list_row", id=7, status=t("uz", "bc.status.paused"), done=6, total=10) in message.text

    await harness.tap(OWNER, "adm:b:6:open")  # finished: card without controls, no watcher
    assert harness.session.of(SendMessage)[-1].reply_markup is None
    assert 6 not in admin_handlers._watchers
    await harness.tap(OWNER, "adm:b:7:open")  # paused: resume control and a watcher
    assert _callback_data(harness.session.of(SendMessage)[-1].reply_markup)[0] == "adm:b:7:resume"
    assert 7 in admin_handlers._watchers


# ─── channels (handlers called directly; Telegram lookups mocked) ──────────

class _State:
    def __init__(self):
        self.clear = AsyncMock()


def _channel_message(text, user_id=OWNER):
    return SimpleNamespace(
        text=text, from_user=SimpleNamespace(id=user_id), reply=AsyncMock(), forward_from_chat=None,
    )


async def test_channel_add_and_delete_are_audited(harness):
    fake_bot = SimpleNamespace(
        id=1,
        get_chat=AsyncMock(return_value=SimpleNamespace(id=-1001234, title="Ish <b>", username="ishkanal", invite_link=None)),
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")),
    )
    async with aiosqlite.connect(harness.db_path) as conn:
        await conn.execute(
            "INSERT INTO subscription_checks (user_id, ok, checked_at) VALUES (900000000101, 1, 0)"
        )
        await conn.commit()
    with patch.object(admin_handlers, "bot", fake_bot):
        message = _channel_message("@ishkanal")
        await admin_handlers.channel_add_process(message, _State(), lang="uz", admin_role="owner")
    assert message.reply.call_args.args[0] == t("uz", "admin.channel_added")
    assert await harness.rows("SELECT id, chat_id, added_by FROM channels") == [("@ishkanal", -1001234, OWNER)]
    added = await harness.audit("channels.add")
    assert len(added) == 1 and added[0][2] == "@ishkanal"
    assert json.loads(added[0][3]) == {"chat_id": -1001234, "title": "Ish <b>", "source": "bot"}

    message = _channel_message("@ishkanal")
    await admin_handlers.channel_delete_process(message, _State(), lang="uz", admin_role="owner")
    assert message.reply.call_args.args[0] == t("uz", "admin.channel_deleted")
    assert await harness.rows("SELECT id FROM channels") == []
    assert await harness.rows("SELECT * FROM subscription_checks") == []
    deleted = await harness.audit("channels.delete")
    assert len(deleted) == 1 and deleted[0][:3] == (OWNER, "channels.delete", "@ishkanal")


async def test_channel_add_rolls_back_without_its_audit_row(harness):
    fake_bot = SimpleNamespace(
        id=1,
        get_chat=AsyncMock(return_value=SimpleNamespace(id=-1005, title="T", username="kanal2", invite_link=None)),
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status="administrator")),
    )
    async with aiosqlite.connect(harness.db_path) as conn:
        await conn.execute("DROP TABLE admin_audit_log")
        await conn.commit()
    with patch.object(admin_handlers, "bot", fake_bot), pytest.raises(Exception):
        await admin_handlers.channel_add_process(_channel_message("@kanal2"), _State(), lang="uz", admin_role="owner")
    assert await harness.rows("SELECT id FROM channels") == []


async def test_channel_steps_are_denied_to_a_demoted_admin_mid_flow(harness):
    await harness.send(ADMIN, t("uz", "btn.admin.channel_add"))
    assert harness.texts()[-1] == t("uz", "admin.channel_add_prompt")
    async with aiosqlite.connect(harness.db_path) as conn:
        await conn.execute("UPDATE admins SET role = 'viewer' WHERE user_id = ?", (ADMIN,))
        await conn.commit()
    await harness.send(ADMIN, "@ishkanal")
    assert harness.texts()[-1] == t("uz", "admin.denied")
    assert await harness.rows("SELECT id FROM channels") == []


def test_admin_webapp_url_targets_the_spa_admin_route():
    assert admin_handlers.admin_webapp_url() == "https://abitur24.uz/admin"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Batafsil | https://bandlik.uz", {"text": "Batafsil", "url": "https://bandlik.uz"}),
        ("A|http://x.uz/a?b=1", {"text": "A", "url": "http://x.uz/a?b=1"}),
        ("A | tg://resolve?domain=x", None),
        ("A | https://x.uz/with space", None),
        ("x" * 64 + " | https://x.uz", {"text": "x" * 64, "url": "https://x.uz"}),
        (None, None),
    ],
)
def test_parse_button(raw, expected):
    assert admin_handlers.parse_button(raw) == expected
