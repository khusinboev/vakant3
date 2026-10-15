"""
B4: Telegram membership updates (src/handlers/membership.py).

* my_chat_member in a private chat: kicked -> users.blocked = 1, member -> 0;
  groups/channels, other statuses and unknown users change nothing.
* chat_member in a required (enabled) channel drops the user's cached
  subscription verdict; other channels, no-op changes and unknown users do not.
* main.include_routers makes the dispatcher request both update types.

Updates are real aiogram objects fed through a real Dispatcher; the DB is a
per-test file (only the `connect` seam of the handler module is pointed at it).
"""
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import aiosqlite
import pytest
from aiogram import Bot, Dispatcher
from aiogram.types import (
    Chat,
    ChatMemberBanned,
    ChatMemberLeft,
    ChatMemberMember,
    ChatMemberRestricted,
    ChatMemberUpdated,
    Update,
    User,
)

from src.db.connection import connect as real_connect
from src.db.migrate import run_migrations
from src.handlers import membership

UID = 900000000001
UNKNOWN = 900000000999
CHANNEL_ID = -1001234567890
OTHER_CHANNEL_ID = -1009876543210
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
BOT_TOKEN = "123456789:TEST-dummy-token-never-valid-on-telegram"

USERS_DDL = (
    "CREATE TABLE users (user_id INTEGER PRIMARY KEY, date INTEGER, lang TEXT, region TEXT, "
    "district TEXT, specs TEXT, money INTEGER, blocked INTEGER NOT NULL DEFAULT 0)"
)


# -- fixtures -----------------------------------------------------------------

@pytest.fixture
async def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "membership.sqlite3")
    async with aiosqlite.connect(path) as conn:
        await conn.execute(USERS_DDL)
        await conn.commit()
        await run_migrations(conn)
        await conn.execute("INSERT INTO users (user_id, date, blocked) VALUES (?, 1, 0)", (UID,))
        await conn.commit()

    @asynccontextmanager
    async def _connect():
        async with real_connect(path) as conn:
            yield conn

    monkeypatch.setattr(membership, "connect", _connect)
    return path


@pytest.fixture
def dispatcher():
    """A dispatcher wired exactly like main.py's, with the routers detached afterwards."""
    import main

    dp = Dispatcher()
    main.include_routers(dp)
    yield dp
    for router in list(dp.sub_routers):
        router._parent_router = None
    dp.sub_routers.clear()


@pytest.fixture
def bot():
    return Bot(BOT_TOKEN)


async def q(path, sql, args=()):
    async with aiosqlite.connect(path) as conn:
        cursor = await conn.execute(sql, args)
        return await cursor.fetchall()


async def execute(path, sql, args=()):
    async with aiosqlite.connect(path) as conn:
        await conn.execute(sql, args)
        await conn.commit()


async def blocked_of(path, user_id=UID):
    rows = await q(path, "SELECT blocked FROM users WHERE user_id = ?", (user_id,))
    return rows[0][0] if rows else None


async def add_channel(path, *, id_, chat_id=None, username=None, enabled=1):
    await execute(
        path,
        "INSERT INTO channels (id, chat_id, username, enabled) VALUES (?, ?, ?, ?)",
        (id_, chat_id, username, enabled),
    )


async def add_cache(path, user_id=UID):
    await execute(
        path,
        "INSERT OR REPLACE INTO subscription_checks (user_id, checked_at, ok, missing_json) "
        "VALUES (?, ?, 1, '[]')",
        (user_id, int(time.time())),
    )


async def cached(path, user_id=UID) -> bool:
    return bool(await q(path, "SELECT 1 FROM subscription_checks WHERE user_id = ?", (user_id,)))


# -- update builders ----------------------------------------------------------

def _user(user_id=UID):
    return User(id=user_id, is_bot=False, first_name="Synthetic")


def _bot_user():
    return User(id=123456789, is_bot=True, first_name="Bot", username="bandlikuzbot")


def _member(status, user, **extra):
    if status == "member":
        return ChatMemberMember(status="member", user=user)
    if status == "kicked":
        return ChatMemberBanned(status="kicked", user=user, until_date=0)
    if status == "left":
        return ChatMemberLeft(status="left", user=user)
    if status == "restricted":
        flags = {
            name: False
            for name in (
                "can_send_messages", "can_send_audios", "can_send_documents", "can_send_photos",
                "can_send_videos", "can_send_video_notes", "can_send_voice_notes", "can_send_polls",
                "can_send_other_messages", "can_add_web_page_previews", "can_change_info",
                "can_invite_users", "can_pin_messages", "can_manage_topics",
            )
        }
        return ChatMemberRestricted(
            status="restricted", user=user, is_member=extra.get("is_member", True),
            until_date=0, **flags,
        )
    raise AssertionError(status)


def my_chat_member(old, new, *, chat_id=UID, chat_type="private"):
    return Update(
        update_id=1,
        my_chat_member=ChatMemberUpdated(
            chat=Chat(id=chat_id, type=chat_type),
            from_user=_user(chat_id if chat_type == "private" else UID),
            date=NOW,
            old_chat_member=_member(old, _bot_user()),
            new_chat_member=_member(new, _bot_user()),
        ),
    )


def chat_member(old, new, *, user_id=UID, chat_id=CHANNEL_ID, username=None, old_kw=None, new_kw=None):
    return Update(
        update_id=2,
        chat_member=ChatMemberUpdated(
            chat=Chat(id=chat_id, type="channel", username=username),
            from_user=_user(user_id),
            date=NOW,
            old_chat_member=_member(old, _user(user_id), **(old_kw or {})),
            new_chat_member=_member(new, _user(user_id), **(new_kw or {})),
        ),
    )


# -- dispatcher wiring --------------------------------------------------------

def test_main_requests_membership_update_types(dispatcher):
    used = set(dispatcher.resolve_used_update_types())
    assert {"my_chat_member", "chat_member"} <= used
    # the pre-existing handlers are still wired
    assert {"message", "callback_query"} <= used


# -- my_chat_member -----------------------------------------------------------

async def test_private_kicked_sets_blocked(dispatcher, bot, db_path):
    await dispatcher.feed_update(bot, my_chat_member("member", "kicked"))
    assert await blocked_of(db_path) == 1


async def test_private_member_clears_blocked(dispatcher, bot, db_path):
    await execute(db_path, "UPDATE users SET blocked = 1 WHERE user_id = ?", (UID,))
    await dispatcher.feed_update(bot, my_chat_member("kicked", "member"))
    assert await blocked_of(db_path) == 0


async def test_set_blocked_reports_only_real_changes(db_path):
    """The `blocked IS NOT ?` guard skips redundant writes; the return value is the observable part."""
    assert await membership.set_blocked(UID, True) is True
    assert await membership.set_blocked(UID, True) is False
    assert await membership.set_blocked(UID, False) is True
    assert await membership.set_blocked(UID, False) is False
    assert await membership.set_blocked(UID + 1, True) is False  # unknown user: nothing written


async def test_blocked_updates_are_idempotent(dispatcher, bot, db_path):
    for _ in range(2):
        await dispatcher.feed_update(bot, my_chat_member("member", "kicked"))
    assert await blocked_of(db_path) == 1
    for _ in range(2):
        await dispatcher.feed_update(bot, my_chat_member("kicked", "member"))
    assert await blocked_of(db_path) == 0


@pytest.mark.parametrize("chat_type", ["group", "supergroup", "channel"])
async def test_non_private_chats_do_not_touch_blocked(dispatcher, bot, db_path, chat_type):
    # chat id equal to a real user id on purpose: only the chat type may veto the write
    await dispatcher.feed_update(bot, my_chat_member("member", "kicked", chat_id=UID, chat_type=chat_type))
    assert await blocked_of(db_path) == 0


async def test_private_other_statuses_are_ignored(dispatcher, bot, db_path):
    await execute(db_path, "UPDATE users SET blocked = 1 WHERE user_id = ?", (UID,))
    await dispatcher.feed_update(bot, my_chat_member("member", "left"))
    assert await blocked_of(db_path) == 1


async def test_unknown_user_is_not_created(dispatcher, bot, db_path):
    await dispatcher.feed_update(bot, my_chat_member("member", "kicked", chat_id=UNKNOWN))
    await dispatcher.feed_update(bot, my_chat_member("kicked", "member", chat_id=UNKNOWN))
    assert await q(db_path, "SELECT user_id FROM users WHERE user_id = ?", (UNKNOWN,)) == []
    assert await q(db_path, "SELECT COUNT(*) FROM users") == [(1,)]


async def test_db_failure_is_swallowed(dispatcher, bot, db_path, monkeypatch):
    await add_channel(db_path, id_="@reqchan", chat_id=CHANNEL_ID)

    @asynccontextmanager
    async def _broken():
        raise RuntimeError("db down")
        yield  # pragma: no cover

    monkeypatch.setattr(membership, "connect", _broken)
    await dispatcher.feed_update(bot, my_chat_member("member", "kicked"))
    await dispatcher.feed_update(bot, chat_member("left", "member"))  # neither may raise


# -- chat_member --------------------------------------------------------------

@pytest.mark.parametrize(
    "old,new,old_kw,new_kw",
    [
        ("left", "member", None, None),                                           # joined
        ("member", "left", None, None),                                           # left
        ("member", "kicked", None, None),                                         # kicked
        ("member", "restricted", None, {"is_member": True}),                      # restricted
        ("restricted", "restricted", {"is_member": True}, {"is_member": False}),  # lost membership while restricted
    ],
)
async def test_required_channel_change_drops_cache(dispatcher, bot, db_path, old, new, old_kw, new_kw):
    await add_channel(db_path, id_="@reqchan", chat_id=CHANNEL_ID)
    await add_cache(db_path)
    await dispatcher.feed_update(bot, chat_member(old, new, old_kw=old_kw, new_kw=new_kw))
    assert not await cached(db_path)


async def test_only_the_affected_user_cache_is_dropped(dispatcher, bot, db_path):
    await add_channel(db_path, id_="@reqchan", chat_id=CHANNEL_ID)
    await add_cache(db_path, UID)
    await add_cache(db_path, UID + 1)
    await dispatcher.feed_update(bot, chat_member("left", "member", user_id=UID))
    assert not await cached(db_path, UID)
    assert await cached(db_path, UID + 1)


async def test_unknown_user_without_cache_row_is_fine(dispatcher, bot, db_path):
    await add_channel(db_path, id_="@reqchan", chat_id=CHANNEL_ID)
    await dispatcher.feed_update(bot, chat_member("left", "member", user_id=UNKNOWN))
    assert await q(db_path, "SELECT COUNT(*) FROM subscription_checks") == [(0,)]
    assert await q(db_path, "SELECT user_id FROM users WHERE user_id = ?", (UNKNOWN,)) == []


async def test_channel_not_in_required_list_is_ignored(dispatcher, bot, db_path):
    await add_channel(db_path, id_="@reqchan", chat_id=CHANNEL_ID)
    await add_cache(db_path)
    await dispatcher.feed_update(bot, chat_member("left", "member", chat_id=OTHER_CHANNEL_ID))
    assert await cached(db_path)


async def test_disabled_channel_is_ignored(dispatcher, bot, db_path):
    await add_channel(db_path, id_="@offchan", chat_id=CHANNEL_ID, enabled=0)
    await add_cache(db_path)
    await dispatcher.feed_update(bot, chat_member("left", "member"))
    assert await cached(db_path)


async def test_unchanged_membership_keeps_cache(dispatcher, bot, db_path):
    await add_channel(db_path, id_="@reqchan", chat_id=CHANNEL_ID)
    await add_cache(db_path)
    await dispatcher.feed_update(bot, chat_member("member", "member"))
    assert await cached(db_path)


@pytest.mark.parametrize(
    "row,username",
    [
        (dict(id_="@LegacyChan"), "legacychan"),                    # legacy row: only the pasted @name
        (dict(id_=str(CHANNEL_ID)), None),                          # id stored as the numeric chat id
        (dict(id_="x1", username="@ByUsername"), "byusername"),     # username column
    ],
)
async def test_required_channel_matching_forms(dispatcher, bot, db_path, row, username):
    await add_channel(db_path, **row)
    await add_cache(db_path)
    await dispatcher.feed_update(bot, chat_member("left", "member", username=username))
    assert not await cached(db_path)


async def test_username_alone_does_not_match_other_channel(dispatcher, bot, db_path):
    await add_channel(db_path, id_="@reqchan", chat_id=CHANNEL_ID)
    await add_cache(db_path)
    await dispatcher.feed_update(
        bot, chat_member("left", "member", chat_id=OTHER_CHANNEL_ID, username="elsewhere")
    )
    assert await cached(db_path)
