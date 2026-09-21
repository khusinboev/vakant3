"""Entry gate: /start, forced subscription, caching and channel link parsing.

No network: every Telegram round trip goes through ``subscription._request``,
the single httpx seam, which is monkeypatched here.
"""

import json
import time

import aiosqlite
import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from src.db.migrate import run_migrations
from src.functions.functions import parse_channel_link
from webapp.core import entry_gate, subscription
from webapp.core.database import get_db
from webapp.core.entry_gate import evaluate_entry, raise_for_state, require_entry
from webapp.routers import admin_channels

NOW = 1_700_000_000


@pytest.fixture(autouse=True)
def _no_rate_limits():
    """slowapi keys on the test client IP, so limits would leak between tests."""
    from webapp.core.limiter import limiter

    previous = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = previous


@pytest.fixture(autouse=True)
def _fresh_column_cache():
    """Each test builds its own database — the process-wide cache must not leak."""
    entry_gate.reset_users_columns_cache()
    yield
    entry_gate.reset_users_columns_cache()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db(tmp_path):
    conn = await aiosqlite.connect(tmp_path / "gate.sqlite3")
    conn.row_factory = aiosqlite.Row
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS webapp_admin_settings (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            referral_enabled INTEGER NOT NULL DEFAULT 0,
            referral_required_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    await conn.execute(
        "INSERT OR REPLACE INTO webapp_admin_settings (singleton, referral_enabled, "
        "referral_required_count) VALUES (1, 0, 0)"
    )
    await run_migrations(conn)
    await conn.execute("ALTER TABLE users ADD COLUMN ref_by INTEGER")
    await conn.commit()
    yield conn
    await conn.close()


async def add_user(db, user_id: int, *, started: bool = True) -> None:
    await db.execute(
        "INSERT OR REPLACE INTO users (user_id, date, lang, started_at) VALUES (?, ?, 'uz', ?)",
        (user_id, NOW, NOW if started else None),
    )
    await db.commit()


async def add_channel(db, channel_id: str, chat_id: int | None = None) -> None:
    await db.execute(
        "INSERT OR REPLACE INTO channels (id, title, username, invite_link, chat_id, enabled) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        (channel_id, f"Title {channel_id}", channel_id.lstrip("@"),
         f"https://t.me/{channel_id.lstrip('@')}", chat_id),
    )
    await db.commit()


@pytest.fixture
def telegram(monkeypatch):
    """Scriptable stand-in for ``subscription._request`` + a call log."""
    calls: list[tuple[str, dict]] = []
    script: dict[str, object] = {"handler": None}

    async def fake_request(method, params):
        calls.append((method, dict(params)))
        handler = script["handler"]
        assert handler is not None, f"unexpected telegram call: {method}"
        return handler(method, params)

    monkeypatch.setattr(subscription, "_request", fake_request)
    monkeypatch.setattr(subscription, "_now", lambda: NOW)
    subscription.reset_bot_id_cache()

    class Telegram:
        calls = None

        def script(self, handler):
            script["handler"] = handler

        def member(self, status="member"):
            self.script(lambda method, params: (200, {"ok": True, "result": {"status": status}}))

        def failure(self, status_code, description):
            self.script(
                lambda method, params: (status_code, {"ok": False, "description": description})
            )

        def transient(self, status_code=500):
            self.script(lambda method, params: (status_code, {"ok": False, "description": "boom"}))

    tg = Telegram()
    tg.calls = calls
    return tg


# ---------------------------------------------------------------------------
# Subscription verdicts
# ---------------------------------------------------------------------------


async def test_started_at_null_blocks_with_bot_start_required(db):
    await add_user(db, 10, started=False)
    state = await evaluate_entry(db, 10)
    assert state["bot_started"] is False
    with pytest.raises(Exception) as exc:
        raise_for_state(state)
    assert exc.value.detail["code"] == "BOT_START_REQUIRED"


async def test_not_subscribed_returns_channel_list(db, telegram):
    await add_user(db, 11)
    await add_channel(db, "@alpha")
    await add_channel(db, "@beta")
    telegram.member("left")

    state = await evaluate_entry(db, 11)
    assert state["subscribed"] is False
    assert [c["id"] for c in state["channels"]] == ["@alpha", "@beta"]
    assert state["channels"][0]["invite_link"] == "https://t.me/alpha"

    with pytest.raises(Exception) as exc:
        raise_for_state(state)
    assert exc.value.detail["code"] == "SUBSCRIPTION_REQUIRED"
    assert len(exc.value.detail["channels"]) == 2


async def test_cached_ok_skips_telegram(db, telegram):
    await add_user(db, 12)
    await add_channel(db, "@alpha")
    telegram.member("member")

    first = await subscription.check_subscription(db, 12)
    await db.commit()
    assert first == {"ok": True, "missing": [], "cached": False, "degraded": False}
    assert len(telegram.calls) == 1

    second = await subscription.check_subscription(db, 12)
    assert second["ok"] is True and second["cached"] is True
    assert len(telegram.calls) == 1, "a fresh cache row must not hit Telegram"


async def test_cache_expires_after_ttl(db, telegram, monkeypatch):
    await add_user(db, 13)
    await add_channel(db, "@alpha")
    telegram.member("member")
    await subscription.check_subscription(db, 13)
    await db.commit()

    monkeypatch.setattr(subscription, "_now", lambda: NOW + subscription.CACHE_TTL_OK + 1)
    await subscription.check_subscription(db, 13)
    assert len(telegram.calls) == 2


async def test_telegram_5xx_fails_open_with_short_ttl(db, telegram, monkeypatch):
    await add_user(db, 14)
    await add_channel(db, "@alpha")
    telegram.transient(503)

    verdict = await subscription.check_subscription(db, 14)
    await db.commit()
    assert verdict["ok"] is True and verdict["degraded"] is True

    cursor = await db.execute("SELECT checked_at FROM subscription_checks WHERE user_id = 14")
    checked_at = int((await cursor.fetchone())[0])
    # Back-dated so the row ages out after CACHE_TTL_DEGRADED, not CACHE_TTL_OK.
    assert checked_at == NOW - (subscription.CACHE_TTL_OK - subscription.CACHE_TTL_DEGRADED)

    monkeypatch.setattr(subscription, "_now", lambda: NOW + subscription.CACHE_TTL_DEGRADED + 1)
    assert await subscription.read_cached(db, 14) is None


async def test_network_error_fails_open(db, telegram):
    await add_user(db, 15)
    await add_channel(db, "@alpha")
    telegram.script(lambda method, params: (0, None))  # httpx transport error

    verdict = await subscription.check_subscription(db, 15)
    assert verdict["ok"] is True and verdict["degraded"] is True


async def test_channel_where_bot_is_not_admin_is_skipped(db, telegram):
    await add_user(db, 16)
    await add_channel(db, "@broken")
    await add_channel(db, "@good")

    def handler(method, params):
        if params["chat_id"] == "@broken":
            return 400, {"ok": False, "description": "Bad Request: member list is inaccessible"}
        return 200, {"ok": True, "result": {"status": "member"}}

    telegram.script(handler)
    verdict = await subscription.check_subscription(db, 16)
    await db.commit()
    assert verdict["ok"] is True, "a channel the bot cannot police must not lock users out"

    cursor = await db.execute("SELECT last_check_ok FROM channels WHERE id = '@broken'")
    assert int((await cursor.fetchone())[0]) == 0


async def test_user_not_found_counts_as_missing(db, telegram):
    await add_user(db, 17)
    await add_channel(db, "@alpha")
    telegram.failure(400, "Bad Request: user not found")

    verdict = await subscription.check_subscription(db, 17)
    assert verdict["ok"] is False
    assert [c["id"] for c in verdict["missing"]] == ["@alpha"]


async def test_chat_id_wins_over_legacy_id(db, telegram):
    await add_user(db, 18)
    await add_channel(db, "@ALPHA", chat_id=-1001234567890)
    telegram.member("member")

    await subscription.check_subscription(db, 18)
    assert telegram.calls[0][1]["chat_id"] == "-1001234567890"


async def test_recheck_invalidates_the_cache(db, telegram):
    await add_user(db, 19)
    await add_channel(db, "@alpha")
    telegram.member("left")
    first = await subscription.check_subscription(db, 19)
    await db.commit()
    assert first["ok"] is False

    telegram.member("member")
    cached = await subscription.check_subscription(db, 19)
    assert cached["cached"] is True and cached["ok"] is False

    forced = await subscription.check_subscription(db, 19, force=True)
    await db.commit()
    assert forced["ok"] is True and forced["cached"] is False


# ---------------------------------------------------------------------------
# Gate ordering, admin bypass, referral
# ---------------------------------------------------------------------------


async def test_admin_bypasses_every_check(db, telegram):
    await add_user(db, 20, started=False)
    await add_channel(db, "@alpha")
    await db.execute(
        "INSERT INTO admins (user_id, role, added_at, disabled) VALUES (20, 'admin', ?, 0)",
        (NOW,),
    )
    await db.commit()

    state = await evaluate_entry(db, 20)
    assert state["is_admin"] is True and state["role"] == "admin"
    raise_for_state(state)  # must not raise
    assert telegram.calls == [], "the gate must not call Telegram for admins"


async def test_disabled_admin_does_not_bypass(db, telegram):
    await add_user(db, 21, started=False)
    await db.execute(
        "INSERT INTO admins (user_id, role, added_at, disabled) VALUES (21, 'admin', ?, 1)",
        (NOW,),
    )
    await db.commit()
    state = await evaluate_entry(db, 21)
    assert state["is_admin"] is False
    with pytest.raises(Exception) as exc:
        raise_for_state(state)
    assert exc.value.detail["code"] == "BOT_START_REQUIRED"


async def test_referral_gate_runs_last(db, telegram):
    await add_user(db, 22)
    await db.execute(
        "UPDATE webapp_admin_settings SET referral_enabled = 1, referral_required_count = 3"
    )
    await db.commit()

    state = await evaluate_entry(db, 22)
    assert state["subscribed"] is True  # no channels configured
    assert state["referral"] == {"enabled": True, "required": 3, "count": 0, "unlocked": False}
    with pytest.raises(Exception) as exc:
        raise_for_state(state)
    assert exc.value.detail["code"] == "REFERRAL_LOCKED"
    assert exc.value.detail["required"] == 3


async def test_banned_user_is_reported_first(db, telegram):
    await add_user(db, 23)
    cursor = await db.execute("PRAGMA table_info(users)")
    if "banned" not in {row[1] for row in await cursor.fetchall()}:
        # m009 (USERS agent) adds it; this test must pass either way.
        await db.execute("ALTER TABLE users ADD COLUMN banned INTEGER NOT NULL DEFAULT 0")
    await db.execute("UPDATE users SET banned = 1 WHERE user_id = 23")
    await db.commit()

    state = await evaluate_entry(db, 23)
    assert state["banned"] is True
    with pytest.raises(Exception) as exc:
        raise_for_state(state)
    assert exc.value.detail["code"] == "USER_BANNED"


async def test_missing_started_at_column_does_not_lock_anyone_out(db):
    """An un-migrated database must fail open, never wall every user off."""
    await add_user(db, 24)
    started, banned = await entry_gate._user_flags(db, 24)
    assert (started, banned) == (True, False)

    await db.execute("CREATE TABLE users_new (user_id INTEGER PRIMARY KEY, date INTEGER)")
    await db.execute("DROP TABLE users")
    await db.execute("ALTER TABLE users_new RENAME TO users")
    await db.commit()
    assert await entry_gate._user_flags(db, 24) == (True, False)


# ---------------------------------------------------------------------------
# require_entry as a router dependency
# ---------------------------------------------------------------------------


def build_app(db, user_id: int) -> FastAPI:
    app = FastAPI()

    async def fake_user():
        return {"user_id": user_id, "lang": "uz"}

    @app.get("/probe", dependencies=[Depends(require_entry)])
    async def probe(request: Request):
        return {"ok": True}

    from webapp.core.auth import current_user

    app.dependency_overrides[current_user] = fake_user
    app.dependency_overrides[get_db] = lambda: db
    return app


async def test_require_entry_blocks_and_allows(db, telegram):
    await add_user(db, 30, started=False)
    with TestClient(build_app(db, 30)) as client:
        response = client.get("/probe")
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "BOT_START_REQUIRED"

    await add_user(db, 30, started=True)
    with TestClient(build_app(db, 30)) as client:
        assert client.get("/probe").status_code == 200


# ---------------------------------------------------------------------------
# Link parsing matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, kind, value",
    [
        ("@bandlikuz", "username", "bandlikuz"),
        ("bandlikuz", "username", "bandlikuz"),
        ("  @Bandlik_uz  ", "username", "Bandlik_uz"),
        ("t.me/bandlikuz", "username", "bandlikuz"),
        ("https://t.me/bandlikuz", "username", "bandlikuz"),
        ("https://www.t.me/bandlikuz/", "username", "bandlikuz"),
        ("https://t.me/s/bandlikuz", "username", "bandlikuz"),
        ("https://telegram.me/bandlikuz?x=1", "username", "bandlikuz"),
        ("https://t.me/bandlikuz/42", "username", "bandlikuz"),
    ],
)
def test_parse_username_forms(raw, kind, value):
    parsed = parse_channel_link(raw)
    assert (parsed.kind, parsed.username) == (kind, value)
    assert parsed.target == f"@{value}"


@pytest.mark.parametrize(
    "raw",
    ["https://t.me/+AbCdEf12345", "t.me/+AbCdEf12345", "https://t.me/joinchat/AbCdEf12345"],
)
def test_parse_invite_forms(raw):
    parsed = parse_channel_link(raw)
    assert parsed.kind == "invite"
    assert parsed.invite_link.startswith("https://t.me/")
    assert parsed.target == ""


@pytest.mark.parametrize("raw, chat_id", [("-1001234567890", -1001234567890), ("100200300", 100200300)])
def test_parse_chat_id_forms(raw, chat_id):
    parsed = parse_channel_link(raw)
    assert (parsed.kind, parsed.chat_id) == ("chat_id", chat_id)
    assert parsed.target == str(chat_id)


@pytest.mark.parametrize("raw", ["", "   ", "@ab", "https://example.com/foo", "+12345", "??"])
def test_parse_rejects_garbage(raw):
    with pytest.raises(ValueError):
        parse_channel_link(raw)


# ---------------------------------------------------------------------------
# Admin channels router
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_client(db, monkeypatch):
    from webapp.core import auth

    app = FastAPI()
    app.include_router(admin_channels.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db

    async def fake_admin(request: Request = None):
        return {"user_id": 1, "role": "owner", "user": {"user_id": 1}}

    # require_role builds a fresh dependency per route; override each of them.
    for route in app.routes:
        for dependant in getattr(getattr(route, "dependant", None), "dependencies", []):
            if getattr(dependant.call, "__require_role__", None):
                app.dependency_overrides[dependant.call] = fake_admin

    monkeypatch.setattr(auth, "require_admin", fake_admin)
    with TestClient(app) as client:
        yield client


async def test_add_channel_validates_and_stores(db, telegram, admin_client):
    def handler(method, params):
        if method == "getChat":
            return 200, {
                "ok": True,
                "result": {"id": -1001, "title": "Bandlik", "username": "bandlikuz"},
            }
        if method == "getMe":
            return 200, {"ok": True, "result": {"id": 777}}
        return 200, {"ok": True, "result": {"status": "administrator"}}

    telegram.script(handler)
    response = admin_client.post("/api/admin/channels", json={"link": "t.me/bandlikuz"})
    assert response.status_code == 200, response.text
    channel = response.json()["channel"]
    assert channel["id"] == "@bandlikuz"
    assert channel["chat_id"] == -1001
    assert channel["invite_link"] == "https://t.me/bandlikuz"
    assert channel["last_check_ok"] is True

    duplicate = admin_client.post("/api/admin/channels", json={"link": "@bandlikuz"})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "CHANNEL_EXISTS"


async def test_add_channel_rejects_when_bot_is_not_admin(db, telegram, admin_client):
    def handler(method, params):
        if method == "getChat":
            return 200, {"ok": True, "result": {"id": -1002, "title": "X", "username": "x_channel"}}
        if method == "getMe":
            return 200, {"ok": True, "result": {"id": 777}}
        return 200, {"ok": True, "result": {"status": "left"}}

    telegram.script(handler)
    response = admin_client.post("/api/admin/channels", json={"link": "@x_channel"})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "CHANNEL_BOT_NOT_ADMIN"

    cursor = await db.execute("SELECT COUNT(*) FROM channels")
    assert (await cursor.fetchone())[0] == 0


async def test_add_channel_rejects_invite_without_chat_id(db, telegram, admin_client):
    telegram.script(lambda method, params: (200, {"ok": True, "result": {}}))
    response = admin_client.post("/api/admin/channels", json={"link": "https://t.me/+abcdef"})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "CHANNEL_INVALID"
    assert detail["reason"] == "invite_link_requires_chat_id"


async def test_getme_is_cached_across_calls(db, telegram, admin_client):
    def handler(method, params):
        if method == "getChat":
            return 200, {"ok": True, "result": {"id": -abs(hash(params["chat_id"])) % 10000,
                                                "title": "T", "username": params["chat_id"].lstrip("@")}}
        if method == "getMe":
            return 200, {"ok": True, "result": {"id": 777}}
        return 200, {"ok": True, "result": {"status": "administrator"}}

    telegram.script(handler)
    admin_client.post("/api/admin/channels", json={"link": "@one_channel"})
    admin_client.post("/api/admin/channels", json={"link": "@two_channel"})
    assert len([c for c in telegram.calls if c[0] == "getMe"]) == 1


async def test_patch_delete_and_check(db, telegram, admin_client):
    await add_channel(db, "@alpha", chat_id=-1005)

    patched = admin_client.patch("/api/admin/channels/@alpha", json={"enabled": False})
    assert patched.status_code == 200 and patched.json()["enabled"] is False
    cursor = await db.execute("SELECT enabled FROM channels WHERE id = '@alpha'")
    assert int((await cursor.fetchone())[0]) == 0

    def handler(method, params):
        if method == "getChat":
            return 200, {"ok": True, "result": {"id": -1005, "title": "Alpha", "username": "alpha"}}
        if method == "getMe":
            return 200, {"ok": True, "result": {"id": 777}}
        return 400, {"ok": False, "description": "Bad Request: chat not found"}

    telegram.script(handler)
    checked = admin_client.post("/api/admin/channels/@alpha/check")
    assert checked.json()["status"] == "bot_not_admin"
    assert checked.json()["ok"] is False

    # A delete must drop cached verdicts computed against the old channel set.
    await db.execute(
        "INSERT INTO subscription_checks (user_id, checked_at, ok, missing_json) "
        "VALUES (1, ?, 0, ?)",
        (NOW, json.dumps([{"id": "@alpha"}])),
    )
    await db.commit()
    assert admin_client.delete("/api/admin/channels/@alpha").status_code == 200
    cursor = await db.execute("SELECT COUNT(*) FROM subscription_checks")
    assert (await cursor.fetchone())[0] == 0


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


async def test_m006_backfills_started_at(tmp_path):
    async with aiosqlite.connect(tmp_path / "legacy.sqlite3") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY, date INTEGER)")
        await conn.execute("CREATE TABLE channels (id TEXT PRIMARY KEY)")
        await conn.execute("INSERT INTO users (user_id, date) VALUES (5, 1234)")
        await conn.execute("INSERT INTO channels (id) VALUES ('@LEGACY')")
        await conn.commit()

        await run_migrations(conn)

        cursor = await conn.execute("SELECT started_at FROM users WHERE user_id = 5")
        assert int((await cursor.fetchone())[0]) == 1234
        cursor = await conn.execute("SELECT enabled, chat_id FROM channels WHERE id = '@LEGACY'")
        row = await cursor.fetchone()
        assert int(row["enabled"]) == 1 and row["chat_id"] is None
        assert await run_migrations(conn) == []


def test_time_is_not_frozen_globally():
    """Guard: the fixtures patch subscription._now, never time.time itself."""
    assert abs(time.time() - NOW) > 1000
