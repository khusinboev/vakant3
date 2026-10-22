"""Generic bot job queue + auto-post attempt history.

``bot_jobs`` lets the API hand work to the bot process (e.g. "post this
vacancy right now"). ``src/functions/bot_jobs.py:bot_jobs_loop`` polls it and
dispatches by ``kind`` through a ``JOB_HANDLERS`` registry.

``auto_post_log`` replaces the "failed"/"skipped" flags that used to live
forever inside ``webapp_admin_settings.auto_post_scheduled_times_json``: every
attempt (scheduled tick or admin "post now") gets one row here, so the admin
panel can page through real history instead of decoding a growing JSON blob.
``posted_vacancies`` is kept as-is for dedupe.
"""

ID = "m010_bot_jobs_autopost"


async def apply(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'queued',
            result_json TEXT,
            error TEXT,
            created_by INTEGER,
            created_at INTEGER NOT NULL,
            started_at INTEGER,
            finished_at INTEGER
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_bot_jobs_status_id ON bot_jobs (status, id)"
    )

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auto_post_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT,
            channel TEXT,
            message_id INTEGER,
            status TEXT NOT NULL CHECK (status IN ('sent', 'failed', 'skipped')),
            error TEXT,
            posted_at INTEGER NOT NULL
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_auto_post_log_posted_at ON auto_post_log (posted_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_auto_post_log_channel_posted "
        "ON auto_post_log (channel, posted_at)"
    )
