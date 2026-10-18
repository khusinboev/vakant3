"""``webapp_admin_settings.autopost_min_quality``: the auto-post quality floor.

The channel auto-post now picks from the vacancy store (``src/ingest/``) and
only posts rows whose ``quality_score`` (0-100, ``src/ingest/quality.py``) is
at least this value. Default 60. ``webapp/core/database.py`` adds the same
column on API startup, so whichever process meets the table first works.
"""

from src.db.migrate import add_column_if_missing

ID = "m024_autopost_min_quality"


async def apply(conn) -> None:
    cursor = await conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'webapp_admin_settings'"
    )
    if await cursor.fetchone() is not None:
        await add_column_if_missing(
            conn, "webapp_admin_settings", "autopost_min_quality", "INTEGER NOT NULL DEFAULT 60"
        )
