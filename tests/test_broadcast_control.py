import aiosqlite
import pytest

from src.functions.broadcast_control import TRANSITIONS, set_broadcast_state


@pytest.fixture
async def conn():
    db = await aiosqlite.connect(":memory:")
    await db.execute(
        "CREATE TABLE broadcasts (id INTEGER PRIMARY KEY, status TEXT NOT NULL, finished_at INTEGER)"
    )
    try:
        yield db
    finally:
        await db.close()


async def _status(db, broadcast_id):
    cur = await db.execute("SELECT status, finished_at FROM broadcasts WHERE id = ?", (broadcast_id,))
    return await cur.fetchone()


@pytest.mark.parametrize(
    "start,action,expected",
    [
        ("queued", "pause", "paused"),
        ("running", "pause", "paused"),
        ("paused", "resume", "queued"),
        ("draft", "cancel", "cancelled"),
        ("queued", "cancel", "cancelled"),
        ("running", "cancel", "cancelled"),
        ("paused", "cancel", "cancelled"),
    ],
)
async def test_allowed_transitions(conn, start, action, expected):
    await conn.execute("INSERT INTO broadcasts (id, status) VALUES (1, ?)", (start,))
    assert await set_broadcast_state(conn, 1, action) == (start, expected)
    status, finished_at = await _status(conn, 1)
    assert status == expected
    assert (finished_at is not None) == (expected == "cancelled")


@pytest.mark.parametrize(
    "start,action",
    [
        ("draft", "pause"),
        ("paused", "pause"),
        ("done", "pause"),
        ("queued", "resume"),
        ("running", "resume"),
        ("cancelled", "resume"),
        ("done", "cancel"),
        ("failed", "cancel"),
        ("cancelled", "cancel"),
    ],
)
async def test_refused_transitions_change_nothing(conn, start, action):
    await conn.execute("INSERT INTO broadcasts (id, status) VALUES (1, ?)", (start,))
    assert await set_broadcast_state(conn, 1, action) is None
    assert (await _status(conn, 1))[0] == start


async def test_missing_broadcast_and_unknown_action(conn):
    assert await set_broadcast_state(conn, 99, "pause") is None
    with pytest.raises(ValueError):
        await set_broadcast_state(conn, 1, "explode")


async def test_lost_race_returns_none(conn):
    """The status changed between the read and the conditional UPDATE."""
    await conn.execute("INSERT INTO broadcasts (id, status) VALUES (1, 'running')")

    class Racing:
        def __init__(self, db):
            self.db = db

        async def execute(self, sql, params=()):
            if sql.startswith("UPDATE"):
                await self.db.execute("UPDATE broadcasts SET status = 'done' WHERE id = 1")
            return await self.db.execute(sql, params)

    assert await set_broadcast_state(Racing(conn), 1, "pause") is None
    assert (await _status(conn, 1))[0] == "done"


def test_transition_table_matches_schema_statuses():
    schema = {"draft", "queued", "running", "paused", "cancelled", "done", "failed"}
    for allowed, new in TRANSITIONS.values():
        assert set(allowed) <= schema and new in schema
