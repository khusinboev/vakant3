"""Server-side error log, written by ``webapp.core.error_log.log_error``.

Sources: ``api`` (the FastAPI catch-all handler), ``bot`` (aiogram handlers),
``scheduler`` (the background loops in main.py). Retention (30 d) is added to
the maintenance sweep by the coordinator, not here.
"""

ID = "m012_error_log"


async def apply(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS error_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at   INTEGER NOT NULL,
            source       TEXT NOT NULL,
            level        TEXT NOT NULL DEFAULT 'error',
            message      TEXT NOT NULL,
            context_json TEXT
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_error_log_created_at ON error_log(created_at)"
    )
