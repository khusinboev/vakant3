"""Entry gate: /start tracking, rich channels table, subscription cache.

The Mini App can be opened without ever pressing /start (BotFather Main App,
``t.me/<bot>/app``, ``startapp`` links), so the API needs its own copy of the
two facts the bot used to check alone: did this user start the bot, and is the
user subscribed to every required channel.

``users`` and ``channels`` are created by the bot (StatsMiddleware.init_db), but
migrations may run first on a fresh database — the two CREATE statements below
are byte-identical to the bot's so whichever process wins creates the same
table.
"""

from src.db.migrate import add_column_if_missing

ID = "m006_entry_gate"

#: Rows per back-fill statement. The whole migration runs inside one
#: ``BEGIN IMMEDIATE``, which locks the other process out of every write, so
#: the back-fill is split into statements that each finish quickly instead of
#: one UPDATE that rewrites the whole ``users`` table in a single go.
BACKFILL_CHUNK = 5000

#: (column, declaration) pairs added to the legacy one-column ``channels`` table.
CHANNEL_COLUMNS = (
    ("title", "TEXT"),
    ("username", "TEXT"),
    ("invite_link", "TEXT"),
    ("chat_id", "INTEGER"),
    ("enabled", "INTEGER NOT NULL DEFAULT 1"),
    ("added_by", "INTEGER"),
    ("added_at", "INTEGER"),
    ("last_check_ok", "INTEGER"),
    ("last_check_at", "INTEGER"),
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
    await add_column_if_missing(conn, "users", "started_at", "INTEGER")
    # One-off backfill: everyone already in the table reached it through /start.
    # Chunked so no single statement rewrites the whole table (see BACKFILL_CHUNK).
    # Idempotent by construction: it only ever touches NULL rows, so re-running
    # the migration on a database where it already ran is a no-op.
    while True:
        cursor = await conn.execute(
            "UPDATE users SET started_at = date WHERE user_id IN ("
            "    SELECT user_id FROM users WHERE started_at IS NULL AND date IS NOT NULL LIMIT ?"
            ")",
            (BACKFILL_CHUNK,),
        )
        if not cursor.rowcount:
            break
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_started_at ON users(started_at)")

    await conn.execute("CREATE TABLE IF NOT EXISTS channels (id TEXT PRIMARY KEY)")
    for column, decl in CHANNEL_COLUMNS:
        await add_column_if_missing(conn, "channels", column, decl)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_channels_enabled ON channels(enabled)")
    # A channel must not be addable twice under two spellings (@name and -100…).
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_channels_chat_id "
        "ON channels(chat_id) WHERE chat_id IS NOT NULL"
    )

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS subscription_checks (
            user_id      INTEGER PRIMARY KEY,
            checked_at   INTEGER NOT NULL,
            ok           INTEGER NOT NULL,
            missing_json TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_subscription_checks_checked_at "
        "ON subscription_checks(checked_at)"
    )
