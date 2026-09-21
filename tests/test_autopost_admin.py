"""Tests for the AUTOPOST slice: bot_jobs queue, the refactored auto-post
scheduler (pick_and_post / auto_post_log) and webapp/routers/admin_autopost.py.

Router tests build a throwaway FastAPI app containing ONLY
``admin_autopost.router`` with ``get_db`` overridden to a temp SQLite file and
the ``require_role``/``require_confirmation`` dependency nodes (found by
walking the dependant tree via their ``__require_role__``/``__confirm_action__``
markers — see webapp/core/auth.py and webapp/core/confirm.py) overridden with
a fixed actor, so these tests do not depend on real sessions/tokens.
"""
from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiosqlite
import httpx
import pytest
from fastapi import FastAPI

from src.db.migrate import run_migrations
from src.db.settings import ensure_settings_columns
from src.functions.bot_jobs import JOB_HANDLERS, claim_next_job, enqueue_job, run_claimed_job
from src.functions.auto_post_scheduler import _handle_post_now, pick_and_post
from webapp.core.database import get_db
from webapp.routers import admin_autopost

pytestmark = pytest.mark.asyncio


# ─── shared helpers ──────────────────────────────────────────────────────────

async def _migrated_conn(tmp_path, name: str = "db.sqlite3") -> aiosqlite.Connection:
    """A fresh SQLite file with every mNNN migration applied (bot_jobs, auto_post_log, ...)."""
    conn = await aiosqlite.connect(str(tmp_path / name))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA busy_timeout=5000")
    await run_migrations(conn)
    await ensure_settings_columns(conn)  # channel_lang etc. (bot-added, not a migration)
    return conn


async def _add_auto_post_tables(conn: aiosqlite.Connection) -> None:
    """``vacancy_cache``/``posted_vacancies`` are created by the webapp (not a migration)."""
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS vacancy_cache (
            uid TEXT PRIMARY KEY, data_json TEXT NOT NULL, expires_at INTEGER NOT NULL
        )"""
    )
    await conn.execute(
        """CREATE TABLE IF NOT EXISTS posted_vacancies (
            vacancy_uid TEXT NOT NULL, channel TEXT NOT NULL, posted_at INTEGER NOT NULL,
            PRIMARY KEY (vacancy_uid, channel)
        )"""
    )
    await conn.commit()


async def _seed_admin_settings(conn: aiosqlite.Connection, **overrides) -> None:
    row = {
        "auto_post_enabled": 1,
        "auto_post_channel": "@ch",
        "auto_post_min_salary": 0,
        "channel_lang": "uz",
    }
    row.update(overrides)
    cols = ", ".join(row.keys())
    placeholders = ", ".join("?" for _ in row)
    await conn.execute(
        f"INSERT INTO webapp_admin_settings (singleton, {cols}) VALUES (1, {placeholders})",
        tuple(row.values()),
    )
    await conn.commit()


def _walk_dependant(dependant):
    yield dependant
    for sub in dependant.dependencies:
        yield from _walk_dependant(sub)


def _build_app(conn: aiosqlite.Connection, actor: dict) -> FastAPI:
    """A minimal app hosting only admin_autopost.router, deps overridden for `actor`."""
    app = FastAPI()
    app.include_router(admin_autopost.router, prefix="/api")

    async def _get_db_override():
        return conn

    app.dependency_overrides[get_db] = _get_db_override

    async def _actor_override():
        return actor

    seen = set()
    for route in admin_autopost.router.routes:
        for dep in _walk_dependant(route.dependant):
            call = dep.call
            if call is None or call in seen:
                continue
            if getattr(call, "__require_role__", None) is not None or getattr(
                call, "__confirm_action__", None
            ) is not None:
                seen.add(call)
                app.dependency_overrides[call] = _actor_override
    return app


# ─── bot_jobs: exclusive claim ───────────────────────────────────────────────

async def test_claim_next_job_is_exclusive(tmp_path):
    """Two pollers racing for the same queued row: exactly one wins."""
    setup_conn = await _migrated_conn(tmp_path, "jobs.sqlite3")
    await enqueue_job(setup_conn, "settings.reload", {})
    await setup_conn.commit()
    await setup_conn.close()

    db_path = tmp_path / "jobs.sqlite3"
    conn_a = await aiosqlite.connect(str(db_path))
    conn_a.row_factory = aiosqlite.Row
    await conn_a.execute("PRAGMA journal_mode=WAL")
    await conn_a.execute("PRAGMA busy_timeout=5000")

    conn_b = await aiosqlite.connect(str(db_path))
    conn_b.row_factory = aiosqlite.Row
    await conn_b.execute("PRAGMA journal_mode=WAL")
    await conn_b.execute("PRAGMA busy_timeout=5000")

    try:
        results = await asyncio.gather(claim_next_job(conn_a), claim_next_job(conn_b))
    finally:
        await conn_a.close()
        await conn_b.close()

    winners = [r for r in results if r is not None]
    assert len(winners) == 1, "exactly one claimer should win the race"

    verify_conn = await aiosqlite.connect(str(db_path))
    verify_conn.row_factory = aiosqlite.Row
    cur = await verify_conn.execute("SELECT status FROM bot_jobs")
    row = await cur.fetchone()
    assert row["status"] == "running"
    await verify_conn.close()


async def test_claim_next_job_returns_none_when_empty(tmp_path):
    conn = await _migrated_conn(tmp_path)
    assert await claim_next_job(conn) is None
    await conn.close()


# ─── bot_jobs: handler error recorded ────────────────────────────────────────

async def test_handler_error_is_recorded(tmp_path):
    conn = await _migrated_conn(tmp_path)

    async def _boom(payload):
        raise RuntimeError("kaboom")

    JOB_HANDLERS["test.boom"] = _boom
    try:
        job_id = await enqueue_job(conn, "test.boom", {})
        await conn.commit()

        claimed = await claim_next_job(conn)
        assert claimed is not None
        await run_claimed_job(conn, claimed)

        cur = await conn.execute("SELECT status, error, finished_at FROM bot_jobs WHERE id = ?", (job_id,))
        row = await cur.fetchone()
        assert row["status"] == "failed"
        assert "kaboom" in row["error"]
        assert row["finished_at"] is not None
    finally:
        JOB_HANDLERS.pop("test.boom", None)
        await conn.close()


async def test_unknown_job_kind_fails_without_crashing_loop(tmp_path):
    conn = await _migrated_conn(tmp_path)
    job_id = await enqueue_job(conn, "does.not.exist", {})
    await conn.commit()

    claimed = await claim_next_job(conn)
    await run_claimed_job(conn, claimed)

    cur = await conn.execute("SELECT status, error FROM bot_jobs WHERE id = ?", (job_id,))
    row = await cur.fetchone()
    assert row["status"] == "failed"
    assert "does.not.exist" in row["error"]
    await conn.close()


# ─── auto_post_scheduler: pick_and_post / post_now ───────────────────────────

async def test_pick_and_post_sends_and_logs(tmp_path):
    conn = await _migrated_conn(tmp_path)
    await _add_auto_post_tables(conn)

    now_ts = int(time.time())
    await conn.execute(
        "INSERT INTO vacancy_cache (uid, data_json, expires_at) VALUES (?, ?, ?)",
        ("osonish_1", json.dumps({"title": "Dev", "salary_max": 0}), now_ts + 3600),
    )
    await conn.commit()

    mock_bot = AsyncMock()
    mock_bot.send_message.return_value = SimpleNamespace(message_id=555)
    with patch("src.functions.auto_post_scheduler.bot", mock_bot):
        result = await pick_and_post(conn, channel="@ch", min_salary=0, lang="uz")

    assert result == {"status": "sent", "uid": "osonish_1", "message_id": 555, "error": None}

    log_row = await (await conn.execute("SELECT * FROM auto_post_log")).fetchone()
    assert log_row["status"] == "sent"
    assert log_row["uid"] == "osonish_1"
    assert log_row["channel"] == "@ch"
    assert log_row["message_id"] == 555

    posted = await (
        await conn.execute("SELECT * FROM posted_vacancies WHERE channel = '@ch'")
    ).fetchone()
    assert posted["vacancy_uid"] == "osonish_1"
    await conn.close()


async def test_pick_and_post_skips_when_nothing_to_post(tmp_path):
    conn = await _migrated_conn(tmp_path)
    await _add_auto_post_tables(conn)

    mock_bot = AsyncMock()
    with patch("src.functions.auto_post_scheduler.bot", mock_bot):
        result = await pick_and_post(conn, channel="@ch", min_salary=0, lang="uz")

    assert result["status"] == "skipped"
    mock_bot.send_message.assert_not_called()

    log_row = await (await conn.execute("SELECT * FROM auto_post_log")).fetchone()
    assert log_row["status"] == "skipped"
    await conn.close()


async def test_pick_and_post_failed_send_is_logged_not_raised(tmp_path):
    conn = await _migrated_conn(tmp_path)
    await _add_auto_post_tables(conn)

    now_ts = int(time.time())
    await conn.execute(
        "INSERT INTO vacancy_cache (uid, data_json, expires_at) VALUES (?, ?, ?)",
        ("osonish_2", json.dumps({"title": "Dev"}), now_ts + 3600),
    )
    await conn.commit()

    mock_bot = AsyncMock()
    mock_bot.send_message.side_effect = RuntimeError("telegram down")
    with patch("src.functions.auto_post_scheduler.bot", mock_bot):
        result = await pick_and_post(conn, channel="@ch", min_salary=0, lang="uz")

    assert result["status"] == "failed"
    assert "telegram down" in result["error"]

    log_row = await (await conn.execute("SELECT * FROM auto_post_log")).fetchone()
    assert log_row["status"] == "failed"
    assert "telegram down" in log_row["error"]

    count = await (await conn.execute("SELECT COUNT(*) FROM posted_vacancies")).fetchone()
    assert count[0] == 0
    await conn.close()


async def test_handle_post_now_job_handler(tmp_path):
    """The registered ``auto_post.post_now`` bot_jobs handler end to end."""
    conn = await _migrated_conn(tmp_path)
    await _add_auto_post_tables(conn)
    await _seed_admin_settings(conn)

    now_ts = int(time.time())
    await conn.execute(
        "INSERT INTO vacancy_cache (uid, data_json, expires_at) VALUES (?, ?, ?)",
        ("osonish_9", json.dumps({"title": "Dev"}), now_ts + 3600),
    )
    await conn.commit()

    assert JOB_HANDLERS["auto_post.post_now"] is _handle_post_now

    mock_bot = AsyncMock()
    mock_bot.send_message.return_value = SimpleNamespace(message_id=777)

    class _ConnCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *exc):
            return False

    with patch("src.functions.auto_post_scheduler.bot", mock_bot), \
         patch("src.functions.auto_post_scheduler.connect", lambda: _ConnCtx()):
        out = await _handle_post_now({"uid": "osonish_9"})

    assert out == {"message_id": 777, "uid": "osonish_9"}

    log_row = await (await conn.execute("SELECT * FROM auto_post_log")).fetchone()
    assert log_row["status"] == "sent"
    assert log_row["uid"] == "osonish_9"
    await conn.close()


async def test_handle_post_now_raises_when_channel_unset(tmp_path):
    conn = await _migrated_conn(tmp_path)
    await _add_auto_post_tables(conn)
    await _seed_admin_settings(conn, auto_post_channel="")
    await conn.commit()

    class _ConnCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *exc):
            return False

    with patch("src.functions.auto_post_scheduler.connect", lambda: _ConnCtx()):
        with pytest.raises(RuntimeError):
            await _handle_post_now({})
    await conn.close()


# ─── admin_autopost router ───────────────────────────────────────────────────

async def test_history_pagination(tmp_path):
    conn = await _migrated_conn(tmp_path)
    now_ts = int(time.time())
    for i in range(5):
        await conn.execute(
            "INSERT INTO auto_post_log (uid, channel, message_id, status, error, posted_at) "
            "VALUES (?, ?, ?, 'sent', NULL, ?)",
            (f"uid{i}", "@ch", 100 + i, now_ts + i),
        )
    await conn.commit()

    app = _build_app(conn, {"user_id": 1, "role": "owner", "user": {}})
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        seen: list[str] = []
        cursor = None
        for _ in range(10):  # bounded loop guard against an infinite-pagination bug
            params = {"limit": 2}
            if cursor:
                params["cursor"] = cursor
            resp = await client.get("/api/admin/auto-post/history", params=params)
            assert resp.status_code == 200
            body = resp.json()
            seen.extend(item["uid"] for item in body["items"])
            cursor = body["next_cursor"]
            if cursor is None:
                break

    assert len(seen) == 5
    assert len(set(seen)) == 5  # no duplicates/skips across pages
    # newest first
    assert seen == ["uid4", "uid3", "uid2", "uid1", "uid0"]
    await conn.close()


async def test_post_now_writes_job_and_audit_row(tmp_path):
    conn = await _migrated_conn(tmp_path)

    app = _build_app(conn, {"user_id": 42, "role": "owner", "user": {}})
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/admin/auto-post/post-now", json={"uid": "osonish_5"})
        assert resp.status_code == 200
        body = resp.json()
        job_id = body["job_id"]
        assert body["status"] == "queued"

        row = await (
            await conn.execute(
                "SELECT kind, payload_json, status, created_by FROM bot_jobs WHERE id = ?",
                (job_id,),
            )
        ).fetchone()
        assert row["kind"] == "auto_post.post_now"
        assert json.loads(row["payload_json"]) == {"uid": "osonish_5"}
        assert row["status"] == "queued"
        assert row["created_by"] == 42

        audit_count = await (
            await conn.execute(
                "SELECT COUNT(*) FROM admin_audit_log WHERE action = 'autopost.post_now'"
            )
        ).fetchone()
        assert audit_count[0] == 1

        status_resp = await client.get(f"/api/admin/jobs/{job_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "queued"

        missing_resp = await client.get("/api/admin/jobs/999999")
        assert missing_resp.status_code == 404
        assert missing_resp.json()["detail"]["code"] == "NOT_FOUND"
    await conn.close()
