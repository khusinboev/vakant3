"""One end-to-end pass over the real ``webapp.main.app``.

Every other test file builds a small FastAPI app around a single router with
``get_db`` overridden. This one does the opposite: it boots the *actual*
application — lifespan, ``init_db``, migrations, the connection pool, the
limiter middleware, every router — against a throwaway SQLite file and walks a
user and an admin through the whole product in the order they really happen:

    launch -> locked (no /start) -> locked (not subscribed) -> allowed
    -> admin bootstrap -> settings versioning -> confirmation tokens
    -> money -> moderation -> content -> broadcast -> channels

The tests share one module-scoped database on purpose: scenario N's state is
scenario N+1's precondition, which is exactly the coupling a per-router unit
test cannot catch (CLAUDE.md "One SQLite file, two processes").

Nothing leaves the process. Every Telegram round trip goes through
``webapp.core.subscription._request`` (the single httpx seam, stubbed here),
osonish.uz is stubbed at the jobs router, and ``httpx.AsyncClient.request`` /
``aiohttp.ClientSession._request`` are both replaced with a raising stub so an
unstubbed call fails loudly instead of hitting the network.

Schema note: ``saves``/``regions``/``districts``/``referral_payouts`` belong to
the bot process (``StatsMiddleware.init_db``), not to the API, so they are
created here before the app boots — the same way they already exist in
production when the API starts.
"""

import asyncio
import hashlib
import hmac
import json
import time
import types
import urllib.parse
from contextlib import asynccontextmanager
from pathlib import Path

import aiohttp
import aiosqlite
import httpx
import pytest
from fastapi.testclient import TestClient

from src.functions import broadcast_worker
from webapp.core import entry_gate, subscription
from webapp.core.config import DB_PATH, get_settings
from webapp.main import app
from webapp.routers import jobs as jobs_router

USER_ID = 7_710_001
OWNER_ID = 7_710_002
OUTSIDER_ID = 7_710_003
BOT_ID = 4_242_424

REQUIRED_CHANNEL = "@e2e_required"
SEEDED_ARTICLE_ID = "worktime-norm"


# ---------------------------------------------------------------------------
# Tables the bot process owns (see the module docstring)
# ---------------------------------------------------------------------------

BOT_OWNED_DDL = (
    "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, date INTEGER, "
    "lang TEXT, region TEXT, district TEXT, specs TEXT, money INTEGER)",
    "CREATE TABLE IF NOT EXISTS channels (id TEXT PRIMARY KEY)",
    "CREATE TABLE IF NOT EXISTS saves (user_id INTEGER, save_id INTEGER, "
    "PRIMARY KEY (user_id, save_id))",
    "CREATE TABLE IF NOT EXISTS regions (soato TEXT PRIMARY KEY, name_uz TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS districts (soato TEXT PRIMARY KEY, "
    "region_soato TEXT NOT NULL, name_uz TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS referral_payouts (user_id INTEGER PRIMARY KEY, "
    "inviter_id INTEGER NOT NULL, amount INTEGER NOT NULL, ts INTEGER NOT NULL)",
)


# ---------------------------------------------------------------------------
# Small synchronous DB helpers (the app owns the pool; these open their own
# connection to the same WAL file)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def open_db():
    conn = await aiosqlite.connect(str(DB_PATH))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        await conn.close()


def query(sql: str, params: tuple = ()) -> list[dict]:
    async def run():
        async with open_db() as conn:
            cursor = await conn.execute(sql, params)
            return [dict(row) for row in await cursor.fetchall()]

    return asyncio.run(run())


def execute(sql: str, params: tuple = ()) -> None:
    async def run():
        async with open_db() as conn:
            await conn.execute(sql, params)
            await conn.commit()

    asyncio.run(run())


def _reset_database_file() -> None:
    for suffix in ("", "-wal", "-shm"):
        path = Path(f"{DB_PATH}{suffix}")
        if path.exists():
            path.unlink()

    async def build():
        async with open_db() as conn:
            for ddl in BOT_OWNED_DDL:
                await conn.execute(ddl)
            await conn.commit()

    asyncio.run(build())


# ---------------------------------------------------------------------------
# Telegram stub
# ---------------------------------------------------------------------------


class TelegramStub:
    """Stand-in for ``subscription._request`` with a per-method call log.

    ``member_status`` answers ``getChatMember`` for a *user*, ``bot_status``
    for the bot itself (channel validation asks about ``getMe().id``).
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.member_status = "member"
        self.bot_status = "administrator"

    async def request(self, method: str, params: dict):
        self.calls.append((method, dict(params)))
        if method == "getMe":
            return 200, {"ok": True, "result": {"id": BOT_ID, "username": "e2e_bot"}}
        if method == "getChat":
            name = str(params.get("chat_id") or "").lstrip("@")
            return 200, {
                "ok": True,
                "result": {"id": -100_000 - len(name), "title": f"Title {name}", "username": name},
            }
        if method == "getChatMember":
            is_bot = int(params.get("user_id") or 0) == BOT_ID
            status = self.bot_status if is_bot else self.member_status
            return 200, {"ok": True, "result": {"status": status}}
        return 200, {"ok": True, "result": {}}

    def count(self, method: str) -> int:
        return sum(1 for name, _ in self.calls if name == method)


class FakeBot:
    """Just enough of the aiogram bot for the broadcast worker."""

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, user_id, text, reply_markup=None):
        self.sent.append((int(user_id), str(text)))
        return types.SimpleNamespace(message_id=len(self.sent))


# ---------------------------------------------------------------------------
# initData
# ---------------------------------------------------------------------------


def init_data_for(user_id: int, *, lang: str = "uz") -> str:
    """A valid ``Telegram.WebApp.initData`` string, signed with the live TOKEN."""
    token = get_settings().TOKEN
    fields = {
        "auth_date": str(int(time.time())),
        "query_id": "AAE-e2e",
        "user": json.dumps(
            {
                "id": int(user_id),
                "first_name": f"E2E{user_id}",
                "username": f"e2e{user_id}",
                "language_code": lang,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urllib.parse.urlencode(fields)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def env():
    """Fresh database + the real app booted + every outbound call stubbed."""
    monkeypatch = pytest.MonkeyPatch()
    _reset_database_file()

    telegram = TelegramStub()
    monkeypatch.setattr(subscription, "_request", telegram.request)
    subscription.reset_bot_id_cache()
    entry_gate.reset_users_columns_cache()

    async def _no_network(*args, **kwargs):  # pragma: no cover - guard
        raise AssertionError("an outbound HTTP call escaped the stubs")

    monkeypatch.setattr(httpx.AsyncClient, "request", _no_network)
    monkeypatch.setattr(aiohttp.ClientSession, "_request", _no_network)

    async def fake_osonish_list(**kwargs):
        return [], 1

    async def fake_cache_get(key):
        return None

    async def fake_cache_set(key, value, ttl=0):
        return None

    monkeypatch.setattr(jobs_router, "fetch_osonish_list", fake_osonish_list)
    monkeypatch.setattr(jobs_router, "cache_get", fake_cache_get)
    monkeypatch.setattr(jobs_router, "cache_set", fake_cache_set)

    # ADMIN_IDS bootstraps the first owner row (webapp/core/auth.py).
    monkeypatch.setattr(get_settings(), "ADMIN_IDS", str(OWNER_ID), raising=False)

    # slowapi is in-memory and keyed on the (constant) test client IP.
    previous_limiter = app.state.limiter.enabled
    app.state.limiter.enabled = False

    with TestClient(app) as client:
        yield types.SimpleNamespace(client=client, tg=telegram)

    app.state.limiter.enabled = previous_limiter
    monkeypatch.undo()
    subscription.reset_bot_id_cache()
    entry_gate.reset_users_columns_cache()


@pytest.fixture(scope="module")
def tokens() -> dict[str, str]:
    """Session tokens minted in scenario 1/3 and reused by the later ones."""
    return {}


def auth(tokens: dict, who: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens[who]}"}


def login(client: TestClient, user_id: int) -> str:
    response = client.post("/api/auth/tg-webapp", json={"init_data": init_data_for(user_id)})
    assert response.status_code == 200, response.text
    return response.json()["session_token"]


def confirm_token(client: TestClient, headers: dict, action: str, params: dict) -> str:
    response = client.post(
        "/api/admin/confirm", headers=headers, json={"action": action, "params": params}
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


def detail(response) -> dict:
    body = response.json()
    assert isinstance(body.get("detail"), dict), body
    return body["detail"]


# ---------------------------------------------------------------------------
# 1. A launch that never went through /start
# ---------------------------------------------------------------------------


def test_01_launch_without_start_is_locked(env, tokens):
    """The Main App button opens the Mini App without a /start — API must lock it."""
    tokens["user"] = login(env.client, USER_ID)
    headers = auth(tokens, "user")

    response = env.client.get("/api/jobs/search", headers=headers)
    assert response.status_code == 403, response.text
    assert detail(response)["code"] == "BOT_START_REQUIRED"

    gate = env.client.get("/api/auth/gate", headers=headers)
    assert gate.status_code == 200, gate.text
    body = gate.json()
    assert body["bot_started"] is False
    assert body["is_admin"] is False

    row = query("SELECT started_at FROM users WHERE user_id = ?", (USER_ID,))
    assert row and row[0]["started_at"] is None


# ---------------------------------------------------------------------------
# 2. Forced subscription
# ---------------------------------------------------------------------------


def test_02_subscription_gate_and_cache(env, tokens):
    headers = auth(tokens, "user")

    # The bot's /start handler writes exactly this column.
    execute(
        "UPDATE users SET started_at = ? WHERE user_id = ? AND started_at IS NULL",
        (int(time.time()), USER_ID),
    )
    execute(
        "INSERT OR REPLACE INTO channels (id, title, username, invite_link, enabled) "
        "VALUES (?, ?, ?, ?, 1)",
        (REQUIRED_CHANNEL, "E2E kanal", REQUIRED_CHANNEL.lstrip("@"), f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}"),
    )

    env.tg.member_status = "left"
    response = env.client.get("/api/jobs/search", headers=headers)
    assert response.status_code == 403, response.text
    payload = detail(response)
    assert payload["code"] == "SUBSCRIPTION_REQUIRED"
    assert [c["id"] for c in payload["channels"]] == [REQUIRED_CHANNEL]
    assert payload["channels"][0]["invite_link"] == f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}"

    # Subscribing needs an explicit recheck: the "not subscribed" verdict is cached.
    env.tg.member_status = "member"
    still_locked = env.client.get("/api/auth/gate", headers=headers)
    assert still_locked.json()["subscribed"] is False

    rechecked = env.client.post("/api/auth/gate/recheck", headers=headers)
    assert rechecked.status_code == 200, rechecked.text
    assert rechecked.json()["subscribed"] is True

    allowed = env.client.get("/api/jobs/search", headers=headers)
    assert allowed.status_code == 200, allowed.text

    calls_before = env.tg.count("getChatMember")
    assert calls_before >= 2, "guard: the stub must really have been consulted"
    assert env.client.get("/api/jobs/search", headers=headers).status_code == 200
    assert env.client.get("/api/auth/gate", headers=headers).json()["subscribed"] is True
    assert env.tg.count("getChatMember") == calls_before, (
        "a fresh subscription_checks row must not hit Telegram again"
    )


# ---------------------------------------------------------------------------
# 3. Admin bootstrap
# ---------------------------------------------------------------------------


def test_03_admin_bootstrap_and_access_control(env, tokens):
    assert query("SELECT 1 FROM admins") == []

    tokens["owner"] = login(env.client, OWNER_ID)
    tokens["outsider"] = login(env.client, OUTSIDER_ID)

    state = env.client.get("/api/admin/state", headers=auth(tokens, "owner"))
    assert state.status_code == 200, state.text
    assert state.json()["is_admin"] is True
    assert state.json()["role"] == "owner"
    assert query("SELECT user_id, role, disabled FROM admins") == [
        {"user_id": OWNER_ID, "role": "owner", "disabled": 0}
    ]

    # Admin routes are Bearer-only; initData alone is replayable for its window.
    init_only = env.client.get(
        "/api/admin/state", headers={"X-Telegram-Init-Data": init_data_for(OWNER_ID)}
    )
    assert init_only.status_code == 401, init_only.text
    assert detail(init_only)["code"] == "AUTH_REQUIRED"

    outsider = env.client.get("/api/admin/state", headers=auth(tokens, "outsider"))
    assert outsider.status_code == 403, outsider.text
    assert detail(outsider)["code"] == "ADMIN_REQUIRED"


# ---------------------------------------------------------------------------
# 4. Optimistic settings concurrency
# ---------------------------------------------------------------------------


def test_04_settings_patch_is_versioned_and_audited(env, tokens):
    headers = auth(tokens, "owner")
    version = env.client.get("/api/admin/state", headers=headers).json()["version"]

    first = env.client.patch(
        "/api/admin/state",
        headers=headers,
        json={"expected_version": version, "pro_price": 3000, "referral_reward": 1500},
    )
    assert first.status_code == 200, first.text
    assert first.json()["version"] == version + 1
    assert first.json()["pro_price"] == 3000

    stale = env.client.patch(
        "/api/admin/state",
        headers=headers,
        json={"expected_version": version, "pro_price": 9999},
    )
    assert stale.status_code == 409, stale.text
    assert detail(stale)["code"] == "SETTINGS_CONFLICT"
    assert detail(stale)["version"] == version + 1
    assert env.client.get("/api/admin/state", headers=headers).json()["pro_price"] == 3000

    audit = query(
        "SELECT actor_id, target_type, payload_json FROM admin_audit_log WHERE action = ?",
        ("settings.patch",),
    )
    assert len(audit) == 1, audit
    assert audit[0]["actor_id"] == OWNER_ID
    assert audit[0]["target_type"] == "settings"
    assert "pro_price" in json.loads(audit[0]["payload_json"])["diff"]


# ---------------------------------------------------------------------------
# 5. Confirmation tokens + ledger
# ---------------------------------------------------------------------------


def test_05_confirmation_token_guards_money(env, tokens):
    headers = auth(tokens, "owner")
    params = {"user_id": USER_ID, "amount": 5000}
    body = {**params, "note": "e2e credit"}

    token = confirm_token(env.client, headers, "wallet.add_balance", params)

    refused = env.client.post("/api/wallet/admin/add-balance", headers=headers, json=body)
    assert refused.status_code == 403, refused.text
    assert detail(refused)["code"] == "CONFIRMATION_REQUIRED"
    assert detail(refused)["action"] == "wallet.add_balance"
    assert query("SELECT 1 FROM wallet_transactions") == []

    granted = env.client.post(
        "/api/wallet/admin/add-balance",
        headers={**headers, "X-Confirm-Token": token},
        json=body,
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["new_balance"] == 5000

    rows = query(
        "SELECT kind, amount, balance_after, actor_id, note FROM wallet_transactions "
        "WHERE user_id = ?",
        (USER_ID,),
    )
    assert rows == [
        {
            "kind": "admin_credit",
            "amount": 5000,
            "balance_after": 5000,
            "actor_id": OWNER_ID,
            "note": "e2e credit",
        }
    ]
    assert query("SELECT user_balance FROM users WHERE user_id = ?", (USER_ID,))[0][
        "user_balance"
    ] == 5000
    assert query(
        "SELECT target_id FROM admin_audit_log WHERE action = ?", ("wallet.add_balance",)
    ) == [{"target_id": str(USER_ID)}]

    history = env.client.get("/api/wallet/transactions", headers=auth(tokens, "user"))
    assert history.status_code == 200, history.text
    items = history.json()["items"]
    assert [item["kind"] for item in items] == ["admin_credit"]
    assert items[0]["balance_after"] == 5000


# ---------------------------------------------------------------------------
# 6. Pro activation
# ---------------------------------------------------------------------------


def test_06_pro_activation_is_charged_once(env, tokens):
    headers = auth(tokens, "user")

    wallet = env.client.get("/api/wallet", headers=headers)
    assert wallet.status_code == 200, wallet.text
    assert wallet.json() == {
        "balance": 5000,
        "is_pro": False,
        "pro_price": 3000,
        "referral_reward": 1500,
    }

    activated = env.client.post("/api/wallet/activate-pro", headers=headers)
    assert activated.status_code == 200, activated.text
    assert activated.json()["balance"] == 2000
    assert activated.json()["is_pro"] is True

    rows = query(
        "SELECT kind, amount, balance_after, price_snapshot FROM wallet_transactions "
        "WHERE user_id = ? AND kind = 'pro_activation'",
        (USER_ID,),
    )
    assert rows == [
        {"kind": "pro_activation", "amount": -3000, "balance_after": 2000, "price_snapshot": 3000}
    ]

    again = env.client.post("/api/wallet/activate-pro", headers=headers)
    assert again.status_code == 400, again.text
    assert detail(again)["code"] == "ALREADY_PRO"
    assert query("SELECT user_balance FROM users WHERE user_id = ?", (USER_ID,))[0][
        "user_balance"
    ] == 2000


# ---------------------------------------------------------------------------
# 7. Admin users API + ban
# ---------------------------------------------------------------------------


def test_07_admin_users_list_detail_and_ban(env, tokens):
    headers = auth(tokens, "owner")

    listing = env.client.get("/api/admin/users", headers=headers, params={"q": str(USER_ID)})
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]
    assert [item["user_id"] for item in items] == [USER_ID]
    assert items[0]["is_pro"] is True
    assert items[0]["balance"] == 2000
    assert items[0]["banned"] is False

    detail_response = env.client.get(f"/api/admin/users/{USER_ID}", headers=headers)
    assert detail_response.status_code == 200, detail_response.text
    body = detail_response.json()
    assert body["user"]["user_id"] == USER_ID
    assert body["wallet"]["balance"] == 2000 and body["wallet"]["is_pro"] is True
    assert body["counts"]["saves"] == 0
    assert body["counts"]["referrals"] == 0
    assert [tx["kind"] for tx in body["recent_transactions"]] == [
        "pro_activation",
        "admin_credit",
    ]

    banned = env.client.post(
        f"/api/admin/users/{USER_ID}/ban", headers=headers, json={"banned": True, "reason": "e2e"}
    )
    assert banned.status_code == 200, banned.text
    assert banned.json()["banned"] is True

    locked = env.client.get("/api/jobs/search", headers=auth(tokens, "user"))
    assert locked.status_code == 403, locked.text
    # The gate reports the ban before /start, subscription and the referral gate.
    assert detail(locked)["code"] == "USER_BANNED"
    assert env.client.get("/api/auth/gate", headers=auth(tokens, "user")).json()["banned"] is True

    assert query(
        "SELECT target_id FROM admin_audit_log WHERE action = ?", ("users.ban",)
    ) == [{"target_id": str(USER_ID)}]

    unbanned = env.client.post(
        f"/api/admin/users/{USER_ID}/ban", headers=headers, json={"banned": False}
    )
    assert unbanned.status_code == 200, unbanned.text
    assert env.client.get("/api/jobs/search", headers=auth(tokens, "user")).status_code == 200


# ---------------------------------------------------------------------------
# 8. Content
# ---------------------------------------------------------------------------


def test_08_public_content_hides_unpublished_articles(env, tokens):
    russian = env.client.get("/api/content/laws", params={"lang": "ru"})
    assert russian.status_code == 200, russian.text
    body = russian.json()
    assert body["categories"], "m007 must seed the categories"
    published_ids = {article["id"] for article in body["articles"]}
    assert SEEDED_ARTICLE_ID in published_ids

    uzbek = env.client.get("/api/content/laws", params={"lang": "uz"}).json()
    ru_titles = {a["id"]: a["title"] for a in body["articles"]}
    uz_titles = {a["id"]: a["title"] for a in uzbek["articles"]}
    assert ru_titles[SEEDED_ARTICLE_ID] != uz_titles[SEEDED_ARTICLE_ID], (
        "ru must be served from the *_ru columns, not the uz fallback"
    )

    headers = auth(tokens, "owner")
    current = env.client.get(f"/api/admin/content/articles/{SEEDED_ARTICLE_ID}", headers=headers)
    assert current.status_code == 200, current.text
    payload = {
        key: current.json()[key]
        for key in ("category_id", "sort_order", "source_url", "title", "summary", "full_text", "source_label")
    }
    payload["published"] = False

    updated = env.client.put(
        f"/api/admin/content/articles/{SEEDED_ARTICLE_ID}", headers=headers, json=payload
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["published"] is False

    after = env.client.get("/api/content/laws", params={"lang": "ru"}).json()
    assert SEEDED_ARTICLE_ID not in {a["id"] for a in after["articles"]}
    assert len(after["articles"]) == len(published_ids) - 1

    hidden = env.client.get(f"/api/content/laws/{SEEDED_ARTICLE_ID}")
    assert hidden.status_code == 404, hidden.text

    # The admin list still sees it, and the mutation is audited.
    admin_ids = {a["id"] for a in env.client.get("/api/admin/content/articles", headers=headers).json()["items"]}
    assert SEEDED_ARTICLE_ID in admin_ids
    assert query(
        "SELECT target_id FROM admin_audit_log WHERE action = ?", ("content.article.update",)
    ) == [{"target_id": SEEDED_ARTICLE_ID}]


# ---------------------------------------------------------------------------
# 9. Broadcast: API materializes, the bot worker delivers
# ---------------------------------------------------------------------------


def test_09_broadcast_create_queue_and_worker(env, tokens):
    headers = auth(tokens, "owner")
    token = confirm_token(
        env.client, headers, "broadcast.create", {"kind": "text", "segment": "test_admins"}
    )

    created = env.client.post(
        "/api/admin/broadcasts",
        headers={**headers, "X-Confirm-Token": token},
        json={
            "kind": "text",
            "text": "E2E <b>xabar</b>",
            "segment": "test_admins",
            "buttons": [{"text": "Ochish", "url": "https://t.me/e2e_required"}],
        },
    )
    assert created.status_code == 200, created.text
    broadcast_id = created.json()["id"]
    assert created.json()["status"] == "draft"

    qtok = confirm_token(env.client, headers, "broadcast.queue", {"broadcast_id": broadcast_id})
    queued = env.client.post(
        f"/api/admin/broadcasts/{broadcast_id}/queue",
        headers={**headers, "X-Confirm-Token": qtok},
        json={"broadcast_id": broadcast_id},
    )
    assert queued.status_code == 200, queued.text
    total = queued.json()["total"]
    assert total == 1
    assert queued.json()["status"] == "queued"

    targets = query(
        "SELECT user_id, status FROM broadcast_targets WHERE broadcast_id = ?", (broadcast_id,)
    )
    assert targets == [{"user_id": OWNER_ID, "status": "pending"}]

    bot = FakeBot()
    worked = asyncio.run(broadcast_worker.process_once(bot, connect=open_db))
    assert worked is True
    assert [user_id for user_id, _ in bot.sent] == [OWNER_ID]
    assert "E2E <b>xabar</b>" in bot.sent[0][1]

    row = query(
        "SELECT status, total, sent, failed, blocked FROM broadcasts WHERE id = ?",
        (broadcast_id,),
    )[0]
    assert row == {
        "status": "done",
        "total": total,
        "sent": total,
        "failed": 0,
        "blocked": 0,
    }

    progress = env.client.get(f"/api/admin/broadcasts/{broadcast_id}", headers=headers)
    assert progress.status_code == 200, progress.text
    assert progress.json()["status"] == "done"
    assert progress.json()["sent"] == total


# ---------------------------------------------------------------------------
# 10. Channels admin
# ---------------------------------------------------------------------------


def test_10_admin_channels_add_duplicate_and_not_admin(env, tokens):
    headers = auth(tokens, "owner")

    env.tg.bot_status = "administrator"
    added = env.client.post("/api/admin/channels", headers=headers, json={"link": "t.me/e2e_public"})
    assert added.status_code == 200, added.text
    channel = added.json()["channel"]
    assert channel["id"] == "@e2e_public"
    assert channel["title"] == "Title e2e_public"
    assert channel["enabled"] is True
    assert channel["last_check_ok"] is True
    assert channel["added_by"] == OWNER_ID

    duplicate = env.client.post("/api/admin/channels", headers=headers, json={"link": "@e2e_public"})
    assert duplicate.status_code == 409, duplicate.text
    assert detail(duplicate)["code"] == "CHANNEL_EXISTS"

    env.tg.bot_status = "left"
    refused = env.client.post("/api/admin/channels", headers=headers, json={"link": "@e2e_orphan"})
    assert refused.status_code == 400, refused.text
    assert detail(refused)["code"] == "CHANNEL_BOT_NOT_ADMIN"
    assert query("SELECT id FROM channels WHERE id = ?", ("@e2e_orphan",)) == []

    listed = env.client.get("/api/admin/channels", headers=headers)
    assert listed.status_code == 200, listed.text
    assert {row["id"] for row in listed.json()["items"]} == {REQUIRED_CHANNEL, "@e2e_public"}
