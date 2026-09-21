import aiosqlite
import pytest

from src.db.migrate import add_column_if_missing, discover, run_migrations


@pytest.mark.asyncio
async def test_migrations_apply_once_and_in_order():
    async with aiosqlite.connect(":memory:") as conn:
        first = await run_migrations(conn)
        assert first == [m for m, _ in discover()]
        assert first[0] == "m000_baseline"
        second = await run_migrations(conn)
        assert second == []
        cursor = await conn.execute("SELECT COUNT(*) FROM schema_migrations")
        assert (await cursor.fetchone())[0] == len(first)


@pytest.mark.asyncio
async def test_add_column_if_missing_is_idempotent():
    async with aiosqlite.connect(":memory:") as conn:
        await conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        assert await add_column_if_missing(conn, "t", "x", "INTEGER NOT NULL DEFAULT 0") is True
        assert await add_column_if_missing(conn, "t", "x", "INTEGER NOT NULL DEFAULT 0") is False
