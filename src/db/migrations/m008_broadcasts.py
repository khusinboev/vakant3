"""Broadcast jobs and their per-user targets.

The bot used to hold the whole broadcast in memory: a restart lost it and the
progress lived only in the status message. Both the panel and the bot now write
a ``broadcasts`` row plus one ``broadcast_targets`` row per recipient, and a
single worker in the bot process drains them (see
``src/functions/broadcast_worker.py``).

``broadcast_targets.status`` is intentionally free-form (no CHECK): the worker
uses an extra ``sending`` state to claim a batch atomically.
"""

ID = "m008_broadcasts"


async def apply(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS broadcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('draft','queued','running','paused','cancelled','done','failed')),
            kind TEXT NOT NULL CHECK(kind IN ('text','photo','video','document','forward')),
            text TEXT,
            parse_mode TEXT DEFAULT 'HTML',
            media_path TEXT,
            media_file_id TEXT,
            forward_chat_id INTEGER,
            forward_message_id INTEGER,
            buttons_json TEXT NOT NULL DEFAULT '[]',
            target_json TEXT NOT NULL DEFAULT '{}',
            total INTEGER NOT NULL DEFAULT 0,
            sent INTEGER NOT NULL DEFAULT 0,
            failed INTEGER NOT NULL DEFAULT 0,
            blocked INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            created_at INTEGER,
            started_at INTEGER,
            finished_at INTEGER
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS broadcast_targets (
            broadcast_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            error TEXT,
            sent_at INTEGER,
            PRIMARY KEY (broadcast_id, user_id)
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_broadcast_targets_status "
        "ON broadcast_targets(broadcast_id, status)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_broadcasts_status ON broadcasts(status, id)"
    )
