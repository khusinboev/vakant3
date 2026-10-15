"""Stage B admin API: pause/resume/cancel through broadcast_control, audit, detail breakdown."""
import json

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.db.migrate import run_migrations
from webapp.core import auth as auth_module
from webapp.core.database import get_db
from webapp.core.limiter import limiter
from webapp.routers import admin_broadcasts

BASE = 900_000_000_000
ACTOR = BASE + 77


@pytest.fixture
async def db_path(tmp_path):
    path = tmp_path / "b2api.sqlite3"
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, date INTEGER, lang TEXT, region TEXT, "
            "user_pro INTEGER NOT NULL DEFAULT 0, blocked INTEGER NOT NULL DEFAULT 0)"
        )
        await conn.commit()
        await run_migrations(conn)
        for broadcast_id, status in enumerate(
            ["draft", "queued", "running", "paused", "done", "cancelled", "failed"], start=1
        ):
            await conn.execute(
                "INSERT INTO broadcasts (id, actor_id, status, kind, text, created_at) "
                "VALUES (?, ?, ?, 'text', 'salom', 0)",
                (broadcast_id, ACTOR, status),
            )
        await conn.commit()
    return path


def _make_app(db_path, actor=None, *, real_role_check=False, monkeypatch=None):
    async def _db():
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    try:
        limiter.reset()
    except Exception:  # pragma: no cover - depends on the slowapi version
        limiter._storage.reset()
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(admin_broadcasts.router, prefix="/api")
    app.dependency_overrides[get_db] = _db
    actor = actor or {"user_id": ACTOR, "role": "admin"}
    if real_role_check:
        async def _admin(request, db):
            return actor

        monkeypatch.setattr(auth_module, "require_admin", _admin)
    else:
        app.dependency_overrides[admin_broadcasts.require_broadcast_admin] = lambda: actor
    return app


@pytest.fixture
def client(db_path):
    with TestClient(_make_app(db_path)) as test_client:
        yield test_client


async def _status(db_path, broadcast_id):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("SELECT status FROM broadcasts WHERE id = ?", (broadcast_id,))
        return (await cursor.fetchone())[0]


async def _audit(db_path):
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT actor_id, action, target_type, target_id, payload_json FROM admin_audit_log ORDER BY id"
        )
        return [
            (row[0], row[1], row[2], row[3], json.loads(row[4] or "null"))
            for row in await cursor.fetchall()
        ]


# ─── pause / resume ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("broadcast_id, start", [(2, "queued"), (3, "running")])
async def test_pause_holds_an_active_broadcast_and_audits_it(client, db_path, broadcast_id, start):
    response = client.post(f"/api/admin/broadcasts/{broadcast_id}/pause")
    assert response.status_code == 200, response.text
    assert response.json() == {"id": broadcast_id, "status": "paused"}
    assert await _status(db_path, broadcast_id) == "paused"
    assert await _audit(db_path) == [
        (ACTOR, "broadcast.pause", "broadcast", str(broadcast_id), {"from": start, "to": "paused"})
    ]


async def test_resume_requeues_a_paused_broadcast_and_audits_it(client, db_path):
    response = client.post("/api/admin/broadcasts/4/resume")
    assert response.status_code == 200, response.text
    assert response.json() == {"id": 4, "status": "queued"}
    assert await _status(db_path, 4) == "queued"
    assert await _audit(db_path) == [
        (ACTOR, "broadcast.resume", "broadcast", "4", {"from": "paused", "to": "queued"})
    ]


@pytest.mark.parametrize(
    "action, broadcast_id, status, code",
    [
        ("pause", 1, "draft", "BROADCAST_NOT_PAUSABLE"),
        ("pause", 4, "paused", "BROADCAST_NOT_PAUSABLE"),
        ("pause", 5, "done", "BROADCAST_NOT_PAUSABLE"),
        ("resume", 2, "queued", "BROADCAST_NOT_RESUMABLE"),
        ("resume", 3, "running", "BROADCAST_NOT_RESUMABLE"),
        ("resume", 6, "cancelled", "BROADCAST_NOT_RESUMABLE"),
        ("resume", 7, "failed", "BROADCAST_NOT_RESUMABLE"),
        ("cancel", 5, "done", "BROADCAST_NOT_CANCELLABLE"),
        ("cancel", 6, "cancelled", "BROADCAST_NOT_CANCELLABLE"),
    ],
)
async def test_refused_transitions_are_409_and_change_nothing(
    client, db_path, action, broadcast_id, status, code
):
    response = client.post(f"/api/admin/broadcasts/{broadcast_id}/{action}")
    assert response.status_code == 409
    assert response.json()["detail"] == {"code": code, "status": status}
    assert await _status(db_path, broadcast_id) == status
    assert await _audit(db_path) == []


@pytest.mark.parametrize("action", ["pause", "resume", "cancel"])
def test_unknown_broadcast_is_404(client, action):
    response = client.post(f"/api/admin/broadcasts/999/{action}")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND"


async def test_cancel_keeps_its_response_and_audit_action(client, db_path):
    response = client.post("/api/admin/broadcasts/4/cancel")
    assert response.status_code == 200
    assert response.json() == {"id": 4, "status": "cancelled"}
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("SELECT status, finished_at FROM broadcasts WHERE id = 4")
        status, finished_at = await cursor.fetchone()
    assert status == "cancelled" and finished_at
    assert await _audit(db_path) == [
        (ACTOR, "broadcast.cancel", "broadcast", "4", {"from": "paused", "to": "cancelled"})
    ]


async def test_the_audit_row_and_the_transition_share_one_transaction(db_path, monkeypatch):
    async def broken_audit(*args, **kwargs):
        raise RuntimeError("audit insert failed")

    monkeypatch.setattr(admin_broadcasts, "log_admin_action", broken_audit)
    with TestClient(_make_app(db_path), raise_server_exceptions=False) as test_client:
        response = test_client.post("/api/admin/broadcasts/3/pause")
    assert response.status_code == 500
    assert await _status(db_path, 3) == "running"  # the UPDATE was never committed


async def test_pause_and_resume_need_the_admin_role(db_path, monkeypatch):
    app = _make_app(
        db_path, {"user_id": ACTOR, "role": "moderator"}, real_role_check=True, monkeypatch=monkeypatch
    )
    with TestClient(app) as test_client:
        for path in ("/api/admin/broadcasts/3/pause", "/api/admin/broadcasts/4/resume"):
            response = test_client.post(path)
            assert response.status_code == 403
            assert response.json()["detail"]["code"] == "ADMIN_REQUIRED"
    assert await _status(db_path, 3) == "running" and await _status(db_path, 4) == "paused"

    app = _make_app(
        db_path, {"user_id": ACTOR, "role": "admin"}, real_role_check=True, monkeypatch=monkeypatch
    )
    with TestClient(app) as test_client:
        assert test_client.post("/api/admin/broadcasts/3/pause").status_code == 200


@pytest.mark.parametrize("action, broadcast_id", [("pause", 3), ("resume", 4), ("cancel", 2)])
def test_state_changes_are_rate_limited_at_ten_per_minute(client, action, broadcast_id):
    codes = [
        client.post(f"/api/admin/broadcasts/{broadcast_id}/{action}").status_code for _ in range(11)
    ]
    assert codes[0] == 200
    assert set(codes[1:10]) == {409}  # refused calls still count
    assert codes[10] == 429


# ─── detail ─────────────────────────────────────────────────────────────────

async def test_detail_reports_error_kinds_and_retry_state(client, db_path):
    async with aiosqlite.connect(db_path) as conn:
        await conn.executemany(
            "INSERT INTO broadcast_targets "
            "(broadcast_id, user_id, status, error, error_kind, attempts, next_attempt_at) "
            "VALUES (3, ?, ?, ?, ?, ?, ?)",
            [
                (BASE + 1, "sent", None, None, 1, None),
                (BASE + 2, "sent", None, None, 3, None),
                (BASE + 3, "failed", "Bad Request: can't parse entities", "bad_request", 1, None),
                (BASE + 4, "failed", "Bad Request: chat not found", "chat_not_found", 1, None),
                (BASE + 5, "failed", "timeout", "network", 6, None),
                (BASE + 6, "blocked", "Forbidden: bot was blocked", "blocked", 1, None),
                (BASE + 7, "blocked", "Forbidden: user is deactivated", "deactivated", 1, None),
                (BASE + 8, "pending", "Too Many Requests", "flood", 1, 1_800_000_040),
                (BASE + 9, "pending", "Bad Gateway", "network", 2, 1_800_000_020),
                (BASE + 10, "pending", None, None, 0, None),
            ],
        )
        await conn.commit()

    detail = client.get("/api/admin/broadcasts/3").json()
    assert detail["error_kinds"] == {
        "bad_request": 1, "chat_not_found": 1, "network": 1, "blocked": 1, "deactivated": 1,
    }
    assert detail["retry"] == {
        "scheduled": 2,
        "next_attempt_at": 1_800_000_020,
        "retried": 3,            # users 2, 5 and 9 needed more than one send
        "extra_attempts": 2 + 5 + 1,
    }
    assert detail["targets"] == {"sent": 2, "failed": 3, "blocked": 2, "pending": 3}
    by_user = {row["user_id"]: row for row in detail["errors"]}
    assert set(by_user) == {BASE + 3, BASE + 4, BASE + 5, BASE + 6, BASE + 7}
    assert by_user[BASE + 5]["error_kind"] == "network" and by_user[BASE + 5]["attempts"] == 6
    assert "content_failed" in detail
