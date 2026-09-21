"""Admin authentication, roles, confirmation tokens, settings versioning, audit.

The app is exercised through a real TestClient, but the database dependency is
overridden onto a temp SQLite file: these tests must never touch the DB the
rest of the suite (or a developer's machine) uses. The schema is built here
from the migrations plus the few tables the bot process owns, so the tests do
not depend on ``init_db`` while other agents are editing it.
"""

import asyncio
import json
import time

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from webapp.core import confirm
from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.session import sign_session_payload
from webapp.main import app

OWNER_ID = 900001
ADMIN_ID = 900002
VIEWER_ID = 900003
OUTSIDER_ID = 900004


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

BOT_OWNED_DDL = (
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        date INTEGER,
        lang TEXT,
        region TEXT,
        district TEXT,
        specs TEXT,
        money INTEGER,
        ref_by INTEGER,
        username TEXT,
        first_name TEXT,
        photo_url TEXT,
        user_balance INTEGER,
        user_pro INTEGER,
        pref_filters_json TEXT,
        blocked INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS webapp_sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL
    )
    """,
)


async def _build_schema(path: str) -> None:
    from src.db.migrate import run_migrations

    async with aiosqlite.connect(path) as conn:
        conn.row_factory = aiosqlite.Row
        for ddl in BOT_OWNED_DDL:
            await conn.execute(ddl)
        await conn.commit()
        await run_migrations(conn)
        # Columns webapp/core/database.py adds to the settings singleton and
        # that m005 does not own.
        for column, decl in (
            ("channel_lang", "TEXT NOT NULL DEFAULT 'uz'"),
            ("auto_post_scheduled_day", "TEXT NOT NULL DEFAULT ''"),
            ("last_weekly_stats_week", "TEXT NOT NULL DEFAULT ''"),
        ):
            cursor = await conn.execute("PRAGMA table_info(webapp_admin_settings)")
            if not any(row[1] == column for row in await cursor.fetchall()):
                await conn.execute(
                    f"ALTER TABLE webapp_admin_settings ADD COLUMN {column} {decl}"
                )
        await conn.execute("INSERT OR IGNORE INTO webapp_admin_settings (singleton) VALUES (1)")
        now = int(time.time())
        for user_id in (OWNER_ID, ADMIN_ID, VIEWER_ID, OUTSIDER_ID):
            await conn.execute(
                "INSERT OR IGNORE INTO users (user_id, date, lang, user_balance, user_pro) "
                "VALUES (?, ?, 'uz', 0, 0)",
                (user_id, now),
            )
        await conn.commit()


@pytest.fixture
def db_path(tmp_path) -> str:
    path = str(tmp_path / "admin_auth.sqlite3")
    asyncio.run(_build_schema(path))
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    """TestClient whose get_db is pinned to the temp database."""

    async def _override_get_db():
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
        finally:
            await conn.close()

    settings = get_settings()
    monkeypatch.setattr(settings, "ADMIN_IDS", str(OWNER_ID), raising=False)
    app.dependency_overrides[get_db] = _override_get_db
    # The limiter is in-memory and shared across tests; disable it so a rerun
    # of the same endpoint inside one test does not trip a 429.
    app.state.limiter.enabled = False
    try:
        # No `with`: the lifespan (init_db against the real DB) must not run.
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.state.limiter.enabled = True


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _query(db_path: str, sql: str, params: tuple = ()) -> list[dict]:
    async def run():
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, params)
            return [dict(row) for row in await cursor.fetchall()]

    return asyncio.run(run())


def _execute(db_path: str, sql: str, params: tuple = ()) -> None:
    async def run():
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute(sql, params)
            await conn.commit()

    asyncio.run(run())


def bearer(db_path: str, user_id: int) -> dict[str, str]:
    """Mint a session row directly in the DB and return the auth header."""
    import secrets

    now = int(time.time())
    exp = now + 3600
    sid = secrets.token_urlsafe(24)
    _execute(
        db_path,
        "INSERT INTO webapp_sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (sid, int(user_id), now, exp),
    )
    return {"Authorization": f"Bearer {sign_session_payload({'sid': sid, 'exp': exp})}"}


def seed_admin(db_path: str, user_id: int, role: str, disabled: int = 0) -> None:
    _execute(
        db_path,
        "INSERT OR REPLACE INTO admins (user_id, role, added_by, added_at, disabled) VALUES (?, ?, ?, ?, ?)",
        (int(user_id), role, OWNER_ID, int(time.time()), disabled),
    )


# --------------------------------------------------------------------------
# Bootstrap and access control
# --------------------------------------------------------------------------


def test_admin_ids_bootstraps_an_owner_row(client, db_path):
    assert _query(db_path, "SELECT * FROM admins") == []

    response = client.get("/api/admin/state", headers=bearer(db_path, OWNER_ID))
    assert response.status_code == 200
    body = response.json()
    assert body["is_admin"] is True
    assert body["role"] == "owner"

    rows = _query(db_path, "SELECT user_id, role, disabled FROM admins")
    assert rows == [{"user_id": OWNER_ID, "role": "owner", "disabled": 0}]


def test_env_admin_is_ignored_once_an_owner_exists(client, db_path):
    """ADMIN_IDS is bootstrap only: a second env id is not auto-promoted."""
    seed_admin(db_path, OWNER_ID, "owner")
    get_settings().ADMIN_IDS = f"{OWNER_ID},{OUTSIDER_ID}"

    response = client.get("/api/admin/state", headers=bearer(db_path, OUTSIDER_ID))
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ADMIN_REQUIRED"
    assert _query(db_path, "SELECT 1 FROM admins WHERE user_id = ?", (OUTSIDER_ID,)) == []


def test_non_admin_gets_403(client, db_path):
    seed_admin(db_path, OWNER_ID, "owner")
    response = client.get("/api/admin/state", headers=bearer(db_path, OUTSIDER_ID))
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ADMIN_REQUIRED"


def test_disabled_admin_is_refused(client, db_path):
    seed_admin(db_path, OWNER_ID, "owner")
    seed_admin(db_path, ADMIN_ID, "admin", disabled=1)
    response = client.get("/api/admin/state", headers=bearer(db_path, ADMIN_ID))
    assert response.status_code == 403


def test_init_data_alone_is_rejected_on_admin_routes(client, db_path):
    """Admin routes are Bearer-only; initData is replayable for its window."""
    seed_admin(db_path, OWNER_ID, "owner")
    response = client.get(
        "/api/admin/state",
        headers={"X-Telegram-Init-Data": "user=%7B%22id%22%3A900001%7D&auth_date=1&hash=deadbeef"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_REQUIRED"


def test_anonymous_gets_401(client):
    response = client.get("/api/admin/state")
    assert response.status_code == 401


# --------------------------------------------------------------------------
# Roles
# --------------------------------------------------------------------------


def test_viewer_can_read_but_cannot_patch(client, db_path):
    seed_admin(db_path, OWNER_ID, "owner")
    seed_admin(db_path, VIEWER_ID, "viewer")
    headers = bearer(db_path, VIEWER_ID)

    assert client.get("/api/admin/state", headers=headers).json()["role"] == "viewer"

    response = client.patch("/api/admin/state", headers=headers, json={"pro_price": 55000})
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "ADMIN_REQUIRED"
    assert detail["required_role"] == "admin"
    # Nothing was written.
    assert _query(db_path, "SELECT pro_price FROM webapp_admin_settings")[0]["pro_price"] == 10000


def test_admin_role_can_patch_but_cannot_manage_admins(client, db_path):
    seed_admin(db_path, OWNER_ID, "owner")
    seed_admin(db_path, ADMIN_ID, "admin")
    headers = bearer(db_path, ADMIN_ID)

    assert client.patch("/api/admin/state", headers=headers, json={"pro_price": 12000}).status_code == 200

    response = client.post("/api/admin/admins", headers=headers, json={"user_id": 5, "role": "viewer"})
    assert response.status_code == 403
    assert response.json()["detail"]["required_role"] == "owner"


# --------------------------------------------------------------------------
# Admin management
# --------------------------------------------------------------------------


def test_owner_can_add_and_remove_an_admin(client, db_path):
    seed_admin(db_path, OWNER_ID, "owner")
    headers = bearer(db_path, OWNER_ID)

    created = client.post(
        "/api/admin/admins", headers=headers, json={"user_id": ADMIN_ID, "role": "moderator"}
    )
    assert created.status_code == 201
    assert created.json()["role"] == "moderator"

    duplicate = client.post(
        "/api/admin/admins", headers=headers, json={"user_id": ADMIN_ID, "role": "admin"}
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "ADMIN_EXISTS"

    promoted = client.patch(
        f"/api/admin/admins/{ADMIN_ID}", headers=headers, json={"role": "admin"}
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"

    listed = client.get("/api/admin/admins", headers=headers).json()["items"]
    assert {row["user_id"] for row in listed} == {OWNER_ID, ADMIN_ID}

    assert client.delete(f"/api/admin/admins/{ADMIN_ID}", headers=headers).status_code == 200
    assert _query(db_path, "SELECT 1 FROM admins WHERE user_id = ?", (ADMIN_ID,)) == []

    actions = [row["action"] for row in _query(db_path, "SELECT action FROM admin_audit_log ORDER BY id")]
    assert actions == ["admins.add", "admins.role", "admins.remove"]


def test_last_enabled_owner_cannot_be_removed_disabled_or_demoted(client, db_path):
    seed_admin(db_path, OWNER_ID, "owner")
    seed_admin(db_path, ADMIN_ID, "admin")
    headers = bearer(db_path, OWNER_ID)

    for call in (
        lambda: client.delete(f"/api/admin/admins/{OWNER_ID}", headers=headers),
        lambda: client.patch(f"/api/admin/admins/{OWNER_ID}", headers=headers, json={"disabled": True}),
        lambda: client.patch(f"/api/admin/admins/{OWNER_ID}", headers=headers, json={"role": "viewer"}),
    ):
        response = call()
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "CANNOT_REMOVE_LAST_OWNER"

    still_owner = _query(db_path, "SELECT role, disabled FROM admins WHERE user_id = ?", (OWNER_ID,))
    assert still_owner == [{"role": "owner", "disabled": 0}]

    # With a second owner in place the first one may step down.
    seed_admin(db_path, ADMIN_ID, "owner")
    assert client.delete(f"/api/admin/admins/{OWNER_ID}", headers=headers).status_code == 200


# --------------------------------------------------------------------------
# Confirmation tokens
# --------------------------------------------------------------------------


def test_confirm_token_round_trip():
    params = {"user_id": 7, "amount": 1000}
    token = confirm.issue_confirm_token(OWNER_ID, "wallet.add_balance", params)
    assert confirm.verify_confirm_token(token, OWNER_ID, "wallet.add_balance", params) is True
    # Key order must not matter.
    assert confirm.verify_confirm_token(
        token, OWNER_ID, "wallet.add_balance", {"amount": 1000, "user_id": 7}
    ) is True


def test_confirm_token_is_bound_to_actor_action_and_params():
    token = confirm.issue_confirm_token(OWNER_ID, "wallet.add_balance", {"user_id": 7, "amount": 1000})
    assert confirm.verify_confirm_token(token, ADMIN_ID, "wallet.add_balance", {"user_id": 7, "amount": 1000}) is False
    assert confirm.verify_confirm_token(token, OWNER_ID, "wallet.reset_user", {"user_id": 7, "amount": 1000}) is False
    assert confirm.verify_confirm_token(token, OWNER_ID, "wallet.add_balance", {"user_id": 7, "amount": 1000000}) is False
    assert confirm.verify_confirm_token("garbage", OWNER_ID, "wallet.add_balance", {}) is False
    assert confirm.verify_confirm_token("", OWNER_ID, "wallet.add_balance", {}) is False


def test_confirm_token_expires():
    """A token whose exp has passed is refused even though its MAC is valid."""
    params = {"user_id": 7}
    past = int(time.time()) - 1
    expired = f"{past}.{confirm._sign(OWNER_ID, 'wallet.add_balance', params, past)}"
    assert confirm.verify_confirm_token(expired, OWNER_ID, "wallet.add_balance", params) is False


def test_confirm_token_expiry_cannot_be_extended_by_the_client():
    token = confirm.issue_confirm_token(OWNER_ID, "wallet.add_balance", {"user_id": 7})
    _, _, signature = token.partition(".")
    forged = f"{int(time.time()) + 86400}.{signature}"
    assert confirm.verify_confirm_token(forged, OWNER_ID, "wallet.add_balance", {"user_id": 7}) is False


def test_confirm_endpoint_issues_a_usable_token(client, db_path):
    seed_admin(db_path, OWNER_ID, "owner")
    response = client.post(
        "/api/admin/confirm",
        headers=bearer(db_path, OWNER_ID),
        json={"action": "wallet.add_balance", "params": {"user_id": 7, "amount": 1000}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["expires_in"] == confirm.confirm_ttl()
    assert confirm.verify_confirm_token(
        body["token"], OWNER_ID, "wallet.add_balance", {"user_id": 7, "amount": 1000}
    ) is True


def test_confirm_endpoint_requires_admin(client, db_path):
    seed_admin(db_path, OWNER_ID, "owner")
    response = client.post(
        "/api/admin/confirm",
        headers=bearer(db_path, OUTSIDER_ID),
        json={"action": "wallet.add_balance", "params": {}},
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------
# Settings versioning and audit
# --------------------------------------------------------------------------


def test_patch_bumps_version_and_writes_one_audit_row(client, db_path):
    seed_admin(db_path, OWNER_ID, "owner")
    headers = bearer(db_path, OWNER_ID)

    before = client.get("/api/admin/state", headers=headers).json()
    assert before["version"] == 0

    response = client.patch(
        "/api/admin/state",
        headers=headers,
        json={"pro_price": 15000, "channel_lang": "ru", "expected_version": 0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["pro_price"] == 15000
    assert body["channel_lang"] == "ru"

    rows = _query(db_path, "SELECT actor_id, action, target_type, payload_json FROM admin_audit_log")
    assert len(rows) == 1
    assert rows[0]["actor_id"] == OWNER_ID
    assert rows[0]["action"] == "settings.patch"
    assert rows[0]["target_type"] == "settings"
    payload = json.loads(rows[0]["payload_json"])
    assert payload["version"] == 1
    assert payload["diff"]["pro_price"] == [10000, 15000]
    assert payload["diff"]["channel_lang"] == ["uz", "ru"]


def test_stale_expected_version_conflicts(client, db_path):
    seed_admin(db_path, OWNER_ID, "owner")
    headers = bearer(db_path, OWNER_ID)

    assert client.patch(
        "/api/admin/state", headers=headers, json={"pro_price": 11000, "expected_version": 0}
    ).status_code == 200

    stale = client.patch(
        "/api/admin/state", headers=headers, json={"pro_price": 99000, "expected_version": 0}
    )
    assert stale.status_code == 409
    detail = stale.json()["detail"]
    assert detail["code"] == "SETTINGS_CONFLICT"
    assert detail["version"] == 1
    assert _query(db_path, "SELECT pro_price FROM webapp_admin_settings")[0]["pro_price"] == 11000
    # The losing PATCH left no audit row behind.
    assert len(_query(db_path, "SELECT 1 FROM admin_audit_log")) == 1


def test_failed_patch_validation_leaves_no_audit_row(client, db_path):
    seed_admin(db_path, OWNER_ID, "owner")
    headers = bearer(db_path, OWNER_ID)

    response = client.patch(
        "/api/admin/state",
        headers=headers,
        json={"auto_post_per_day_min": 9, "auto_post_per_day_max": 3},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"
    assert _query(db_path, "SELECT 1 FROM admin_audit_log") == []


def test_audit_payload_never_stores_secrets(db_path):
    from webapp.core.audit import log_admin_action, scrub

    assert scrub({"confirm_token": "abc", "amount": 5}) == {"confirm_token": "[redacted]", "amount": 5}
    assert scrub({"nested": {"secret": "s"}}) == {"nested": {"secret": "[redacted]"}}

    async def run():
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await log_admin_action(
                conn,
                actor_id=OWNER_ID,
                action="wallet.add_balance",
                target_type="user",
                target_id="7",
                payload={"amount": 1000, "session_token": "leak-me"},
                ip="10.0.0.1",
            )
            await conn.commit()

    asyncio.run(run())
    row = _query(db_path, "SELECT payload_json, ip FROM admin_audit_log")[0]
    assert "leak-me" not in row["payload_json"]
    assert json.loads(row["payload_json"])["session_token"] == "[redacted]"
    assert row["ip"] == "10.0.0.1"
