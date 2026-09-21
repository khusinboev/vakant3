"""Regression tests for the security review fixes (SECFIX).

Each block names the finding it pins down. They are deliberately close to the
mechanism rather than to a whole request flow: the point of most of these fixes
is that a *forged* input stops being trusted, and that is easiest to state
directly against the function that used to trust it.
"""
from __future__ import annotations

import base64
import json
import time
import urllib.parse

import aiosqlite
import httpx
import pytest
from fastapi import FastAPI
from starlette.requests import Request

from src.db.migrate import MIGRATION_BUSY_TIMEOUT_MS, run_migrations
from webapp.core import errors
from webapp.core.config import get_settings
from webapp.core.database import get_db

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def make_request(headers: dict[str, str] | None = None, client_host: str = "203.0.113.9") -> Request:
    """A bare Starlette request — enough for the key/IP functions under test."""
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
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
            "client": (client_host, 40000),
            "headers": raw,
        }
    )


def signed_init_data(user_id: int, *, token: str | None = None) -> str:
    """Genuine Telegram initData for ``user_id``, signed with the bot token."""
    import hashlib
    import hmac

    bot_token = token or get_settings().TOKEN
    fields = {
        "auth_date": str(int(time.time())),
        "query_id": "AAA",
        "user": json.dumps({"id": user_id, "first_name": "T"}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(fields)


def walk_dependant(dependant):
    yield dependant
    for sub in dependant.dependencies:
        yield from walk_dependant(sub)


def override_admin_deps(app: FastAPI, router, actor: dict, *, confirm: bool = True) -> None:
    """Override ``require_role`` (and optionally ``require_confirmation``) nodes.

    With ``confirm=False`` the confirmation dependency is left in place and its
    inner ``require_admin`` is overridden instead, so the token check really
    runs while the test still does not need a session row.
    """
    from webapp.core.auth import require_admin

    async def _actor():
        return actor

    app.dependency_overrides[require_admin] = _actor
    seen = set()
    for route in router.routes:
        for dep in walk_dependant(route.dependant):
            call = dep.call
            if call is None or call in seen:
                continue
            is_role = getattr(call, "__require_role__", None) is not None
            is_confirm = getattr(call, "__confirm_action__", None) is not None
            if is_role or (is_confirm and confirm):
                seen.add(call)
                app.dependency_overrides[call] = _actor


#: The ``users`` table as the running system actually has it: the bot's base
#: DDL (src/middleware/middlewares.py) plus the columns the bot and the API add
#: by ALTER. Migrations only create a *minimal* users table when it is absent,
#: so a test that needs ``ref_by``/``user_pro`` must create this one first —
#: exactly the order a real deployment has.
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


async def migrated_conn(
    tmp_path, name: str = "secfix.sqlite3", *, with_users: bool = True
) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(str(tmp_path / name))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA busy_timeout=5000")
    if with_users:
        await conn.execute(USERS_DDL)
        await conn.commit()
    await run_migrations(conn)
    return conn


def client_for(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


# ===========================================================================
# 1. Rate-limit buckets key on a VERIFIED identity only
# ===========================================================================

async def test_junk_bearer_token_falls_back_to_the_ip_bucket():
    """A token nobody signed must not buy its own bucket."""
    from webapp.core.limiter import rate_limit_key

    first = rate_limit_key(make_request({"authorization": "Bearer junk-aaaaaaaaaaaaaaaaaaaa"}))
    second = rate_limit_key(make_request({"authorization": "Bearer junk-bbbbbbbbbbbbbbbbbbbb"}))

    assert first == second == "ip:203.0.113.9"


async def test_junk_init_data_falls_back_to_the_ip_bucket():
    from webapp.core.limiter import rate_limit_key

    forged = urllib.parse.urlencode(
        {"user": json.dumps({"id": 999}), "auth_date": str(int(time.time())), "hash": "00" * 32}
    )
    assert rate_limit_key(make_request({"x-telegram-init-data": forged})) == "ip:203.0.113.9"


async def test_a_validly_signed_session_gets_its_own_bucket():
    from webapp.core.limiter import rate_limit_key
    from webapp.core.session import sign_session_payload

    token = sign_session_payload({"sid": "session-abc", "exp": int(time.time()) + 3600})
    assert rate_limit_key(make_request({"authorization": f"Bearer {token}"})) == "sess:session-abc"


async def test_an_expired_session_token_does_not_get_its_own_bucket():
    from webapp.core.limiter import rate_limit_key
    from webapp.core.session import sign_session_payload

    token = sign_session_payload({"sid": "session-old", "exp": int(time.time()) - 5})
    assert rate_limit_key(make_request({"authorization": f"Bearer {token}"})) == "ip:203.0.113.9"


async def test_genuine_init_data_gets_its_own_bucket():
    from webapp.core.limiter import rate_limit_key

    key = rate_limit_key(make_request({"x-telegram-init-data": signed_init_data(4242)}))
    assert key == "tg:4242"


async def test_resolved_user_id_on_request_state_wins():
    from webapp.core.limiter import rate_limit_key

    request = make_request({"authorization": "Bearer junk"})
    request.state.user_id = 7
    assert rate_limit_key(request) == "u:7"


async def test_auth_publishes_the_verified_user_id_for_the_limiter(tmp_path):
    """``webapp.core.auth`` is what sets ``request.state.user_id``."""
    from webapp.core.auth import _resolve
    from webapp.core.session import sign_session_payload

    conn = await aiosqlite.connect(str(tmp_path / "auth.sqlite3"))
    conn.row_factory = aiosqlite.Row
    try:
        await conn.execute(USERS_DDL)
        await conn.execute("INSERT INTO users (user_id, lang) VALUES (55, 'uz')")
        await conn.execute(
            "CREATE TABLE webapp_sessions (token TEXT PRIMARY KEY, user_id INTEGER, "
            "created_at INTEGER, expires_at INTEGER)"
        )
        exp = int(time.time()) + 3600
        await conn.execute(
            "INSERT INTO webapp_sessions (token, user_id, created_at, expires_at) "
            "VALUES ('sid-55', 55, ?, ?)",
            (int(time.time()), exp),
        )
        await conn.commit()

        token = sign_session_payload({"sid": "sid-55", "exp": exp})
        request = make_request({"authorization": f"Bearer {token}"})
        user, code = await _resolve(request, conn)
        assert code is None and user["user_id"] == 55
        assert request.state.user_id == 55
    finally:
        await conn.close()


# ===========================================================================
# 3. Client IP comes from X-Real-IP / the LAST forwarded hop
# ===========================================================================

async def test_client_ip_prefers_x_real_ip():
    from webapp.core.request_ip import client_ip

    request = make_request({"x-real-ip": "198.51.100.7", "x-forwarded-for": "1.1.1.1, 2.2.2.2"})
    assert client_ip(request) == "198.51.100.7"


async def test_client_ip_ignores_the_client_supplied_first_hop():
    from webapp.core.request_ip import client_ip

    # "9.9.9.9" is what the caller wrote; "198.51.100.7" is what nginx appended.
    request = make_request({"x-forwarded-for": "9.9.9.9, 198.51.100.7"})
    assert client_ip(request) == "198.51.100.7"


async def test_client_ip_falls_back_to_the_socket_peer():
    from webapp.core.request_ip import client_ip

    assert client_ip(make_request({}, client_host="192.0.2.5")) == "192.0.2.5"


async def test_client_ip_rejects_a_header_with_control_characters():
    from webapp.core.request_ip import MAX_IP_CHARS, client_ip

    assert client_ip(make_request({"x-real-ip": "a" * 200})) == "a" * MAX_IP_CHARS


async def test_audit_client_ip_uses_the_same_rule():
    from webapp.core.audit import client_ip as audit_client_ip

    assert audit_client_ip(make_request({"x-forwarded-for": "9.9.9.9, 198.51.100.7"})) == "198.51.100.7"


# ===========================================================================
# 2. Stored XSS: <a href> schemes
# ===========================================================================

@pytest.mark.parametrize(
    "href",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "  javascript:alert(1)",
        "java\tscript:alert(1)",
        "&#106;avascript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "vbscript:msgbox(1)",
        "/relative/path",
        "//evil.example",
        "",
    ],
)
async def test_unsafe_hrefs_are_rejected(href):
    from webapp.routers.admin_content import _html_is_valid

    assert _html_is_valid(f'<a href="{href}">click</a>') is False


@pytest.mark.parametrize(
    "href",
    ["https://lex.uz/docs/1", "http://example.uz", "tg://resolve?domain=bandlikuz", "mailto:a@b.uz"],
)
async def test_safe_hrefs_are_accepted(href):
    from webapp.routers.admin_content import _html_is_valid

    assert _html_is_valid(f'<a href="{href}">click</a>') is True


async def test_plain_markup_still_passes():
    from webapp.routers.admin_content import _html_is_valid

    assert _html_is_valid("<b>bold</b> and <i>italic</i><br>next") is True


# ===========================================================================
# 4. /broadcasts/{id}/queue requires a confirmation token
# ===========================================================================

async def _broadcast_fixture(tmp_path):
    conn = await migrated_conn(tmp_path, "broadcasts.sqlite3")
    await conn.executemany(
        "INSERT INTO users (user_id, lang, user_pro, blocked, date) VALUES (?, 'uz', 0, 0, ?)",
        [(1, int(time.time())), (2, int(time.time()))],
    )
    await conn.execute(
        "INSERT INTO broadcasts (id, actor_id, status, kind, text, target_json, created_at) "
        "VALUES (1, 99, 'draft', 'text', 'hi', ?, ?)",
        (json.dumps({"segment": "all", "exclude_blocked": True}), int(time.time())),
    )
    await conn.commit()
    return conn


async def test_queue_without_a_confirm_token_is_refused(tmp_path):
    from webapp.routers import admin_broadcasts

    conn = await _broadcast_fixture(tmp_path)
    app = FastAPI()
    app.include_router(admin_broadcasts.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: conn
    override_admin_deps(app, admin_broadcasts.router, {"user_id": 99, "role": "admin"}, confirm=False)
    try:
        async with client_for(app) as client:
            response = await client.post("/api/admin/broadcasts/1/queue", json={"broadcast_id": 1})
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == errors.CONFIRMATION_REQUIRED
        row = await (await conn.execute("SELECT status FROM broadcasts WHERE id = 1")).fetchone()
        assert row["status"] == "draft", "nothing may be queued without confirmation"
    finally:
        await conn.close()


async def test_a_token_minted_for_another_broadcast_is_refused(tmp_path):
    from webapp.core.confirm import issue_confirm_token
    from webapp.routers import admin_broadcasts

    conn = await _broadcast_fixture(tmp_path)
    app = FastAPI()
    app.include_router(admin_broadcasts.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: conn
    override_admin_deps(app, admin_broadcasts.router, {"user_id": 99, "role": "admin"}, confirm=False)
    token = issue_confirm_token(99, "broadcast.queue", {"broadcast_id": 2})
    try:
        async with client_for(app) as client:
            response = await client.post(
                "/api/admin/broadcasts/1/queue",
                json={"broadcast_id": 1},
                headers={"X-Confirm-Token": token},
            )
        assert response.status_code == 403
    finally:
        await conn.close()


async def test_queue_with_a_matching_token_still_works(tmp_path):
    from webapp.core.confirm import issue_confirm_token
    from webapp.routers import admin_broadcasts

    conn = await _broadcast_fixture(tmp_path)
    app = FastAPI()
    app.include_router(admin_broadcasts.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: conn
    override_admin_deps(app, admin_broadcasts.router, {"user_id": 99, "role": "admin"}, confirm=False)
    token = issue_confirm_token(99, "broadcast.queue", {"broadcast_id": 1})
    try:
        async with client_for(app) as client:
            response = await client.post(
                "/api/admin/broadcasts/1/queue",
                json={"broadcast_id": 1},
                headers={"X-Confirm-Token": token},
            )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "queued"
    finally:
        await conn.close()


async def test_a_body_id_that_contradicts_the_path_is_rejected(tmp_path):
    from webapp.core.confirm import issue_confirm_token
    from webapp.routers import admin_broadcasts

    conn = await _broadcast_fixture(tmp_path)
    app = FastAPI()
    app.include_router(admin_broadcasts.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: conn
    override_admin_deps(app, admin_broadcasts.router, {"user_id": 99, "role": "admin"}, confirm=False)
    # A valid token for broadcast 2, replayed against path 1: the token check
    # passes (the body says 2) so the path/body mismatch must catch it.
    token = issue_confirm_token(99, "broadcast.queue", {"broadcast_id": 2})
    try:
        async with client_for(app) as client:
            response = await client.post(
                "/api/admin/broadcasts/1/queue",
                json={"broadcast_id": 2},
                headers={"X-Confirm-Token": token},
            )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == errors.VALIDATION_ERROR
    finally:
        await conn.close()


# ===========================================================================
# 5. Uploads are refused on Content-Length, before the body is parsed
# ===========================================================================

def _upload_app(conn):
    from webapp.routers import admin_broadcasts

    app = FastAPI()
    app.include_router(admin_broadcasts.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: conn
    override_admin_deps(app, admin_broadcasts.router, {"user_id": 99, "role": "admin"})
    return app


async def test_oversize_content_length_is_refused_with_413(tmp_path):
    from webapp.core.uploads import UPLOAD_TOO_LARGE
    from webapp.routers.admin_broadcasts import MAX_REQUEST_BYTES

    conn = await _broadcast_fixture(tmp_path)
    app = _upload_app(conn)
    try:
        async with client_for(app) as client:
            request = client.build_request(
                "POST",
                "/api/admin/uploads",
                content=b"x" * 16,
                headers={"content-type": "multipart/form-data; boundary=zz"},
            )
            # The declared size is the lie an oversize upload starts with; the
            # body is never actually sent that large in this test.
            request.headers["content-length"] = str(MAX_REQUEST_BYTES + 1)
            response = await client.send(request)
        assert response.status_code == 413
        assert response.json()["detail"]["code"] == UPLOAD_TOO_LARGE
    finally:
        await conn.close()


async def test_a_normal_upload_still_succeeds(tmp_path, monkeypatch):
    from webapp.core import uploads

    monkeypatch.setattr(uploads, "DB_PATH", tmp_path / "database.sqlite3")
    conn = await _broadcast_fixture(tmp_path)
    app = _upload_app(conn)
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 64
    try:
        async with client_for(app) as client:
            response = await client.post(
                "/api/admin/uploads", files={"file": ("photo.jpg", jpeg, "image/jpeg")}
            )
        assert response.status_code == 200, response.text
        assert response.json()["mime"] == "image/jpeg"
    finally:
        await conn.close()


async def test_a_request_without_the_file_part_is_a_400(tmp_path):
    conn = await _broadcast_fixture(tmp_path)
    app = _upload_app(conn)
    try:
        async with client_for(app) as client:
            response = await client.post("/api/admin/uploads", data={"other": "value"})
        assert response.status_code == 400
    finally:
        await conn.close()


# ===========================================================================
# 6. Migrations: lock timeout + a chunked back-fill
# ===========================================================================

async def test_run_migrations_raises_and_restores_the_busy_timeout(tmp_path):
    conn = await aiosqlite.connect(str(tmp_path / "timeout.sqlite3"))
    conn.row_factory = aiosqlite.Row
    try:
        await conn.execute("PRAGMA busy_timeout=5000")
        seen: list[int] = []

        from src.db import migrate as migrate_module

        original = migrate_module._run_migrations

        async def _spy(c):
            cursor = await c.execute("PRAGMA busy_timeout")
            seen.append(int((await cursor.fetchone())[0]))
            return await original(c)

        migrate_module._run_migrations = _spy
        try:
            await run_migrations(conn)
        finally:
            migrate_module._run_migrations = original

        assert seen == [MIGRATION_BUSY_TIMEOUT_MS]
        cursor = await conn.execute("PRAGMA busy_timeout")
        assert int((await cursor.fetchone())[0]) == 5000, "the caller's timeout must come back"
    finally:
        await conn.close()


async def test_m006_backfill_is_chunked_and_idempotent(tmp_path, monkeypatch):
    from src.db.migrations import m006_entry_gate

    monkeypatch.setattr(m006_entry_gate, "BACKFILL_CHUNK", 3)
    conn = await aiosqlite.connect(str(tmp_path / "m006.sqlite3"))
    conn.row_factory = aiosqlite.Row
    try:
        await conn.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, date INTEGER, lang TEXT, "
            "region TEXT, district TEXT, specs TEXT, money INTEGER)"
        )
        await conn.executemany(
            "INSERT INTO users (user_id, date) VALUES (?, ?)",
            [(i, 1_700_000_000 + i) for i in range(1, 11)],
        )
        # A row the bot never stamped: it must not make the chunk loop spin.
        await conn.execute("INSERT INTO users (user_id, date) VALUES (99, NULL)")
        await conn.commit()

        await m006_entry_gate.apply(conn)
        await conn.commit()

        cursor = await conn.execute(
            "SELECT COUNT(*) FROM users WHERE started_at IS NOT NULL AND started_at = date"
        )
        assert int((await cursor.fetchone())[0]) == 10
        cursor = await conn.execute("SELECT started_at FROM users WHERE user_id = 99")
        assert (await cursor.fetchone())["started_at"] is None

        # Re-running must be a no-op, not a second pass over the table.
        await conn.execute("UPDATE users SET started_at = 1 WHERE user_id = 1")
        await m006_entry_gate.apply(conn)
        cursor = await conn.execute("SELECT started_at FROM users WHERE user_id = 1")
        assert int((await cursor.fetchone())["started_at"]) == 1
    finally:
        await conn.close()


async def test_m014_indexes_ref_by(tmp_path):
    conn = await migrated_conn(tmp_path, "m014.sqlite3")
    try:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_users_ref_by'"
        )
        assert await cursor.fetchone() is not None
    finally:
        await conn.close()


# ===========================================================================
# 7. Unbounded scans are capped
# ===========================================================================

async def test_finance_transactions_total_is_null_past_the_cap(tmp_path, monkeypatch):
    from webapp.routers import admin_finance

    monkeypatch.setattr(admin_finance, "COUNT_CAP", 2)
    conn = await migrated_conn(tmp_path, "finance.sqlite3")
    app = FastAPI()
    app.include_router(admin_finance.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: conn
    override_admin_deps(app, admin_finance.router, {"user_id": 99, "role": "admin"})
    try:
        now = int(time.time())
        await conn.executemany(
            "INSERT INTO wallet_transactions (user_id, kind, amount, balance_after, created_at) "
            "VALUES (?, 'admin_credit', 100, 100, ?)",
            [(i, now) for i in range(5)],
        )
        await conn.commit()
        async with client_for(app) as client:
            response = await client.get("/api/admin/finance/transactions")
        assert response.status_code == 200, response.text
        assert response.json()["total"] is None

        monkeypatch.setattr(admin_finance, "COUNT_CAP", 100)
        async with client_for(app) as client:
            response = await client.get("/api/admin/finance/transactions")
        assert response.json()["total"] == 5
    finally:
        await conn.close()


async def test_finance_referrals_aggregate_is_cached(tmp_path):
    from webapp.routers import admin_finance

    admin_finance._referrals_cache.clear()
    conn = await migrated_conn(tmp_path, "referrals.sqlite3")
    app = FastAPI()
    app.include_router(admin_finance.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: conn
    override_admin_deps(app, admin_finance.router, {"user_id": 99, "role": "admin"})
    try:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS referral_payouts (user_id INTEGER, amount INTEGER, ts INTEGER)"
        )
        await conn.executemany(
            "INSERT INTO users (user_id, first_name, ref_by) VALUES (?, ?, ?)",
            [(1, "Inviter", None), (2, "A", 1), (3, "B", 1)],
        )
        await conn.commit()

        async with client_for(app) as client:
            first = await client.get("/api/admin/finance/referrals")
            assert first.json()["items"][0]["invited_count"] == 2
            # A new invitee lands, but the cached window has not expired.
            await conn.execute("INSERT INTO users (user_id, ref_by) VALUES (4, 1)")
            await conn.commit()
            second = await client.get("/api/admin/finance/referrals")
        assert second.json()["items"][0]["invited_count"] == 2

        admin_finance._referrals_cache.clear()
        async with client_for(app) as client:
            third = await client.get("/api/admin/finance/referrals")
        assert third.json()["items"][0]["invited_count"] == 3
    finally:
        admin_finance._referrals_cache.clear()
        await conn.close()


async def test_system_counts_estimate_big_tables_without_counting_them(tmp_path):
    from webapp.routers import admin_system

    admin_system._big_count_cache.clear()
    conn = await migrated_conn(tmp_path, "system.sqlite3")
    try:
        await conn.executemany("INSERT INTO users (user_id) VALUES (?)", [(i,) for i in range(1, 6)])
        await conn.commit()

        assert await admin_system._estimated_count(conn, "users") == 5
        # Cached: a second call inside the TTL does not look at the table again.
        await conn.execute("INSERT INTO users (user_id) VALUES (900)")
        await conn.commit()
        assert await admin_system._estimated_count(conn, "users") == 5

        admin_system._big_count_cache.clear()
        assert await admin_system._estimated_count(conn, "users") == 900
        assert await admin_system._estimated_count(conn, "no_such_table") == 0
    finally:
        admin_system._big_count_cache.clear()
        await conn.close()


# ===========================================================================
# 8. Cursors are type-checked
# ===========================================================================

def _cursor(payload) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


@pytest.mark.parametrize(
    "payload",
    [[{"$ne": 1}, 5], [[1, 2], 5], [1, True], [True, 5], [{"a": 1}, {"b": 2}]],
)
async def test_non_scalar_cursor_values_are_rejected(payload):
    from webapp.routers.admin_users import _decode_cursor

    with pytest.raises(Exception) as excinfo:
        _decode_cursor(_cursor(payload), 2)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail["code"] == errors.VALIDATION_ERROR


@pytest.mark.parametrize("payload", [[1700000000, 5], [None, None], ["abc", 5], [1.5, 5]])
async def test_scalar_cursor_values_still_decode(payload):
    from webapp.routers.admin_users import _decode_cursor

    assert _decode_cursor(_cursor(payload), 2) == payload


# ===========================================================================
# 9. The referral router sits behind the entry gate and is paginated
# ===========================================================================

async def test_referral_router_is_behind_require_entry():
    from webapp.core.entry_gate import require_entry
    from webapp.routers import referral

    calls = {dep.call for route in referral.router.routes for dep in walk_dependant(route.dependant)}
    assert require_entry in calls


async def test_referral_list_is_capped_and_counts_the_total(tmp_path):
    from webapp.core.auth import current_user
    from webapp.core.entry_gate import require_entry
    from webapp.routers import referral

    conn = await aiosqlite.connect(str(tmp_path / "ref.sqlite3"))
    conn.row_factory = aiosqlite.Row
    app = FastAPI()
    app.include_router(referral.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: conn
    app.dependency_overrides[require_entry] = lambda: {"user_id": 1}
    app.dependency_overrides[current_user] = lambda: {"user_id": 1, "lang": "uz"}
    try:
        await conn.execute(USERS_DDL)
        await conn.executemany(
            "INSERT INTO users (user_id, first_name, date, ref_by) VALUES (?, ?, ?, 1)",
            [(i, f"U{i}", 1_700_000_000 + i) for i in range(2, 80)],
        )
        await conn.commit()

        async with client_for(app) as client:
            response = await client.get("/api/referral")
            body = response.json()
            assert len(body["referrals"]) == referral.MAX_REFERRALS
            assert body["ref_count"] == 78, "the counter stays the true total"

            over = await client.get("/api/referral", params={"limit": 500})
            assert over.status_code == 422, "the page size is not client-chosen beyond the cap"
    finally:
        await conn.close()


# ===========================================================================
# 10. Public routers are rate limited
# ===========================================================================

async def test_public_routes_take_a_request_parameter():
    """`@limiter.limit` raises at call time unless the endpoint takes `request`."""
    from webapp.routers import content, filters

    for module in (content, filters):
        for route in module.router.routes:
            assert "request" in route.endpoint.__code__.co_varnames, route.path


# ===========================================================================
# 11. A channel re-check is audited
# ===========================================================================

async def test_check_channel_writes_an_audit_row(tmp_path, monkeypatch):
    from webapp.routers import admin_channels

    conn = await migrated_conn(tmp_path, "channels.sqlite3")
    app = FastAPI()
    app.include_router(admin_channels.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: conn
    override_admin_deps(app, admin_channels.router, {"user_id": 99, "role": "admin"})

    async def _fake_validate(target):
        return {"status": admin_channels.STATUS_OK, "title": "Chan", "chat_id": -100123}

    monkeypatch.setattr(admin_channels, "validate_target", _fake_validate)
    try:
        await conn.execute("INSERT INTO channels (id, enabled) VALUES ('@ch', 1)")
        await conn.commit()

        async with client_for(app) as client:
            response = await client.post(
                "/api/admin/channels/@ch/check", headers={"x-real-ip": "198.51.100.7"}
            )
        assert response.status_code == 200, response.text

        cursor = await conn.execute(
            "SELECT actor_id, action, target_id, payload_json, ip FROM admin_audit_log "
            "WHERE action = 'channels.check'"
        )
        row = await cursor.fetchone()
        assert row is not None, "a re-check must leave an audit row"
        assert row["actor_id"] == 99 and row["target_id"] == "@ch"
        assert row["ip"] == "198.51.100.7"
        assert json.loads(row["payload_json"])["ok"] is True
    finally:
        await conn.close()


# ===========================================================================
# 12. Only *stale* broadcast claims are reset
# ===========================================================================

async def test_reset_stale_claims_leaves_a_fresh_claim_alone(tmp_path):
    from src.functions.broadcast_worker import STALE_CLAIM_SECONDS, reset_stale_claims

    conn = await migrated_conn(tmp_path, "claims.sqlite3")
    try:
        now = int(time.time())
        await conn.executemany(
            "INSERT INTO broadcast_targets (broadcast_id, user_id, status, claimed_at) "
            "VALUES (1, ?, 'sending', ?)",
            [(1, now), (2, now - STALE_CLAIM_SECONDS - 1), (3, None)],
        )
        await conn.commit()

        reset = await reset_stale_claims(conn)
        assert reset == 2, "the crashed claims and the pre-m015 row, not the live one"

        cursor = await conn.execute(
            "SELECT user_id, status FROM broadcast_targets ORDER BY user_id"
        )
        statuses = {int(row["user_id"]): row["status"] for row in await cursor.fetchall()}
        assert statuses == {1: "sending", 2: "pending", 3: "pending"}
    finally:
        await conn.close()


async def test_claiming_a_batch_stamps_claimed_at(tmp_path):
    from src.functions.broadcast_worker import _claim_batch

    conn = await migrated_conn(tmp_path, "claim_stamp.sqlite3")
    try:
        await conn.execute(
            "INSERT INTO broadcast_targets (broadcast_id, user_id, status) VALUES (1, 7, 'pending')"
        )
        await conn.commit()
        assert await _claim_batch(conn, 1, 10) == [7]
        cursor = await conn.execute(
            "SELECT claimed_at FROM broadcast_targets WHERE broadcast_id = 1 AND user_id = 7"
        )
        assert int((await cursor.fetchone())["claimed_at"]) > 0
    finally:
        await conn.close()


# ===========================================================================
# 14. post_now is deduped; bot_jobs/auto_post_log are purged
# ===========================================================================

async def test_post_now_refuses_a_second_queued_job(tmp_path):
    from webapp.routers import admin_autopost

    conn = await migrated_conn(tmp_path, "postnow.sqlite3")
    app = FastAPI()
    app.include_router(admin_autopost.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: conn
    override_admin_deps(app, admin_autopost.router, {"user_id": 99, "role": "admin"})
    try:
        async with client_for(app) as client:
            first = await client.post("/api/admin/auto-post/post-now", json={})
            assert first.status_code == 200, first.text
            second = await client.post("/api/admin/auto-post/post-now", json={})
        assert second.status_code == 409
        assert second.json()["detail"]["code"] == admin_autopost.JOB_ALREADY_QUEUED

        cursor = await conn.execute(
            "SELECT COUNT(*) FROM bot_jobs WHERE kind = 'auto_post.post_now'"
        )
        assert int((await cursor.fetchone())[0]) == 1

        # Once the job is finished, a new one may be queued again.
        await conn.execute("UPDATE bot_jobs SET status = 'done', finished_at = ?", (int(time.time()),))
        await conn.commit()
        async with client_for(app) as client:
            third = await client.post("/api/admin/auto-post/post-now", json={})
        assert third.status_code == 200, third.text
    finally:
        await conn.close()


async def test_retention_purges_finished_jobs_and_old_auto_post_log(tmp_path):
    from webapp.core.retention import (
        AUTO_POST_LOG_TTL_SECONDS,
        BOT_JOBS_TTL_SECONDS,
        purge_expired,
    )

    conn = await migrated_conn(tmp_path, "retention.sqlite3")
    try:
        now = int(time.time())
        await conn.executemany(
            "INSERT INTO bot_jobs (kind, status, created_at, finished_at) VALUES (?, ?, ?, ?)",
            [
                ("settings.reload", "done", now - BOT_JOBS_TTL_SECONDS - 10, now - BOT_JOBS_TTL_SECONDS - 10),
                ("settings.reload", "done", now, now),
                ("settings.reload", "queued", now - BOT_JOBS_TTL_SECONDS - 10, None),
            ],
        )
        await conn.executemany(
            "INSERT INTO auto_post_log (uid, channel, status, posted_at) VALUES ('u', '@c', 'sent', ?)",
            [(now - AUTO_POST_LOG_TTL_SECONDS - 10,), (now,)],
        )
        await conn.commit()

        deleted = await purge_expired(conn)
        assert deleted["bot_jobs"] == 1
        assert deleted["auto_post_log"] == 1

        cursor = await conn.execute("SELECT COUNT(*) FROM bot_jobs")
        assert int((await cursor.fetchone())[0]) == 2, "a queued job is live work"
    finally:
        await conn.close()
