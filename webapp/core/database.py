from collections.abc import AsyncGenerator

import aiosqlite

from webapp.core.config import DB_PATH

USER_EXTRA_COLUMNS = {
    "ref_by": "INTEGER",
    "username": "TEXT",
    "first_name": "TEXT",
    "photo_url": "TEXT",
    "user_balance": "INTEGER",
    "user_pro": "INTEGER",
}


async def _ensure_performance_indexes(conn: aiosqlite.Connection) -> None:
    cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in await cursor.fetchall()}

    if "users" in tables:
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_ref_by ON users(ref_by)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_user_pro ON users(user_pro)")

    if "saves" in tables:
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_saves_user_id_save_id ON saves(user_id, save_id)")

    if "vacancy_cache" in tables:
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_vacancy_cache_expires_at ON vacancy_cache(expires_at)")


async def _ensure_user_columns(conn: aiosqlite.Connection) -> None:
    cursor = await conn.execute("PRAGMA table_info(users)")
    existing = {row[1] for row in await cursor.fetchall()}

    for column, col_type in USER_EXTRA_COLUMNS.items():
        if column not in existing:
            await conn.execute(f"ALTER TABLE users ADD COLUMN {column} {col_type}")


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.execute("PRAGMA busy_timeout=5000")

        await _ensure_user_columns(conn)
        await _ensure_performance_indexes(conn)

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
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS webapp_admin_settings (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                auto_post_enabled INTEGER NOT NULL DEFAULT 0,
                auto_post_channel TEXT NOT NULL DEFAULT '',
                auto_post_min_salary INTEGER NOT NULL DEFAULT 8000000,
                referral_enabled INTEGER NOT NULL DEFAULT 0,
                referral_required_count INTEGER NOT NULL DEFAULT 0,
                next_auto_post_ts INTEGER NOT NULL DEFAULT 0,
                pro_price INTEGER NOT NULL DEFAULT 10000,
                referral_reward INTEGER NOT NULL DEFAULT 2000,
                pro_min_salary INTEGER NOT NULL DEFAULT 8000000
            )
            """
        )
        # Migrate existing rows — add missing columns if not present
        cursor = await conn.execute("PRAGMA table_info(webapp_admin_settings)")
        admin_cols = {row[1] for row in await cursor.fetchall()}
        for col, default in [
            ("pro_price", 10000),
            ("referral_reward", 2000),
            ("pro_min_salary", 8000000),
        ]:
            if col not in admin_cols:
                await conn.execute(
                    f"ALTER TABLE webapp_admin_settings ADD COLUMN {col} INTEGER NOT NULL DEFAULT {default}"
                )
        await conn.execute(
            """
            INSERT OR IGNORE INTO webapp_admin_settings (
                singleton,
                auto_post_enabled,
                auto_post_channel,
                auto_post_min_salary,
                referral_enabled,
                referral_required_count,
                next_auto_post_ts,
                pro_price,
                referral_reward,
                pro_min_salary
            )
            VALUES (1, 0, '', 8000000, 0, 0, 0, 10000, 2000, 8000000)
            """
        )
        await conn.commit()


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        await conn.close()
