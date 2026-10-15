"""users.banned is enforced by the bot: no handler response, no broadcast, no notification."""
from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest

from src.core.timeutil import TZ
from src.db.migrate import run_migrations
from src.functions import broadcast_worker as bw
from src.functions import notification_scheduler as ns
import config
from src.middleware import middlewares as mw_module
from src.middleware.middlewares import StatsMiddleware

MW_MODULE = "src.middleware.middlewares"
BANNED, ALLOWED = 900000000001, 900000000002


async def _migrated(path):
    async with aiosqlite.connect(path) as conn:
        await run_migrations(conn)  # m009 creates users with ``banned``
        # Columns the bot's StatsMiddleware adds (not a migration).
        for column in ("user_pro INTEGER DEFAULT 0", "pref_filters_json TEXT",
                       "blocked INTEGER NOT NULL DEFAULT 0"):
            try:
                await conn.execute(f"ALTER TABLE users ADD COLUMN {column}")
            except aiosqlite.OperationalError:
                pass  # already there (init_db created the table)
        await conn.executemany(
            "INSERT INTO users (user_id, date, lang, banned) VALUES (?, ?, 'uz', ?)",
            [(BANNED, int(time.time()), 1), (ALLOWED, int(time.time()), 0)],
        )
        await conn.commit()


# ─── middleware ──────────────────────────────────────────────────────────────

@pytest.fixture
async def middleware(tmp_path):
    db_path = str(tmp_path / "bot.sqlite3")
    mw = StatsMiddleware(db_path)
    with patch(f"{MW_MODULE}._seed_from_osonish_api", new_callable=AsyncMock):
        await mw.init_db()
    await _migrated(db_path)
    return mw


def _event(user_id):
    return SimpleNamespace(from_user=SimpleNamespace(id=user_id, language_code="uz"))


async def test_a_banned_users_update_reaches_no_handler(middleware):
    handler = AsyncMock(return_value="handled")
    assert await middleware(handler, _event(BANNED), {}) is None
    handler.assert_not_awaited()


async def test_other_users_are_handled_as_before(middleware):
    handler = AsyncMock(return_value="handled")
    data: dict = {}
    assert await middleware(handler, _event(ALLOWED), data) == "handled"
    handler.assert_awaited_once()
    assert data["lang"] == "uz" and data["is_new_user"] is False


async def test_a_new_user_is_not_banned(middleware):
    handler = AsyncMock(return_value="handled")
    data: dict = {}
    assert await middleware(handler, _event(900000000003), data) == "handled"
    assert data["is_new_user"] is True


async def test_the_check_fails_open_without_the_column(tmp_path):
    """A DB older than m009 has no ``banned``/``admins``: everyone passes."""
    db_path = str(tmp_path / "old.sqlite3")
    mw = StatsMiddleware(db_path)
    with patch(f"{MW_MODULE}._seed_from_osonish_api", new_callable=AsyncMock):
        await mw.init_db()
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("INSERT INTO users (user_id, date, lang) VALUES (?, 0, 'ru')", (BANNED,))
        await conn.commit()
    handler = AsyncMock(return_value="handled")
    data: dict = {}
    assert await mw(handler, _event(BANNED), data) == "handled"
    assert data["lang"] == "ru"


async def test_one_connection_per_update(middleware, monkeypatch):
    """The ban is read in resolve_user's own SELECT, not on a second connection."""
    opened = []
    real_connect = mw_module.connect

    def counting_connect(*args, **kwargs):
        opened.append(1)
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(mw_module, "connect", counting_connect)
    for user_id in (BANNED, ALLOWED):
        opened.clear()
        await middleware(AsyncMock(), _event(user_id), {})
        assert len(opened) == 1


async def _admins(middleware, rows):
    async with aiosqlite.connect(middleware.db_path) as conn:
        await conn.executemany(
            "INSERT INTO admins (user_id, role, added_at, disabled) VALUES (?, ?, 0, ?)", rows
        )
        await conn.commit()


async def test_an_enabled_admin_row_bypasses_the_ban(middleware):
    await _admins(middleware, [(BANNED, "moderator", 0)])
    handler = AsyncMock(return_value="handled")
    assert await middleware(handler, _event(BANNED), {}) == "handled"


async def test_a_disabled_admin_row_does_not_bypass(middleware, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_IDS", [BANNED])
    await _admins(middleware, [(BANNED, "owner", 1)])
    handler = AsyncMock()
    assert await middleware(handler, _event(BANNED), {}) is None
    handler.assert_not_awaited()


async def test_admin_ids_bypass_only_while_no_owner_exists(middleware, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_IDS", [BANNED])
    handler = AsyncMock(return_value="handled")
    assert await middleware(handler, _event(BANNED), {}) == "handled"  # bootstrap

    await _admins(middleware, [(900000000009, "owner", 0)])
    handler.reset_mock()
    assert await middleware(handler, _event(BANNED), {}) is None
    handler.assert_not_awaited()


# ─── broadcast targets ───────────────────────────────────────────────────────

async def test_banned_users_are_not_broadcast_targets(tmp_path):
    path = tmp_path / "bc.sqlite3"
    await _migrated(path)

    @asynccontextmanager
    async def connect():
        conn = await aiosqlite.connect(path)
        try:
            yield conn
        finally:
            await conn.close()

    async with connect() as conn:
        for segment, exclude_blocked in (("all", True), ("all", False), ("lang:uz", True)):
            broadcast_id = await bw.create_broadcast(
                conn, actor_id=1, kind="text", text="salom",
                target={"segment": segment, "exclude_blocked": exclude_blocked},
            )
            assert await bw.queue_broadcast(conn, broadcast_id) == 1
            cursor = await conn.execute(
                "SELECT user_id FROM broadcast_targets WHERE broadcast_id = ?", (broadcast_id,)
            )
            assert [row[0] for row in await cursor.fetchall()] == [ALLOWED]
        await conn.commit()


# ─── notifications ───────────────────────────────────────────────────────────

class _Bot:
    def __init__(self):
        self.sent: list[int] = []

    async def send_message(self, *, chat_id, **_kwargs):
        self.sent.append(chat_id)


async def test_banned_pro_users_get_no_notifications(tmp_path):
    path = tmp_path / "notify.sqlite3"
    await _migrated(path)
    async with aiosqlite.connect(path) as conn:
        await conn.execute("UPDATE users SET user_pro = 1")
        await conn.execute(
            "CREATE TABLE notification_settings (user_id INTEGER PRIMARY KEY, "
            "enabled INTEGER NOT NULL DEFAULT 0, created_at INTEGER, updated_at INTEGER)"
        )
        await conn.execute(
            "CREATE TABLE sent_notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user_id INTEGER NOT NULL, vacancy_uid TEXT NOT NULL, sent_at INTEGER NOT NULL)"
        )
        await conn.execute(
            "CREATE TABLE vacancy_cache (uid TEXT PRIMARY KEY, data_json TEXT, expires_at INTEGER)"
        )
        now = int(time.time())
        await conn.executemany(
            "INSERT INTO notification_settings VALUES (?, 1, ?, ?)",
            [(BANNED, now, now), (ALLOWED, now, now)],
        )
        await conn.execute(
            "INSERT INTO vacancy_cache VALUES ('vc1', ?, ?)",
            (json.dumps({"title": "Dev", "max_salary": 7000000}), now + 3600),
        )
        await conn.commit()

        bot = _Bot()
        evening = datetime.now(TZ).replace(hour=ns.WORK_HOUR_END, minute=30, second=0, microsecond=0)
        with patch.object(ns, "bot", bot), patch.object(ns, "_now_uzb", return_value=evening):
            await ns._run_notifications(conn)
    assert bot.sent == [ALLOWED]
