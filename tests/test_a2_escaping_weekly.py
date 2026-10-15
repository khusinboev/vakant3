"""HTML escaping in admin/content handlers and the weekly stats scheduler."""
from __future__ import annotations

import functools
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core.timeutil import TZ, week_key
from src.db.connection import connect
from src.db.migrate import run_migrations
from src.db.settings import ensure_settings_columns, invalidate_settings_cache
from src.functions import weekly_stats_scheduler as ws
from src.functions.stats_chart import WeeklyStats
from src.handlers import admin as admin_handlers
from src.handlers import content

EVIL = "<b>x</b> & <a href='javascript:alert(1)'>y</a>"


# ─── admin.channel_add_process ──────────────────────────────────────────────

class _Message:
    def __init__(self, text):
        self.text = text
        self.forward_from_chat = None
        self.reply = AsyncMock()


class _State:
    def __init__(self):
        self.clear = AsyncMock()


async def _run_channel_add(text, bot):
    message = _Message(text)
    with patch.object(admin_handlers, "bot", bot), patch.object(
        admin_handlers, "parse_channel_link",
        return_value=SimpleNamespace(kind="username", target="@evil", username="evil"),
    ):
        await admin_handlers.channel_add_process(message, _State(), lang="uz")
    return message.reply.call_args.args[0]


async def test_raw_channel_input_is_escaped_when_lookup_fails():
    bot = SimpleNamespace(id=1, get_chat=AsyncMock(side_effect=RuntimeError("no chat")))
    reply = await _run_channel_add("@evil<i>", bot)
    assert "<i>" not in reply and "@evil&lt;i&gt;" in reply


async def test_chat_title_is_escaped_when_the_bot_is_not_admin():
    bot = SimpleNamespace(
        id=1,
        get_chat=AsyncMock(return_value=SimpleNamespace(id=-100, title=EVIL)),
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member")),
    )
    reply = await _run_channel_add("@evil", bot)
    assert "<b>" not in reply and "<a " not in reply
    assert "&lt;b&gt;x&lt;/b&gt; &amp;" in reply


# ─── content._truncate / safe_source_url ────────────────────────────────────

@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://lex.uz/docs/1", "https://lex.uz/docs/1"),
        ("http://lex.uz/x?a=1&b=2", "http://lex.uz/x?a=1&b=2"),
        ("javascript:alert(1)", None),
        ("tg://resolve?domain=x", None),
        ("https://", None),
        ("", None),
        (None, None),
    ],
)
def test_safe_source_url(url, expected):
    assert content.safe_source_url(url) == expected


def test_truncated_text_escapes_the_source_url():
    url = 'https://lex.uz/docs/1?a=1&b="2"'
    text = content._truncate("a\n" * 2000, url, "uz")
    assert 'href="https://lex.uz/docs/1?a=1&amp;b=&quot;2&quot;"' in text


def test_a_bad_scheme_drops_the_link():
    text = content._truncate("a\n" * 2000, "javascript:alert(1)", "uz")
    assert "javascript" not in text and "<a " not in text


def test_a_cut_never_leaves_tags_open_or_half_written():
    body = "<b>" + ("qator\n" * 499) + "oxiri</b>\n" + ("<i>uzun matn</i>\n" * 400)
    text = content._truncate(body, "https://lex.uz/1", "uz")
    assert text.count("<b>") == text.count("</b>")
    assert text.count("<i>") == text.count("</i>")
    cut = content._close_open_tags("salom <b>dunyo</b> <a href=\"https://x")
    assert cut == "salom <b>dunyo</b> "


async def test_law_detail_has_no_url_button_for_a_bad_source(monkeypatch):
    article = {"full_text": "matn", "source_url": "javascript:alert(1)"}
    monkeypatch.setattr(content, "get_article", AsyncMock(return_value=article))
    callback = SimpleNamespace(
        data="law:1",
        message=SimpleNamespace(edit_text=AsyncMock()),
        answer=AsyncMock(),
    )
    await content.law_detail(callback, lang="uz")
    markup = callback.message.edit_text.call_args.kwargs["reply_markup"]
    assert all(button.url is None for row in markup.inline_keyboard for button in row)


# ─── weekly stats: escaping and chart thread ────────────────────────────────

def _stats(**overrides) -> WeeklyStats:
    values = dict(
        week_label="1–7", new_users=1, total_users=2, pro_users=0, total_saves=0,
        new_resumes=0, total_vacancies=0, avg_salary=0,
        top_specs=[EVIL], top_specs_counts=[3], top_regions=["A & B"], top_region_counts=[2],
        weeks_labels=[], users_per_week=[], avg_salary_per_week=[], channel="@ch<x>",
    )
    values.update(overrides)
    return WeeklyStats(**values)


@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
def test_stats_names_are_escaped(lang):
    message = ws.format_stats_message(_stats(), lang)
    assert EVIL not in message and "<a " not in message
    assert "&lt;b&gt;x&lt;/b&gt; &amp;" in message
    assert "A &amp; B" in message and "@ch&lt;x&gt;" in message


async def test_the_chart_is_rendered_off_the_event_loop_thread():
    seen = []

    def chart(stats, lang):
        seen.append(threading.current_thread() is threading.main_thread())
        return b"\x89PNG"

    bot = SimpleNamespace(send_photo=AsyncMock(), send_message=AsyncMock())
    with patch.object(ws, "collect_weekly_stats", AsyncMock(return_value=_stats())), patch.object(
        ws, "generate_weekly_stats_chart", chart
    ), patch.object(ws, "bot", bot):
        await ws.send_weekly_stats("@ch", "uz")
    assert seen == [False]
    bot.send_photo.assert_awaited_once()


# ─── weekly stats: due window and catch-up ──────────────────────────────────

def _at(day: int, hour: int, minute: int = 0) -> datetime:
    # 2026-10-12 is a Monday.
    return datetime(2026, 10, day, hour, minute, tzinfo=TZ)


@pytest.mark.parametrize(
    "moment, due",
    [
        (_at(15, 23, 59), False),   # Thursday
        (_at(16, 9, 59), False),    # Friday before 10:00
        (_at(16, 10, 0), True),
        (_at(16, 10, 6), True),     # used to be outside the 5-minute window
        (_at(16, 23, 0), True),
        (_at(17, 12, 0), True),     # Saturday catch-up
        (_at(18, 23, 59), True),    # Sunday, still the same ISO week
        (_at(19, 0, 1), False),     # next Monday
    ],
)
def test_is_due(moment, due):
    assert ws.is_due(moment) is due


@pytest.fixture
async def settings_db(tmp_path, monkeypatch):
    path = str(tmp_path / "ws.sqlite3")
    open_conns = []

    @asynccontextmanager
    async def tracked_connect(*args, **kwargs):
        async with connect(path) as conn:
            open_conns.append(conn)
            try:
                yield conn
            finally:
                open_conns.remove(conn)

    async with connect(path) as conn:
        await run_migrations(conn)
        await conn.execute("INSERT OR IGNORE INTO webapp_admin_settings (singleton) VALUES (1)")
        await conn.commit()
        await ensure_settings_columns(conn)
        await conn.execute(
            "UPDATE webapp_admin_settings SET auto_post_channel = '@ch', channel_lang = 'ru'"
        )
        await conn.commit()
    invalidate_settings_cache()
    monkeypatch.setattr(ws, "connect", tracked_connect)
    monkeypatch.setattr(ws, "_sent_week_in_process", None)
    yield functools.partial(connect, path), open_conns
    invalidate_settings_cache()


async def _marker(db):
    async with db() as conn:
        cursor = await conn.execute(
            "SELECT last_weekly_stats_week FROM webapp_admin_settings WHERE singleton = 1"
        )
        return (await cursor.fetchone())[0]


async def test_a_restart_after_the_window_still_sends_once(settings_db):
    db, open_conns = settings_db
    sends = []

    async def send(channel, lang):
        assert open_conns == []  # no connection held across the Telegram call
        sends.append((channel, lang))

    later = _at(16, 11, 30)
    with patch.object(ws, "send_weekly_stats", send):
        assert await ws.weekly_stats_tick(_at(16, 9, 0)) == "not_due"
        assert await ws.weekly_stats_tick(later) == "sent"
        assert await _marker(db) == week_key(later)
        assert await ws.weekly_stats_tick(_at(17, 9, 0)) == "already_sent"
    assert sends == [("@ch", "ru")]


async def test_the_db_marker_alone_prevents_a_repost(settings_db):
    """A fresh process (no in-memory guard) trusts the persisted week."""
    db, _ = settings_db
    async with db() as conn:
        await conn.execute(
            "UPDATE webapp_admin_settings SET last_weekly_stats_week = ?", (week_key(_at(16, 12)),)
        )
        await conn.commit()
    send = AsyncMock()
    with patch.object(ws, "send_weekly_stats", send):
        assert await ws.weekly_stats_tick(_at(16, 12)) == "already_sent"
    send.assert_not_awaited()


async def test_a_failed_send_leaves_the_week_unmarked(settings_db):
    db, _ = settings_db
    with patch.object(ws, "send_weekly_stats", AsyncMock(side_effect=RuntimeError("tg down"))):
        with pytest.raises(RuntimeError):
            await ws.weekly_stats_tick(_at(16, 10, 1))
    assert await _marker(db) in (None, "")
    send = AsyncMock()
    with patch.object(ws, "send_weekly_stats", send):
        assert await ws.weekly_stats_tick(_at(16, 14, 0)) == "sent"
    send.assert_awaited_once()
