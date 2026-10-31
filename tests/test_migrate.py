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


async def _ref_by_index(conn):
    """(partial?, sql) of idx_users_ref_by, or None when it does not exist."""
    cursor = await conn.execute("PRAGMA index_list(users)")
    for row in await cursor.fetchall():
        if row[1] == "idx_users_ref_by":
            cursor = await conn.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'idx_users_ref_by'"
            )
            return bool(row[4]), (await cursor.fetchone())[0]
    return None


async def _uses_index(conn, sql: str, params: tuple) -> bool:
    cursor = await conn.execute(f"EXPLAIN QUERY PLAN {sql}", params)
    return any("idx_users_ref_by" in str(row[3]) for row in await cursor.fetchall())


@pytest.mark.asyncio
async def test_m016_replaces_the_full_ref_by_index_left_by_init_db():
    """A prod-shaped DB: init_db's full index existed before m014, so m014 was a no-op."""
    async with aiosqlite.connect(":memory:") as conn:
        await conn.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, date INTEGER, lang TEXT, ref_by INTEGER)"
        )
        await conn.execute("CREATE INDEX idx_users_ref_by ON users(ref_by)")  # the old init_db DDL
        await conn.executemany(
            "INSERT INTO users (user_id, ref_by) VALUES (?, ?)",
            [(900000000000 + i, 900000000000 if i % 10 == 0 else None) for i in range(1, 200)],
        )
        await conn.commit()
        assert (await _ref_by_index(conn))[0] is False

        applied = await run_migrations(conn)
        assert "m014_ref_by_index" in applied and "m016_ref_by_partial_index" in applied

        partial, sql = await _ref_by_index(conn)
        assert partial is True
        assert "WHERE ref_by IS NOT NULL" in sql
        # Still serves every query shape the code runs on the column.
        assert await _uses_index(conn, "SELECT COUNT(*) FROM users WHERE ref_by = ?", (900000000000,))
        assert await _uses_index(
            conn, "SELECT ref_by, COUNT(*) FROM users WHERE ref_by IS NOT NULL GROUP BY ref_by", ()
        )
        cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE ref_by = ?", (900000000000,))
        assert (await cursor.fetchone())[0] == 19


@pytest.mark.asyncio
async def test_m016_is_a_noop_on_a_partial_index_and_without_the_column():
    from src.db.migrations import m016_ref_by_partial_index as m016

    async with aiosqlite.connect(":memory:") as conn:
        await conn.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY)")
        await m016.apply(conn)  # no ref_by column: nothing to index
        assert await _ref_by_index(conn) is None

        await conn.execute("ALTER TABLE users ADD COLUMN ref_by INTEGER")
        await m016.apply(conn)
        await m016.apply(conn)  # idempotent
        assert (await _ref_by_index(conn))[0] is True


@pytest.mark.asyncio
async def test_init_db_creates_the_partial_ref_by_index(tmp_path, monkeypatch):
    from webapp.core import database

    path = tmp_path / "fresh.sqlite3"
    async with aiosqlite.connect(path) as conn:
        await conn.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY, date INTEGER, ref_by INTEGER)")
        await conn.commit()
        # Every migration already applied and the index gone: only init_db's own DDL can recreate it.
        await run_migrations(conn)
        await conn.execute("DROP INDEX idx_users_ref_by")
        await conn.commit()
    monkeypatch.setattr(database, "DB_PATH", path)
    await database.init_db()
    async with aiosqlite.connect(path) as conn:
        assert (await _ref_by_index(conn))[0] is True
