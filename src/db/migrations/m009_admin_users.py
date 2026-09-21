"""Moderation and Pro-expiry columns the admin Users module reads and writes.

``banned`` is deliberately separate from ``blocked``: ``blocked`` means *the
user blocked the bot* (set by the sender when Telegram returns 403), while
``banned`` is a moderator decision that the entry gate enforces.

``pro_until`` is NULL for an unlimited grant (that is what ``user_pro = 1``
alone has always meant), and a unix timestamp for a time-boxed one.

The ``users`` table itself is owned by the bot (``StatsMiddleware.init_db``),
but a fresh database may have the API start first; since a migration is
recorded as applied exactly once, skipping the columns then would leave them
missing forever. So the baseline table is created here when absent — the same
columns the bot creates, with ``IF NOT EXISTS`` so the bot's DDL stays a no-op.
"""

from src.db.migrate import add_column_if_missing

ID = "m009_admin_users"

COLUMNS: tuple[tuple[str, str], ...] = (
    ("banned", "INTEGER NOT NULL DEFAULT 0"),
    ("banned_reason", "TEXT"),
    ("last_seen_at", "INTEGER"),
    ("pro_until", "INTEGER"),
)

INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_users_banned ON users(banned)",
    "CREATE INDEX IF NOT EXISTS idx_users_last_seen_at ON users(last_seen_at)",
)


async def apply(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            date INTEGER,
            lang TEXT,
            region TEXT,
            district TEXT,
            specs TEXT,
            money INTEGER
        )
        """
    )
    for column, decl in COLUMNS:
        await add_column_if_missing(conn, "users", column, decl)
    for statement in INDEXES:
        await conn.execute(statement)
