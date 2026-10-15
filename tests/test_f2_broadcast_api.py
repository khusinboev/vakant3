"""F2: the broadcast detail's "last 20 errors" ordering.

Failed and blocked targets never get ``sent_at`` and no failure timestamp is
written (``claimed_at`` is cleared on every result write), so ordering by
``sent_at`` sorted nothing. The list is ordered by ``rowid DESC`` instead.
User ids are synthetic (900000000000+).
"""
import aiosqlite
import pytest
from fastapi.testclient import TestClient

from src.db.migrate import run_migrations
from tests.test_b2_broadcast_api import _make_app

BASE = 900_000_000_000
ACTOR = BASE + 77


@pytest.fixture
async def db_path(tmp_path):
    path = tmp_path / "f2api.sqlite3"
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, date INTEGER, lang TEXT, region TEXT, "
            "user_pro INTEGER NOT NULL DEFAULT 0, blocked INTEGER NOT NULL DEFAULT 0)"
        )
        await conn.commit()
        await run_migrations(conn)
        await conn.execute(
            "INSERT INTO broadcasts (id, actor_id, status, kind, text, created_at) "
            "VALUES (1, ?, 'done', 'text', 'salom', 0)",
            (ACTOR,),
        )
        # Rows in insertion order that differs from user id order; one sent
        # row with a timestamp must not change where the failures land.
        rows = [
            (BASE + 5, "failed", None),
            (BASE + 1, "blocked", None),
            (BASE + 9, "sent", 1_800_000_000),
            (BASE + 3, "failed", None),
        ]
        rows += [(BASE + 100 + i, "failed", None) for i in range(25)]
        await conn.executemany(
            "INSERT INTO broadcast_targets (broadcast_id, user_id, status, error, error_kind, sent_at) "
            "VALUES (1, ?, ?, CASE WHEN ? = 'sent' THEN NULL ELSE 'x' END, NULL, ?)",
            [(uid, status, status, sent_at) for uid, status, sent_at in rows],
        )
        await conn.commit()
    return path


def test_last_errors_are_the_last_20_rows_newest_first(db_path):
    with TestClient(_make_app(db_path)) as client:
        response = client.get("/api/admin/broadcasts/1")
    assert response.status_code == 200
    errors = response.json()["errors"]
    assert [row["user_id"] for row in errors] == [BASE + 100 + i for i in range(24, 4, -1)]
    assert all(row["status"] in ("failed", "blocked") for row in errors)


async def test_last_errors_follow_row_order_not_user_id(db_path):
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("DELETE FROM broadcast_targets WHERE user_id >= ?", (BASE + 100,))
        await conn.commit()
    with TestClient(_make_app(db_path)) as client:
        errors = client.get("/api/admin/broadcasts/1").json()["errors"]
    # rowid DESC: last inserted first; user_id DESC would give 5, 3, 1.
    assert [row["user_id"] for row in errors] == [BASE + 3, BASE + 1, BASE + 5]
