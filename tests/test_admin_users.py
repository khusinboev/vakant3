"""Tests for the admin Users module (``webapp/routers/admin_users.py``).

The app under test contains ONLY this router: ``require_role`` /
``require_confirmation`` / ``get_db`` are overridden, so nothing here depends on
the rest of the Phase 0 wiring. ``webapp.core.audit`` and ``webapp.core.confirm``
are stubbed into ``sys.modules`` when they are not importable yet (the stub
writes a real ``admin_audit_log`` row, so the audit assertions hold either way).
"""

from __future__ import annotations

import base64
import importlib
import json
import sys
import time
import types

import aiosqlite
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.db.migrate import run_migrations

ADMIN = {"user_id": 777, "role": "owner", "user": {"user_id": 777}}

# --- users DDL copied from src/middleware/middlewares.py (+ the columns the
# API's init_db adds); m009 adds banned/banned_reason/last_seen_at/pro_until.
USERS_DDL = """
CREATE TABLE IF NOT EXISTS users (
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
    photo_url TEXT
)
"""

BASE_TABLES = (
    USERS_DDL,
    "CREATE TABLE IF NOT EXISTS channels (id TEXT PRIMARY KEY)",
    "CREATE TABLE IF NOT EXISTS saves (user_id INTEGER, save_id INTEGER, PRIMARY KEY (user_id, save_id))",
    """
    CREATE TABLE IF NOT EXISTS referral_payouts (
        user_id INTEGER PRIMARY KEY, inviter_id INTEGER NOT NULL,
        amount INTEGER NOT NULL, ts INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS resume_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        event_name TEXT NOT NULL, step TEXT, meta_json TEXT, created_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS resume_exports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, fmt TEXT NOT NULL,
        template_id TEXT NOT NULL, status TEXT NOT NULL, error_text TEXT,
        created_at INTEGER NOT NULL, completed_at INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notification_settings (
        user_id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
    )
    """,
)

# From CONTRACT_P0 — used only if the ledger/audit migrations are not in place.
WALLET_TX_DDL = """
CREATE TABLE IF NOT EXISTS wallet_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, kind TEXT NOT NULL,
    amount INTEGER NOT NULL, balance_after INTEGER NOT NULL, price_snapshot INTEGER,
    actor_id INTEGER, note TEXT, created_at INTEGER NOT NULL
)
"""
AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS admin_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id INTEGER NOT NULL, action TEXT NOT NULL,
    target_type TEXT, target_id TEXT, payload_json TEXT, ip TEXT, created_at INTEGER NOT NULL
)
"""


def _install_phase0_stubs() -> None:
    """Stub the Phase 0 modules this router imports, when they do not exist yet."""
    try:  # pragma: no cover - depends on what has landed
        importlib.import_module("webapp.core.audit")
    except ImportError:  # pragma: no cover
        module = types.ModuleType("webapp.core.audit")

        async def log_admin_action(
            db, *, actor_id, action, target_type=None, target_id=None, payload=None, ip=None
        ):
            await db.execute(
                "INSERT INTO admin_audit_log "
                "(actor_id, action, target_type, target_id, payload_json, ip, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    int(actor_id),
                    action,
                    target_type,
                    target_id,
                    json.dumps(payload or {}),
                    ip,
                    int(time.time()),
                ),
            )

        module.log_admin_action = log_admin_action
        sys.modules["webapp.core.audit"] = module

    try:  # pragma: no cover
        importlib.import_module("webapp.core.confirm")
    except ImportError:  # pragma: no cover
        module = types.ModuleType("webapp.core.confirm")

        def require_confirmation(action, param_keys):
            async def dependency() -> bool:
                return True

            return dependency

        module.require_confirmation = require_confirmation
        sys.modules["webapp.core.confirm"] = module

    from webapp.core import auth as _auth

    if not hasattr(_auth, "require_role"):  # pragma: no cover

        def require_role(min_role: str):
            async def dependency():
                return dict(ADMIN)

            return dependency

        _auth.require_role = require_role


_install_phase0_stubs()

from webapp.core.database import get_db  # noqa: E402
from webapp.core.limiter import limiter  # noqa: E402
from webapp.routers import admin_users  # noqa: E402


def _cursor_payload(cursor: str) -> list:
    padded = cursor + "=" * (-len(cursor) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode()).decode())


@pytest.fixture
async def db(tmp_path):
    path = tmp_path / "admin_users.sqlite3"
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys=ON")
    for statement in BASE_TABLES:
        await conn.execute(statement)
    await conn.commit()
    await run_migrations(conn)
    for statement in (WALLET_TX_DDL, AUDIT_DDL):
        await conn.execute(statement)
    await conn.commit()
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def client(db):
    app = FastAPI()
    app.state.limiter = limiter
    previously_enabled = limiter.enabled
    limiter.enabled = False
    app.include_router(admin_users.router, prefix="/api")

    def _admin():
        return dict(ADMIN)

    async def _db():
        return db

    async def _confirmed():
        return True

    app.dependency_overrides[admin_users.require_viewer] = _admin
    app.dependency_overrides[admin_users.require_moderator] = _admin
    app.dependency_overrides[admin_users.require_admin_role] = _admin
    app.dependency_overrides[admin_users.require_balance_confirmation] = _confirmed
    app.dependency_overrides[get_db] = _db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        try:
            yield http
        finally:
            limiter.enabled = previously_enabled


async def _seed_user(db, user_id: int, **fields):
    columns = {
        "user_id": user_id,
        "date": fields.pop("date", 1_700_000_000 + user_id),
        "lang": fields.pop("lang", "uz"),
    }
    columns.update(fields)
    names = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    await db.execute(
        f"INSERT INTO users ({names}) VALUES ({placeholders})", tuple(columns.values())
    )
    await db.commit()


# ---------------------------------------------------------------------------
# list: pagination, filters, search
# ---------------------------------------------------------------------------
async def test_cursor_pagination_is_stable_over_250_users(db, client):
    for i in range(1, 251):
        await _seed_user(db, 1000 + i, date=1_700_000_000 + i)

    seen: list[int] = []
    cursor = None
    pages = 0
    while True:
        params = {"limit": 40}
        if cursor:
            params["cursor"] = cursor
        response = await client.get("/api/admin/users", params=params)
        assert response.status_code == 200, response.text
        body = response.json()
        pages += 1
        if pages == 1:
            assert body["total"] == 250
        seen.extend(item["user_id"] for item in body["items"])
        cursor = body["next_cursor"]
        if not cursor:
            break
        assert pages < 20

    assert len(seen) == 250
    assert len(set(seen)) == 250  # no duplicates and no gaps across pages
    assert seen == sorted(seen, reverse=True)  # date ASC with id => id DESC
    assert set(seen) == {1000 + i for i in range(1, 251)}


async def test_cursor_is_opaque_and_rejects_garbage(db, client):
    for i in range(1, 6):
        await _seed_user(db, 10 + i)
    response = await client.get("/api/admin/users", params={"limit": 2})
    cursor = response.json()["next_cursor"]
    assert _cursor_payload(cursor)[1] == response.json()["items"][-1]["user_id"]

    bad = await client.get("/api/admin/users", params={"cursor": "!!!not-base64!!!"})
    assert bad.status_code == 400
    assert bad.json()["detail"]["code"] == "VALIDATION_ERROR"


async def test_pagination_with_null_sort_values(db, client):
    await _seed_user(db, 501, last_seen_at=None)
    await _seed_user(db, 502, last_seen_at=None)
    await _seed_user(db, 503, last_seen_at=1_700_000_500)

    seen: list[int] = []
    cursor = None
    while True:
        params = {"limit": 1, "sort": "last_seen"}
        if cursor:
            params["cursor"] = cursor
        body = (await client.get("/api/admin/users", params=params)).json()
        seen.extend(item["user_id"] for item in body["items"])
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert seen == [503, 502, 501]  # non-null first, then the NULL tail by id


async def test_filters(db, client):
    await _seed_user(db, 1, user_pro=1, lang="uz", region="1726", date=100)
    await _seed_user(db, 2, user_pro=0, lang="ru", region="1727", date=200)
    await _seed_user(db, 3, user_pro=0, lang="en", region="1726", date=300, blocked=1)
    await _seed_user(db, 4, user_pro=1, lang="uz", region="1726", date=400)
    await db.execute("UPDATE users SET banned = 1 WHERE user_id = 4")
    await db.commit()

    async def ids(**params):
        body = (await client.get("/api/admin/users", params=params)).json()
        return sorted(item["user_id"] for item in body["items"]), body["total"]

    assert await ids(pro="true") == ([1, 4], 2)
    assert await ids(pro="false") == ([2, 3], 2)
    assert await ids(banned="true") == ([4], 1)
    assert await ids(banned="false") == ([1, 2, 3], 3)
    assert await ids(blocked="true") == ([3], 1)
    assert await ids(lang="ru") == ([2], 1)
    assert await ids(region="1726") == ([1, 3, 4], 3)
    assert (await ids(**{"from": 200, "to": 300}))[0] == [2, 3]

    bad = await client.get("/api/admin/users", params={"lang": "de"})
    assert bad.status_code == 400 and bad.json()["detail"]["field"] == "lang"
    bad = await client.get("/api/admin/users", params={"sort": "nope"})
    assert bad.status_code == 400 and bad.json()["detail"]["field"] == "sort"


async def test_search_by_username_and_id(db, client):
    await _seed_user(db, 11, username="alice_hr", first_name="Alice")
    await _seed_user(db, 12, username="bobby", first_name="Bob")
    await _seed_user(db, 13, username="100_percent", first_name="Carol")

    body = (await client.get("/api/admin/users", params={"q": "ali"})).json()
    assert [i["user_id"] for i in body["items"]] == [11]
    assert body["total"] is None  # LIKE search never pays for a count

    body = (await client.get("/api/admin/users", params={"q": "@bobby"})).json()
    assert [i["user_id"] for i in body["items"]] == [12]

    body = (await client.get("/api/admin/users", params={"q": "Carol"})).json()
    assert [i["user_id"] for i in body["items"]] == [13]

    # "%" is escaped, so it matches literally (i.e. nothing) instead of everything.
    body = (await client.get("/api/admin/users", params={"q": "%"})).json()
    assert body["items"] == []

    body = (await client.get("/api/admin/users", params={"q": "12"})).json()
    assert [i["user_id"] for i in body["items"]] == [12]
    assert body["total"] == 1  # numeric q is a PK lookup, count stays cheap


# ---------------------------------------------------------------------------
# detail
# ---------------------------------------------------------------------------
async def test_detail_aggregates_counts(db, client):
    await _seed_user(db, 20, username="inviter", user_balance=5000, user_pro=1)
    await _seed_user(db, 21, username="target", ref_by=20, user_balance=1500)
    await _seed_user(db, 22, ref_by=21)
    await _seed_user(db, 23, ref_by=21)
    await db.executemany(
        "INSERT INTO saves (user_id, save_id) VALUES (?, ?)", [(21, 1), (21, 2), (21, 3)]
    )
    await db.execute(
        "INSERT INTO referral_payouts (user_id, inviter_id, amount, ts) VALUES (?, ?, ?, ?)",
        (22, 21, 2000, 1_700_000_000),
    )
    await db.execute(
        "INSERT INTO resume_exports (user_id, fmt, template_id, status, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (21, "pdf", "clean", "ok", 1_700_000_000),
    )
    await db.execute(
        "INSERT INTO resume_events (user_id, event_name, created_at) VALUES (?, ?, ?)",
        (21, "resume_opened", 1_700_000_001),
    )
    await db.execute(
        "INSERT INTO notification_settings (user_id, enabled, created_at, updated_at) "
        "VALUES (?, 1, ?, ?)",
        (21, 1, 1),
    )
    await db.execute(
        "INSERT INTO wallet_transactions "
        "(user_id, kind, amount, balance_after, created_at) VALUES (?, ?, ?, ?, ?)",
        (21, "admin_credit", 1500, 1500, 1_700_000_002),
    )
    await db.commit()

    body = (await client.get("/api/admin/users/21")).json()
    assert body["user"]["username"] == "target"
    assert body["wallet"] == {"balance": 1500, "is_pro": False, "pro_until": None}
    assert body["counts"] == {
        "saves": 3,
        "referrals": 2,
        "payouts_sum": 2000,
        "resume_exports": 1,
    }
    assert len(body["recent_transactions"]) == 1
    assert len(body["recent_events"]) == 1
    assert body["notification_settings"]["enabled"] is True
    assert body["referrer"]["user_id"] == 20

    missing = await client.get("/api/admin/users/999999")
    assert missing.status_code == 404
    assert missing.json()["detail"]["resource"] == "user"


async def test_user_saves_list(db, client):
    await _seed_user(db, 30)
    await db.executemany(
        "INSERT INTO saves (user_id, save_id) VALUES (?, ?)", [(30, n) for n in range(1, 6)]
    )
    await db.commit()

    body = (await client.get("/api/admin/users/30/saves", params={"limit": 2})).json()
    assert [i["save_id"] for i in body["items"]] == [5, 4]
    assert body["items"][0]["uid"] == "osonish_5"
    assert body["total"] == 5

    body = (
        await client.get(
            "/api/admin/users/30/saves", params={"limit": 2, "cursor": body["next_cursor"]}
        )
    ).json()
    assert [i["save_id"] for i in body["items"]] == [3, 2]
    assert body["total"] is None


# ---------------------------------------------------------------------------
# mutations
# ---------------------------------------------------------------------------
async def _audit_rows(db, action: str) -> list[dict]:
    cursor = await db.execute(
        "SELECT * FROM admin_audit_log WHERE action = ? ORDER BY id", (action,)
    )
    return [dict(row) for row in await cursor.fetchall()]


async def test_pro_grant_sets_pro_until_and_writes_ledger_and_audit(db, client):
    await _seed_user(db, 40, user_balance=100)

    before = int(time.time())
    response = await client.post("/api/admin/users/40/pro", json={"enabled": True, "days": 30})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_pro"] is True
    assert before + 29 * 86400 <= body["pro_until"] <= int(time.time()) + 30 * 86400

    cursor = await db.execute("SELECT user_pro, pro_until, user_balance FROM users WHERE user_id = 40")
    row = await cursor.fetchone()
    assert row["user_pro"] == 1 and row["pro_until"] == body["pro_until"]
    assert row["user_balance"] == 100  # a Pro grant never moves money

    cursor = await db.execute("SELECT kind, amount, actor_id FROM wallet_transactions WHERE user_id = 40")
    tx = await cursor.fetchone()
    assert (tx["kind"], tx["amount"], tx["actor_id"]) == ("adjustment", 0, ADMIN["user_id"])

    audit = await _audit_rows(db, "users.pro")
    assert len(audit) == 1 and audit[0]["target_id"] == "40"

    # Revoke clears the expiry.
    response = await client.post("/api/admin/users/40/pro", json={"enabled": False})
    assert response.status_code == 200
    cursor = await db.execute("SELECT user_pro, pro_until FROM users WHERE user_id = 40")
    row = await cursor.fetchone()
    assert row["user_pro"] == 0 and row["pro_until"] is None
    assert len(await _audit_rows(db, "users.pro")) == 2

    # Unlimited grant: no days -> NULL pro_until.
    body = (await client.post("/api/admin/users/40/pro", json={"enabled": True})).json()
    assert body["pro_until"] is None

    missing = await client.post("/api/admin/users/98765/pro", json={"enabled": True})
    assert missing.status_code == 404


async def test_ban_sets_flag_and_audits(db, client):
    await _seed_user(db, 50)

    response = await client.post("/api/admin/users/50/ban", json={"banned": True, "reason": "spam"})
    assert response.status_code == 200, response.text
    cursor = await db.execute("SELECT banned, banned_reason FROM users WHERE user_id = 50")
    row = await cursor.fetchone()
    assert row["banned"] == 1 and row["banned_reason"] == "spam"

    audit = await _audit_rows(db, "users.ban")
    assert len(audit) == 1 and audit[0]["actor_id"] == ADMIN["user_id"]

    # The banned user is now findable through the filter.
    body = (await client.get("/api/admin/users", params={"banned": "true"})).json()
    assert [i["user_id"] for i in body["items"]] == [50]
    assert body["items"][0]["banned"] is True

    await client.post("/api/admin/users/50/ban", json={"banned": False})
    cursor = await db.execute("SELECT banned, banned_reason FROM users WHERE user_id = 50")
    row = await cursor.fetchone()
    assert row["banned"] == 0 and row["banned_reason"] is None


async def test_balance_change_writes_ledger_and_audit(db, client):
    await _seed_user(db, 60, user_balance=1000)

    response = await client.post(
        "/api/admin/users/60/balance",
        json={"user_id": 60, "amount": 2500, "note": "manual top-up"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["new_balance"] == 3500

    cursor = await db.execute("SELECT user_balance FROM users WHERE user_id = 60")
    assert (await cursor.fetchone())["user_balance"] == 3500

    cursor = await db.execute(
        "SELECT kind, amount, balance_after, actor_id, note FROM wallet_transactions WHERE user_id = 60"
    )
    tx = await cursor.fetchone()
    assert tx["kind"] == "admin_credit"
    assert (tx["amount"], tx["balance_after"]) == (2500, 3500)
    assert tx["actor_id"] == ADMIN["user_id"] and tx["note"] == "manual top-up"

    audit = await _audit_rows(db, "users.balance")
    assert len(audit) == 1
    assert json.loads(audit[0]["payload_json"])["amount"] == 2500

    # A debit larger than the balance changes nothing and writes no ledger row.
    response = await client.post(
        "/api/admin/users/60/balance", json={"user_id": 60, "amount": -99999}
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INSUFFICIENT_BALANCE"
    cursor = await db.execute("SELECT COUNT(*) FROM wallet_transactions WHERE user_id = 60")
    assert (await cursor.fetchone())[0] == 1
    assert len(await _audit_rows(db, "users.balance")) == 1


async def test_validation_errors(db, client):
    await _seed_user(db, 70, user_balance=10)

    zero = await client.post("/api/admin/users/70/balance", json={"user_id": 70, "amount": 0})
    assert zero.status_code == 400 and zero.json()["detail"]["field"] == "amount"

    mismatch = await client.post("/api/admin/users/70/balance", json={"user_id": 71, "amount": 5})
    assert mismatch.status_code == 400 and mismatch.json()["detail"]["field"] == "user_id"

    huge = await client.post(
        "/api/admin/users/70/balance", json={"user_id": 70, "amount": 10**12}
    )
    assert huge.status_code == 422  # bounded by the ledger's MAX_AMOUNT

    bad_id = await client.post("/api/admin/users/0/ban", json={"banned": True})
    assert bad_id.status_code == 422  # ids must be positive ints

    long_note = await client.post(
        "/api/admin/users/70/balance", json={"user_id": 70, "amount": 5, "note": "x" * 501}
    )
    assert long_note.status_code == 422

    bad_days = await client.post(
        "/api/admin/users/70/pro", json={"enabled": True, "days": 100000}
    )
    assert bad_days.status_code == 422

    revoke_with_days = await client.post(
        "/api/admin/users/70/pro", json={"enabled": False, "days": 30}
    )
    assert revoke_with_days.status_code == 400
    assert revoke_with_days.json()["detail"]["field"] == "days"

    empty_text = await client.post("/api/admin/users/70/message", json={"text": ""})
    assert empty_text.status_code == 422


async def test_direct_message_is_audited(db, client, monkeypatch):
    await _seed_user(db, 80)
    sent: list[tuple] = []

    async def fake_send(token: str, chat_id: int, text: str):
        sent.append((token, chat_id, text))
        return {"ok": True, "result": {"message_id": 4242}}

    monkeypatch.setattr(admin_users, "send_telegram_message", fake_send)

    response = await client.post("/api/admin/users/80/message", json={"text": "salom"})
    assert response.status_code == 200, response.text
    assert response.json()["message_id"] == 4242
    assert sent and sent[0][1] == 80 and sent[0][2] == "salom"

    audit = await _audit_rows(db, "users.message")
    assert len(audit) == 1
    payload = json.loads(audit[0]["payload_json"])
    assert payload["ok"] is True and payload["length"] == 5
    # The token must never reach the audit trail.
    assert sent[0][0] not in json.dumps(payload)


async def test_direct_message_failure_marks_blocked(db, client, monkeypatch):
    await _seed_user(db, 81)

    async def fake_send(token: str, chat_id: int, text: str):
        return {"ok": False, "error_code": 403, "description": "bot was blocked by the user"}

    monkeypatch.setattr(admin_users, "send_telegram_message", fake_send)

    response = await client.post("/api/admin/users/81/message", json={"text": "hi"})
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "TELEGRAM_SEND_FAILED"

    cursor = await db.execute("SELECT blocked FROM users WHERE user_id = 81")
    assert (await cursor.fetchone())["blocked"] == 1
    assert len(await _audit_rows(db, "users.message")) == 1


async def test_list_sql_seeks_into_the_indexes(db):
    """The keyset predicate and the flag filters must SEARCH, never SCAN."""
    clause, _ = admin_users._keyset_clause("u.date", 1, 2)
    plans = {
        "cursor": (
            f"SELECT u.user_id FROM users u WHERE {clause} "
            "ORDER BY u.date DESC, u.user_id DESC LIMIT 50",
            (1, 1, 2),
        ),
        "pro": ("SELECT u.user_id FROM users u WHERE u.user_pro = 1 LIMIT 50", ()),
        "banned": ("SELECT u.user_id FROM users u WHERE u.banned = 1 LIMIT 50", ()),
        "blocked": ("SELECT u.user_id FROM users u WHERE u.blocked = 1 LIMIT 50", ()),
    }
    for name, (sql, args) in plans.items():
        cursor = await db.execute("EXPLAIN QUERY PLAN " + sql, args)
        plan = " ".join(str(row[-1]) for row in await cursor.fetchall())
        assert "SEARCH" in plan, f"{name}: {plan}"
        assert "idx_users_" in plan, f"{name}: {plan}"
