"""``autopost_min_quality`` admin setting (m024) against the real app (b3 harness)."""

from __future__ import annotations

import json

import aiosqlite

from src.db.migrate import run_migrations
from tests import b3_support
from tests.b3_support import ADMIN, VIEWER

harness = b3_support.harness


async def test_min_quality_setting_default_bounds_version_and_audit(harness):
    h = harness
    # init_db (not run by the harness) adds this column in production.
    await h.execute("ALTER TABLE webapp_admin_settings ADD COLUMN channel_lang TEXT NOT NULL DEFAULT 'uz'")
    headers = await h.session(ADMIN)
    state = (await h.http.get("/api/admin/state", headers=headers)).json()
    assert state["autopost_min_quality"] == 60
    version = state["version"]

    ok = await h.http.patch(
        "/api/admin/state", json={"autopost_min_quality": 75, "expected_version": version}, headers=headers
    )
    assert ok.status_code == 200 and ok.json()["autopost_min_quality"] == 75
    assert ok.json()["version"] == version + 1

    stale = await h.http.patch(
        "/api/admin/state", json={"autopost_min_quality": 10, "expected_version": version}, headers=headers
    )
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "SETTINGS_CONFLICT"
    for bad in (101, -1):
        response = await h.http.patch("/api/admin/state", json={"autopost_min_quality": bad}, headers=headers)
        assert response.status_code == 422
    viewer = await h.http.patch(
        "/api/admin/state", json={"autopost_min_quality": 5}, headers=await h.session(VIEWER)
    )
    assert viewer.status_code == 403

    assert await h.scalar("SELECT autopost_min_quality FROM webapp_admin_settings") == 75
    audit = await h.audit("settings.patch")
    assert json.loads(audit[-1]["payload_json"])["diff"] == {"autopost_min_quality": [60, 75]}


async def test_m024_is_idempotent_and_skips_a_missing_settings_table(tmp_path):
    from src.db.migrations import m024_autopost_min_quality as m024

    async with aiosqlite.connect(tmp_path / "a.sqlite3") as conn:
        # No settings table yet (bot first on a fresh DB): nothing to do, no error.
        await m024.apply(conn)
        await conn.execute("CREATE TABLE webapp_admin_settings (singleton INTEGER PRIMARY KEY)")
        await conn.execute("INSERT INTO webapp_admin_settings (singleton) VALUES (1)")
        await m024.apply(conn)
        await m024.apply(conn)  # re-applied: still one column, no error
        cursor = await conn.execute("PRAGMA table_info(webapp_admin_settings)")
        names = [row[1] for row in await cursor.fetchall()]
        assert names.count("autopost_min_quality") == 1
        cursor = await conn.execute("SELECT autopost_min_quality FROM webapp_admin_settings")
        assert (await cursor.fetchone())[0] == 60

    async with aiosqlite.connect(tmp_path / "b.sqlite3") as conn:
        applied = await run_migrations(conn)
        assert "m024_autopost_min_quality" in applied
        assert "m024_autopost_min_quality" not in await run_migrations(conn)
