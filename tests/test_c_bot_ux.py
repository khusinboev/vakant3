"""Bot UX: /start layout, /lang, referral share button, "open in app" buttons,
channel posts with plain emoji, menu button / commands at startup.

Handlers run through a real aiogram ``Dispatcher`` with a recording Bot
session (``tests/test_b1_bot_admin.py``): nothing leaves the process.
Synthetic ids only (900000000000+).
"""
from __future__ import annotations

import functools
import json
import os
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import aiosqlite
import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import EditMessageText, SendMessage
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

from src.buttons.buttuns import button_text
from src.db.connection import connect as real_connect
from src.db.migrate import run_migrations
from src.filters import admin as admin_filter
from src.functions import bot_setup, main_menu
from src.functions.webapp_link import verify_bot_link
from src.handlers import admin as admin_handlers
from src.functions import notification_scheduler as notif
from src.functions.auto_post_scheduler import pick_and_post
from src.handlers import content as content_handlers
from src.handlers import start as start_handlers
from src.i18n import LANGS, t
from src.ui.emoji import ICONS
from tests import test_autopost_admin as ap
from tests import test_b1_bot_admin as b1

USER = 900000000201
STAFF = 900000000202  # a viewer in the admins table
WEBAPP = "https://abitur24.uz/app"
DETAIL = {"title": "Dasturchi <senior>", "company": {"name": "Acme"}, "min_salary": 5000000}

harness = b1.harness  # admin router harness (for the back-button check)


@pytest.fixture
def premium(monkeypatch):
    monkeypatch.setenv("BOT_PREMIUM_EMOJI", "1")


@pytest.fixture
async def ux(tmp_path):
    db_path = tmp_path / "ux.sqlite3"
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(b1.USERS_DDL)
        await conn.execute("ALTER TABLE users ADD COLUMN started_at INTEGER")
        await conn.execute("INSERT INTO users (user_id, lang, date) VALUES (?, 'uz', ?)", (USER, int(time.time())))
        await conn.execute("INSERT INTO users (user_id, lang, date) VALUES (?, 'uz', ?)", (STAFF, int(time.time())))
        await conn.commit()
        await run_migrations(conn)
        await conn.execute(
            "INSERT INTO admins (user_id, role, added_by, added_at, disabled) VALUES (?, 'viewer', NULL, 0, 0)",
            (STAFF,),
        )
        await conn.commit()

    session = b1.RecordingSession()
    bot = Bot(b1.TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_handlers.router)
    dp.include_router(start_handlers.router)
    dp.include_router(content_handlers.router)
    bound = functools.partial(real_connect, str(db_path))
    gate = {"unlocked": True, "ref_link": f"https://t.me/bandlikuzbot?start=ref_{USER}", "current": 0, "required": 0}
    admin_filter.reset_admin_candidates()
    with patch.object(start_handlers, "connect", bound), patch.object(start_handlers, "bot", bot), \
            patch.object(main_menu, "connect", bound), patch.object(admin_filter, "connect", bound), \
            patch.object(admin_handlers, "connect", bound), patch.object(admin_handlers, "bot", bot), \
            patch.object(start_handlers.functions, "check_on_start", AsyncMock(return_value=True)), \
            patch.object(start_handlers, "get_referral_gate_state", AsyncMock(side_effect=lambda _uid: dict(gate))), \
            patch.object(start_handlers, "fetch_osonish_detail", AsyncMock(return_value=DETAIL)), \
            patch.object(content_handlers, "get_articles", AsyncMock(return_value=[{"id": "a1", "title": "Ta'til"}])):
        h = b1.Harness(bot, dp, session, db_path)
        h.gate = gate
        yield h
    start_handlers.router._parent_router = None
    content_handlers.router._parent_router = None
    admin_handlers.router._parent_router = None
    admin_filter.reset_admin_candidates()


def _inline(markup):
    assert isinstance(markup, InlineKeyboardMarkup)
    return [b for row in markup.inline_keyboard for b in row]


# ─── /start ─────────────────────────────────────────────────────────────────

def _rows(markup):
    assert isinstance(markup, ReplyKeyboardMarkup)
    return markup.keyboard


async def test_start_is_one_message_with_the_persistent_signed_keyboard(ux):
    await ux.send(USER, "/start")
    sent = ux.session.of(SendMessage)
    assert len(sent) == 1  # greeting + keyboard in ONE message, no inline app prompt
    greeting = sent[0]
    assert "<b>Admin</b>" in greeting.text and "{e:" not in greeting.text
    kb = greeting.reply_markup
    rows = _rows(kb)
    assert kb.is_persistent and kb.resize_keyboard
    (jobs,), (profile, saves), (laws, hr) = rows  # no admin row for an ordinary user
    assert [b.text for b in (jobs, profile, saves, laws, hr)] == [
        button_text("uz", k) for k in ("start.btn.jobs", "start.btn.profile", "start.btn.saves", "menu.laws", "menu.hr")
    ]
    assert jobs.style == "primary" and laws.web_app is None and hr.web_app is None
    secret = os.environ["WEBAPP_SECRET"]
    for button, go in ((jobs, None), (profile, "profile"), (saves, "saves")):
        parsed = urlparse(button.web_app.url)
        query = parse_qs(parsed.query)
        assert (parsed.scheme, parsed.netloc, parsed.path) == ("https", "abitur24.uz", "/app")
        assert query.get("go", [None])[0] == go
        link = verify_bot_link(query["bt"][0], secret=secret)
        assert link is not None and link.user_id == USER  # signed for THIS user
    rows_db = await ux.rows("SELECT started_at, kb_sent_at FROM users WHERE user_id = ?", (USER,))
    assert rows_db[0][0] and rows_db[0][1]


async def test_staff_get_a_last_admin_row_that_ordinary_users_never_see(ux):
    await ux.send(STAFF, "/start")
    rows = _rows(ux.session.of(SendMessage)[-1].reply_markup)
    assert len(rows) == 4 and [b.text for b in rows[-1]] == [button_text("uz", "menu.admin")]
    assert rows[-1][0].web_app is None
    await ux.send(USER, "/start")
    assert len(_rows(ux.session.of(SendMessage)[-1].reply_markup)) == 3


async def test_admin_button_opens_the_panel_and_exit_restores_the_main_keyboard(ux):
    await ux.send(STAFF, button_text("uz", "menu.admin"))
    hello, hint = ux.session.of(SendMessage)[-2:]
    assert hello.text == t("uz", "admin.hello")
    labels = [b.text for row in _rows(hello.reply_markup) for b in row]
    assert labels[-1] == button_text("uz", "btn.admin.exit")
    assert hint.reply_markup.inline_keyboard[0][0].web_app.url == "https://abitur24.uz/admin"
    await ux.send(STAFF, button_text("uz", "btn.admin.exit"))
    back = ux.session.of(SendMessage)[-1]
    assert back.text == t("uz", "admin.main_menu")
    assert [b.text for b in _rows(back.reply_markup)[-1]] == [button_text("uz", "menu.admin")]
    assert _rows(back.reply_markup)[0][0].web_app is not None


async def test_a_non_admin_typing_the_admin_label_gets_nothing_from_the_panel(ux):
    for text in (t("uz", "menu.admin"), button_text("uz", "menu.admin"), "/admin"):
        await ux.send(USER, text)
    assert ux.session.of(SendMessage) == []  # no panel, no leak of the admin menu


async def test_stale_keyboards_are_refreshed_on_the_next_laws_tap(ux):
    async def sent_before_content():
        await ux.send(USER, t("uz", "menu.laws"))
        texts = [m.text for m in ux.session.of(SendMessage)]
        ux.session.requests.clear()
        return texts

    # never sent with signed links (NULL): refreshed, then the content follows
    assert await sent_before_content() == [t("uz", "menu.refreshed"), t("uz", "content.laws.header")]
    assert await sent_before_content() == [t("uz", "content.laws.header")]  # fresh now
    week_ago = int(time.time()) - main_menu.REFRESH_AFTER_SECONDS - 5
    async with aiosqlite.connect(ux.db_path) as conn:
        await conn.execute("UPDATE users SET kb_sent_at = ? WHERE user_id = ?", (week_ago, USER))
        await conn.commit()
    assert await sent_before_content() == [t("uz", "menu.refreshed"), t("uz", "content.laws.header")]
    recent = int(time.time()) - main_menu.REFRESH_AFTER_SECONDS + 3600
    async with aiosqlite.connect(ux.db_path) as conn:
        await conn.execute("UPDATE users SET kb_sent_at = ? WHERE user_id = ?", (recent, USER))
        await conn.commit()
    assert await sent_before_content() == [t("uz", "content.laws.header")]


async def test_start_escapes_the_first_name(ux):
    ux._user = lambda uid: b1.User(id=uid, is_bot=False, first_name="<i>x</i>")
    await ux.send(USER, "/start")
    assert "<b>&lt;i&gt;x&lt;/i&gt;</b>" in ux.session.of(SendMessage)[0].text


async def test_start_with_premium_uses_custom_emoji_and_bare_labels(ux, premium):
    await ux.send(USER, "/start")
    (greeting,) = ux.session.of(SendMessage)
    assert f'<tg-emoji emoji-id="{ICONS["wave"].id}">' in greeting.text
    (jobs,), (_, _), (laws, _) = _rows(greeting.reply_markup)
    assert (laws.text, laws.icon_custom_emoji_id) == (t("uz", "menu.laws"), ICONS["laws"].id)
    assert (jobs.text, jobs.icon_custom_emoji_id) == (t("uz", "start.btn.jobs"), ICONS["search"].id)
    # A tap on that custom-icon button sends the bare label: it still routes.
    await ux.send(USER, t("uz", "menu.laws"))
    assert ux.session.of(SendMessage)[-1].text == t("uz", "content.laws.header")


async def test_locked_referral_gate_offers_a_share_button(ux):
    ux.gate.update(unlocked=False, required=3, current=1)
    await ux.send(USER, "/start")
    sent = ux.session.of(SendMessage)
    assert len(sent) == 1
    share = _inline(sent[0].reply_markup)[0]
    parsed = urlparse(share.url)
    assert (parsed.netloc, parsed.path) == ("t.me", "/share/url")
    query = parse_qs(parsed.query)
    assert query["url"] == [ux.gate["ref_link"]]
    assert query["text"] == [t("uz", "referral.share_text")]
    assert "start%3Dref_" in share.url  # the ref link itself is url-encoded
    assert "1/3" in sent[0].text


async def test_vacancy_deeplink_has_an_open_in_app_button(ux, premium):
    await ux.send(USER, "/start vacancy_osonish_123")
    card = ux.session.of(SendMessage)[-1]
    assert "Dasturchi &lt;senior&gt;" in card.text
    assert '<tg-emoji emoji-id="' in card.text  # private chat: premium emoji allowed
    button = _inline(card.reply_markup)[0]
    assert button.web_app.url == f"{WEBAPP}?go=vacancy_osonish_123" and button.style == "primary"


# ─── /lang ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("lang", ["ru", "en"])
async def test_language_change_resends_the_menu_in_the_new_language(ux, lang):
    await ux.tap(USER, f"lang:{lang}")
    edit = ux.session.of(EditMessageText)[-1]
    assert edit.text == t(lang, "lang.saved")
    (greeting,) = ux.session.of(SendMessage)
    assert greeting.text == t(lang, "start.greeting", name="Admin")
    rows = _rows(greeting.reply_markup)
    assert [b.text for b in rows[2]] == [button_text(lang, "menu.laws"), button_text(lang, "menu.hr")]
    assert rows[0][0].text == button_text(lang, "start.btn.jobs")
    rows = await ux.rows("SELECT lang FROM users WHERE user_id = ?", (USER,))
    assert rows[0][0] == lang


@pytest.mark.parametrize("lang", LANGS)
async def test_reply_keyboard_taps_route_in_every_language(ux, lang):
    for text in (t(lang, "menu.laws"), button_text(lang, "menu.laws"), f"⚖️ {t(lang, 'menu.laws')}"):
        await ux.send(USER, text)
        assert ux.session.of(SendMessage)[-1].text == t("uz", "content.laws.header")


async def test_admin_back_works_in_russian(harness):
    """ru "Назад" is both common.back and btn.admin.back: the exact-match
    reverse lookup would return common.back and miss the cancel."""
    from src.handlers import admin as admin_handlers

    for lang in LANGS:
        for text in (t(lang, "btn.admin.back"), button_text(lang, "btn.admin.back"), f"🔙{t(lang, 'btn.admin.back')}"):
            assert admin_handlers._is_back(SimpleNamespace(text=text)), (lang, text)
    assert not admin_handlers._is_back(SimpleNamespace(text="@some_channel"))
    await harness.send(b1.ADMIN, t("uz", "btn.admin.channel_add"))
    await harness.send(b1.ADMIN, t("ru", "btn.admin.back"))
    assert harness.session.of(SendMessage)[-1].text == t("uz", "admin.main_menu")


# ─── notifications and channel posts ────────────────────────────────────────

async def test_notification_has_an_open_in_app_button(premium):
    mock_bot = AsyncMock()
    with patch.object(notif, "bot", mock_bot):
        assert await notif._send_notification(USER, "en", "osonish_7", DETAIL) == "sent"
    kwargs = mock_bot.send_message.call_args.kwargs
    assert kwargs["text"].startswith(f'<tg-emoji emoji-id="{ICONS["bell"].id}">')
    button = _inline(kwargs["reply_markup"])[0]
    # Opens this vacancy's detail sheet in the Mini App, not just the app.
    assert button.web_app.url == f"{WEBAPP}?go=vacancy_osonish_7"
    assert (button.text, button.icon_custom_emoji_id) == (t("en", "start.btn.open_app"), ICONS["app"].id)


async def test_channel_post_is_plain_and_links_back_to_the_bot(tmp_path, premium):
    conn = await ap._migrated_conn(tmp_path)
    await ap._add_auto_post_tables(conn)
    await conn.execute(
        "INSERT INTO vacancy_cache (uid, data_json, expires_at) VALUES (?, ?, ?)",
        ("osonish_42", json.dumps(DETAIL), int(time.time()) + 3600),
    )
    await conn.commit()
    mock_bot = AsyncMock()
    mock_bot.send_message.return_value = SimpleNamespace(message_id=9)
    try:
        with patch("src.functions.auto_post_scheduler.bot", mock_bot):
            result = await pick_and_post(conn, channel="@ch", min_salary=0, lang="ru")
    finally:
        await conn.close()
    assert result["status"] == "sent"
    kwargs = mock_bot.send_message.call_args.kwargs
    assert "tg-emoji" not in kwargs["text"] and "💼" in kwargs["text"]
    button = _inline(kwargs["reply_markup"])[0]
    assert button.url == "https://t.me/bandlikuzbot?start=vacancy_osonish_42"
    assert button.icon_custom_emoji_id is None
    assert button.text == f"{ICONS['job'].fallback} {t('ru', 'start.btn.open_in_bot')}"  # job has a custom id: plain mode matters
    assert button.web_app is None  # web_app buttons do not work in channels


def test_weekly_channel_stats_keys_carry_no_premium_tokens():
    from src.i18n.en import STRINGS as EN
    from src.i18n.ru import STRINGS as RU
    from src.i18n.uz import STRINGS as UZ

    for d in (UZ, RU, EN):
        for key, value in d.items():
            if key.startswith(("stats.", "chart.")):
                assert "{e:" not in value, key


# ─── startup: menu button and commands ──────────────────────────────────────

class _SetupBot:
    def __init__(self, fail=()):
        self.calls: list[tuple[str, dict]] = []
        self.fail = set(fail)

    async def _record(self, name, kwargs):
        self.calls.append((name, kwargs))
        if name in self.fail or kwargs.get("language_code") in self.fail:
            raise RuntimeError("telegram says no")
        return True

    def set_chat_menu_button(self, **kwargs):
        return self._record("menu", kwargs)

    def set_my_commands(self, **kwargs):
        return self._record("commands", kwargs)


async def test_setup_sets_menu_button_and_commands_per_language(tmp_path):
    db_path = tmp_path / "setup.sqlite3"
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(b1.USERS_DDL)
        await conn.execute("INSERT INTO users (user_id, lang) VALUES (?, 'ru')", (b1.OWNER,))
        await conn.commit()
        await run_migrations(conn)
        await conn.execute("INSERT INTO admins (user_id, role, added_by, added_at, disabled) VALUES (?, 'owner', NULL, 0, 0)", (b1.OWNER,))
        await conn.execute("INSERT INTO admins (user_id, role, added_by, added_at, disabled) VALUES (?, 'admin', NULL, 0, 1)", (b1.ADMIN,))
        await conn.commit()
    fake = _SetupBot()
    with patch.object(bot_setup, "connect", functools.partial(real_connect, str(db_path))):
        result = await bot_setup.setup_bot_ui(fake, WEBAPP, admin_ids=[])
    assert result == {"ok": 5, "failed": 0}
    menu = fake.calls[0][1]["menu_button"]
    assert menu.type == "web_app" and menu.web_app.url == WEBAPP
    user_lists = [kw for name, kw in fake.calls if name == "commands" and kw["scope"].type == "default"]
    assert [kw["language_code"] for kw in user_lists] == [None, "ru", "en"]
    assert [c.command for c in user_lists[1]["commands"]] == ["start", "lang"]
    assert user_lists[1]["commands"][1].description == t("ru", "cmd.lang")
    admin_lists = [kw for name, kw in fake.calls if name == "commands" and kw["scope"].type == "chat"]
    assert [kw["scope"].chat_id for kw in admin_lists] == [b1.OWNER]  # the disabled admin gets none
    assert [c.command for c in admin_lists[0]["commands"]] == ["start", "lang", "admin"]
    assert admin_lists[0]["commands"][2].description == t("ru", "cmd.admin")


async def test_setup_failures_are_logged_never_raised(tmp_path):
    fake = _SetupBot(fail={"menu", "ru"})

    def broken_connect():
        raise RuntimeError("db down")

    with patch.object(bot_setup, "connect", broken_connect):
        result = await bot_setup.setup_bot_ui(fake, WEBAPP, admin_ids=[b1.OWNER])
    assert result == {"ok": 2, "failed": 2}



def test_vacancy_app_url_is_a_valid_start_param_or_the_plain_app():
    import re

    from src.functions.vacancy_format import vacancy_app_url

    url = vacancy_app_url("osonish_900000000123")
    assert url == f"{WEBAPP}?go=vacancy_osonish_900000000123"
    go = url.split("?go=", 1)[1]
    # Same value must also work as a Telegram start_param.
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", go)
    for bad in ("", "osonish_", "osonish_12a", "hh_5", "osonish_1&go=admin", "osonish_" + "9" * 16):
        assert vacancy_app_url(bad) == WEBAPP, bad
