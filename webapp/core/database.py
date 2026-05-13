from collections.abc import AsyncGenerator

import aiosqlite

from webapp.core.config import DB_PATH

USER_EXTRA_COLUMNS = {
    "ref_by": "INTEGER",
    "username": "TEXT",
    "first_name": "TEXT",
    "photo_url": "TEXT",
}


async def _ensure_user_columns(conn: aiosqlite.Connection) -> None:
    cursor = await conn.execute("PRAGMA table_info(users)")
    existing = {row[1] for row in await cursor.fetchall()}

    for column, col_type in USER_EXTRA_COLUMNS.items():
        if column not in existing:
            await conn.execute(f"ALTER TABLE users ADD COLUMN {column} {col_type}")


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_user_columns(conn)

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS webapp_sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_webapp_sessions_user_id ON webapp_sessions(user_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_webapp_sessions_expires_at ON webapp_sessions(expires_at)"
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_handoff_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                expires_at INTEGER NOT NULL
            )
            """
        )
        await conn.commit()


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()
