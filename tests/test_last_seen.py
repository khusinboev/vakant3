"""``users.last_seen_at`` is refreshed from the auth path, at most once per 10 min.

Both processes stamp it: the API in ``webapp/core/auth.py`` (once per request,
from the row the identity lookup already loaded) and the bot in
``StatsMiddleware.resolve_user``. The throttle is what makes it cheap enough to
do on every request — without it the admin Users ``sort=last_seen`` column and
the ``active_days`` broadcast segment would cost one write per request.
"""

import time
from datetime import datetime, timezone

import aiosqlite
import pytest
from starlette.requests import Request

from src.middleware import middlewares as mw
from webapp.core import users as users_mod
from webapp.core.auth import _resolve
from webapp.core.session import sign_session_payload
from webapp.core.users import LAST_SEEN_THROTTLE_SECONDS, touch_last_seen

USER_ID = 8_100_001
T0 = 1_700_000_000

USERS_DDL = """
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    date INTEGER,
    lang TEXT,
    region TEXT,
    district TEXT,
    specs TEXT,
    money INTEGER,
    ref_by INTEGER,
    user_balance INTEGER DEFAULT 0,
    user_pro INTEGER DEFAULT 0,
    pref_filters_json TEXT,
    blocked INTEGER NOT NULL DEFAULT 0,
    first_name TEXT,
    username TEXT,
    photo_url TEXT,
    last_seen_at INTEGER
)
"""


class _Clock:
    """Stand-in for the ``time`` module inside ``webapp.core.users``."""

    def __init__(self, now: int) -> None:
        self.now = now

    def time(self) -> int:
        return self.now


class CountingDB:
    """Transparent proxy that counts the ``last_seen_at`` UPDATE statements."""

    def __init__(self, conn) -> None:
        self._conn = conn
        self.updates = 0

    def __getattr__(self, name):  # in_transaction, commit, rollback, ...
        return getattr(self._conn, name)

    async def execute(self, sql, parameters=None):
        if "last_seen_at = ?" in sql:
            self.updates += 1
        if parameters is None:
            return await self._conn.execute(sql)
        return await self._conn.execute(sql, parameters)


def _request(token: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "scheme": "http",
            "http_version": "1.1",
            "server": ("testserver", 80),
            "client": ("203.0.113.9", 40000),
            "headers": [(b"authorization", f"Bearer {token}".encode())],
        }
    )


@pytest.fixture
async def api_db(tmp_path):
    conn = await aiosqlite.connect(str(tmp_path / "last_seen.sqlite3"))
    conn.row_factory = aiosqlite.Row
    await conn.execute(USERS_DDL)
    await conn.execute("INSERT INTO users (user_id, lang) VALUES (?, 'uz')", (USER_ID,))
    await conn.execute(
        "CREATE TABLE webapp_sessions (token TEXT PRIMARY KEY, user_id INTEGER, "
        "created_at INTEGER, expires_at INTEGER)"
    )
    await conn.commit()
    try:
        yield conn
    finally:
        await conn.close()


async def _stored(conn) -> int | None:
    cursor = await conn.execute("SELECT last_seen_at FROM users WHERE user_id = ?", (USER_ID,))
    row = await cursor.fetchone()
    return None if row is None else row["last_seen_at"]


# ---------------------------------------------------------------------------
# API: the auth path
# ---------------------------------------------------------------------------


async def test_api_auth_throttles_last_seen(api_db, monkeypatch):
    """Two requests inside the window write once; a later one writes again."""
    clock = _Clock(T0)
    monkeypatch.setattr(users_mod, "time", clock)

    exp = int(time.time()) + 3600
    await api_db.execute(
        "INSERT INTO webapp_sessions (token, user_id, created_at, expires_at) "
        "VALUES ('sid-last-seen', ?, ?, ?)",
        (USER_ID, int(time.time()), exp),
    )
    await api_db.commit()
    token = sign_session_payload({"sid": "sid-last-seen", "exp": exp})

    db = CountingDB(api_db)

    user, code = await _resolve(_request(token), db)
    assert code is None and user["user_id"] == USER_ID
    assert await _stored(api_db) == T0
    assert db.updates == 1

    # Second request, well inside the 10 minute window: no statement at all.
    clock.now = T0 + LAST_SEEN_THROTTLE_SECONDS - 1
    user, code = await _resolve(_request(token), db)
    assert code is None
    assert await _stored(api_db) == T0
    assert db.updates == 1

    # Past the window: refreshed.
    clock.now = T0 + LAST_SEEN_THROTTLE_SECONDS + 1
    user, code = await _resolve(_request(token), db)
    assert code is None
    assert await _stored(api_db) == clock.now
    assert db.updates == 2


async def test_touch_last_seen_leaves_no_open_transaction(api_db, monkeypatch):
    """The write is standalone: committed when it lands, rolled back when not."""
    clock = _Clock(T0)
    monkeypatch.setattr(users_mod, "time", clock)

    row = {"user_id": USER_ID, "last_seen_at": None}
    assert await touch_last_seen(api_db, row) is True
    assert api_db.in_transaction is False
    assert row["last_seen_at"] == T0

    # A concurrent request that loaded the pre-update row still must not write:
    # the WHERE clause repeats the throttle, so the UPDATE matches no row.
    stale = {"user_id": USER_ID, "last_seen_at": None}
    assert await touch_last_seen(api_db, stale) is False
    assert api_db.in_transaction is False
    assert await _stored(api_db) == T0


async def test_touch_last_seen_never_joins_an_open_transaction(api_db, monkeypatch):
    monkeypatch.setattr(users_mod, "time", _Clock(T0))
    await api_db.execute("UPDATE users SET lang = 'ru' WHERE user_id = ?", (USER_ID,))
    assert api_db.in_transaction is True
    try:
        assert await touch_last_seen(api_db, {"user_id": USER_ID, "last_seen_at": None}) is False
    finally:
        await api_db.rollback()
    assert await _stored(api_db) is None


# ---------------------------------------------------------------------------
# Bot: StatsMiddleware
# ---------------------------------------------------------------------------


@pytest.fixture
async def bot_db(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.setattr(mw, "_seed_from_osonish_api", AsyncMock())
    middleware = mw.StatsMiddleware(str(tmp_path / "bot.sqlite3"))
    await middleware.init_db()
    return middleware


async def test_bot_middleware_throttles_last_seen(bot_db, monkeypatch):
    clock = {"now": T0}
    monkeypatch.setattr(
        mw, "now_tz", lambda: datetime.fromtimestamp(clock["now"], tz=timezone.utc)
    )

    async def stored() -> int | None:
        async with aiosqlite.connect(bot_db.db_path) as conn:
            cursor = await conn.execute(
                "SELECT last_seen_at FROM users WHERE user_id = ?", (USER_ID,)
            )
            row = await cursor.fetchone()
            return None if row is None else row[0]

    # First /start: the row is created and stamped.
    assert await bot_db.resolve_user(USER_ID, "uz", None) == ("uz", True)
    assert await stored() == T0

    # Another message inside the window: untouched.
    clock["now"] = T0 + LAST_SEEN_THROTTLE_SECONDS - 1
    assert await bot_db.resolve_user(USER_ID, "uz", None) == ("uz", False)
    assert await stored() == T0

    # And refreshed once the window passed.
    clock["now"] = T0 + LAST_SEEN_THROTTLE_SECONDS + 5
    assert await bot_db.resolve_user(USER_ID, "uz", None) == ("uz", False)
    assert await stored() == clock["now"]


async def test_bot_middleware_survives_a_schema_without_the_column(tmp_path):
    """A pre-m009 database must still resolve the language."""
    path = str(tmp_path / "legacy.sqlite3")
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, date INTEGER, lang TEXT, "
            "blocked INTEGER NOT NULL DEFAULT 0)"
        )
        await conn.execute("INSERT INTO users (user_id, date, lang) VALUES (?, 0, 'ru')", (USER_ID,))
        await conn.commit()

    middleware = mw.StatsMiddleware(path)
    assert await middleware.resolve_user(USER_ID, "uz", None) == ("ru", False)
