"""
users.blocked bayrog'i testlari:
- broadcast TelegramForbiddenError da blocked=1 qo'yadi va muvaffaqiyatli
  yuborishda qayta blocked=0 ga qaytaradi;
- bildirishnoma so'rovi blocked=1 foydalanuvchilarni chiqarib tashlaydi;
- StatsMiddleware yangi xabar kelganda blocked=0 ga qaytaradi.
"""
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest
from aiogram.exceptions import TelegramForbiddenError

from src.handlers.admin import _deliver
from src.middleware.middlewares import StatsMiddleware

MW_MODULE = "src.middleware.middlewares"


def _forbidden() -> TelegramForbiddenError:
    return TelegramForbiddenError(method=object(), message="bot was blocked by the user")


async def _users_db() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute(
        "CREATE TABLE users (user_id INTEGER PRIMARY KEY, blocked INTEGER NOT NULL DEFAULT 0)"
    )
    await conn.commit()
    return conn


# ─── broadcast: _deliver ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deliver_marks_blocked_on_forbidden():
    conn = await _users_db()
    await conn.execute("INSERT INTO users (user_id, blocked) VALUES (1, 0)")
    await conn.commit()

    async def send(_user_id: int):
        raise _forbidden()

    ok = await _deliver(conn, send, 1)
    assert ok is False

    cur = await conn.execute("SELECT blocked FROM users WHERE user_id = 1")
    assert (await cur.fetchone())[0] == 1
    await conn.close()


@pytest.mark.asyncio
async def test_deliver_unblocks_on_success():
    conn = await _users_db()
    await conn.execute("INSERT INTO users (user_id, blocked) VALUES (2, 1)")
    await conn.commit()

    send = AsyncMock(return_value=None)

    ok = await _deliver(conn, send, 2)
    assert ok is True

    cur = await conn.execute("SELECT blocked FROM users WHERE user_id = 2")
    assert (await cur.fetchone())[0] == 0
    await conn.close()


@pytest.mark.asyncio
async def test_deliver_leaves_unrelated_errors_unblocked():
    conn = await _users_db()
    await conn.execute("INSERT INTO users (user_id, blocked) VALUES (3, 0)")
    await conn.commit()

    async def send(_user_id: int):
        raise RuntimeError("boom")

    ok = await _deliver(conn, send, 3)
    assert ok is False

    cur = await conn.execute("SELECT blocked FROM users WHERE user_id = 3")
    assert (await cur.fetchone())[0] == 0
    await conn.close()


# ─── notification scheduler: blocked users excluded ────────────────────────

@pytest.mark.asyncio
async def test_notifications_skip_blocked_users():
    from src.functions.notification_scheduler import _run_notifications

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute(
        "CREATE TABLE users (user_id INTEGER PRIMARY KEY, user_pro INTEGER DEFAULT 0, "
        "pref_filters_json TEXT, lang TEXT, blocked INTEGER NOT NULL DEFAULT 0)"
    )
    await conn.execute(
        """CREATE TABLE notification_settings (
            user_id INTEGER PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER,
            updated_at INTEGER
        )"""
    )
    await conn.execute(
        """CREATE TABLE sent_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vacancy_uid TEXT NOT NULL,
            sent_at INTEGER NOT NULL
        )"""
    )
    await conn.execute(
        "CREATE UNIQUE INDEX idx_sn ON sent_notifications(user_id, vacancy_uid)"
    )
    await conn.execute(
        "CREATE TABLE vacancy_cache (uid TEXT PRIMARY KEY, data_json TEXT, expires_at INTEGER)"
    )

    import time
    now = int(time.time())
    await conn.execute(
        "INSERT INTO users (user_id, user_pro, pref_filters_json, lang, blocked) "
        "VALUES (999, 1, NULL, 'uz', 1)"
    )
    await conn.execute(
        "INSERT INTO notification_settings VALUES (999, 1, ?, ?)", (now, now)
    )
    await conn.execute(
        "INSERT INTO vacancy_cache VALUES ('vc999', '{\"title\": \"Dev\"}', ?)",
        (now + 3600,),
    )
    await conn.commit()

    mock_bot = AsyncMock()
    with patch("src.functions.notification_scheduler.bot", mock_bot):
        await _run_notifications(conn)

    mock_bot.send_message.assert_not_called()
    await conn.close()


@pytest.mark.asyncio
async def test_notifications_mark_blocked_on_forbidden():
    from src.functions.notification_scheduler import _run_notifications

    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute(
        "CREATE TABLE users (user_id INTEGER PRIMARY KEY, user_pro INTEGER DEFAULT 0, "
        "pref_filters_json TEXT, lang TEXT, blocked INTEGER NOT NULL DEFAULT 0)"
    )
    await conn.execute(
        """CREATE TABLE notification_settings (
            user_id INTEGER PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER,
            updated_at INTEGER
        )"""
    )
    await conn.execute(
        """CREATE TABLE sent_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vacancy_uid TEXT NOT NULL,
            sent_at INTEGER NOT NULL
        )"""
    )
    await conn.execute(
        "CREATE UNIQUE INDEX idx_sn ON sent_notifications(user_id, vacancy_uid)"
    )
    await conn.execute(
        "CREATE TABLE vacancy_cache (uid TEXT PRIMARY KEY, data_json TEXT, expires_at INTEGER)"
    )

    import time
    now = int(time.time())
    await conn.execute(
        "INSERT INTO users (user_id, user_pro, pref_filters_json, lang, blocked) "
        "VALUES (888, 1, NULL, 'uz', 0)"
    )
    await conn.execute(
        "INSERT INTO notification_settings VALUES (888, 1, ?, ?)", (now, now)
    )
    await conn.execute(
        "INSERT INTO vacancy_cache VALUES ('vc888', '{\"title\": \"Dev\"}', ?)",
        (now + 3600,),
    )
    await conn.commit()

    mock_bot = AsyncMock()
    mock_bot.send_message.side_effect = _forbidden()
    with patch("src.functions.notification_scheduler.bot", mock_bot):
        await _run_notifications(conn)

    cur = await conn.execute("SELECT blocked FROM users WHERE user_id = 888")
    assert (await cur.fetchone())[0] == 1
    await conn.close()


# ─── StatsMiddleware: un-block on a new message ────────────────────────────

@pytest.mark.asyncio
async def test_middleware_unblocks_returning_user(tmp_path):
    db_path = str(tmp_path / "blocked.sqlite3")
    middleware = StatsMiddleware(db_path)
    with patch(f"{MW_MODULE}._seed_from_osonish_api", new_callable=AsyncMock):
        await middleware.init_db()

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO users (user_id, date, lang, blocked) VALUES (55, 0, 'uz', 1)"
        )
        await conn.commit()

    lang, is_new = await middleware.resolve_user(55, "uz", None)
    assert (lang, is_new) == ("uz", False)

    async with aiosqlite.connect(db_path) as conn:
        cur = await conn.execute("SELECT blocked FROM users WHERE user_id = 55")
        assert (await cur.fetchone())[0] == 0
