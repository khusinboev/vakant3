"""Retention purges expired ``admin_idempotency`` rows (m018), in chunks.

The router only deletes expired rows while claiming a new balance key, so a
quiet panel (or one that only exports) never cleaned the table up.
"""

import time

import aiosqlite
import pytest

from src.db.migrations import m018_admin_idempotency
from webapp.core import retention
from webapp.routers import admin_users

DAY = 24 * 60 * 60


@pytest.fixture
async def db(tmp_path):
    conn = await aiosqlite.connect(tmp_path / "retention_f1.sqlite3")
    conn.row_factory = aiosqlite.Row
    await m018_admin_idempotency.apply(conn)
    await conn.commit()
    try:
        yield conn
    finally:
        await conn.close()


async def _claim(conn, key: str, created_at: int, action: str = "users.balance") -> None:
    await conn.execute(
        "INSERT INTO admin_idempotency "
        "(actor_id, action, idem_key, target_id, body_hash, response_json, created_at) "
        "VALUES (?, ?, ?, NULL, 'h', NULL, ?)",
        (900_000_000_001, action, key, created_at),
    )


def test_ttl_never_drops_a_row_the_router_still_honours():
    assert retention.ADMIN_IDEMPOTENCY_TTL_SECONDS >= admin_users.IDEMPOTENCY_TTL_SECONDS
    # A consumed download-link claim must outlive the link, or it could be replayed.
    assert retention.ADMIN_IDEMPOTENCY_TTL_SECONDS > admin_users.EXPORT_LINK_TTL_SECONDS


async def test_expired_rows_go_and_live_ones_stay(db):
    now = int(time.time())
    ttl = retention.ADMIN_IDEMPOTENCY_TTL_SECONDS
    for i in range(5):
        await _claim(db, f"old-{i}", now - ttl - 60 - i)
    await _claim(db, "old-link", now - ttl - 1, action="users.export_download")
    await _claim(db, "fresh", now - ttl + 60)
    await _claim(db, "fresh-link", now, action="users.export_download")
    await db.commit()

    deleted = await retention.purge_expired(db, chunk=2)

    assert deleted["admin_idempotency"] == 6
    cursor = await db.execute("SELECT idem_key FROM admin_idempotency ORDER BY idem_key")
    assert [row[0] for row in await cursor.fetchall()] == ["fresh", "fresh-link"]


async def test_purge_is_chunked(db, monkeypatch):
    now = int(time.time())
    for i in range(5):
        await _claim(db, f"old-{i}", now - 2 * DAY)
    await db.commit()

    commits = 0
    original = db.commit

    async def counting_commit():
        nonlocal commits
        commits += 1
        await original()

    monkeypatch.setattr(db, "commit", counting_commit)
    deleted = await retention.purge_expired(db, chunk=2)

    assert deleted["admin_idempotency"] == 5
    assert commits == 3  # 2 + 2 + 1, one transaction per chunk


async def test_missing_table_is_skipped(tmp_path):
    async with aiosqlite.connect(tmp_path / "empty.sqlite3") as conn:
        assert "admin_idempotency" not in await retention.purge_expired(conn)
