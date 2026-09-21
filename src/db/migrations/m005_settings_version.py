"""Optimistic-concurrency version counter on the admin settings singleton.

``PATCH /api/admin/state`` bumps ``version`` in the same UPDATE that writes the
fields, so a stale editor gets 409 SETTINGS_CONFLICT instead of silently
overwriting someone else's change. The bot uses the same counter to invalidate
its 60 s settings cache.

The ``CREATE TABLE IF NOT EXISTS`` below mirrors ``webapp/core/database.py``:
migrations also run in the bot process, which never creates this table, so on a
fresh DB where the bot starts first the column would otherwise be lost. Both
statements are IF NOT EXISTS, so whichever process runs first wins and the
other is a no-op (the API then ALTERs in the few columns it adds separately).
"""

from src.db.migrate import add_column_if_missing

ID = "m005_settings_version"


async def apply(conn) -> None:
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
            pro_min_salary INTEGER NOT NULL DEFAULT 8000000,
            resume_target_creation_minutes REAL NOT NULL DEFAULT 8,
            resume_target_completion_rate REAL NOT NULL DEFAULT 60,
            resume_target_send_success_rate REAL NOT NULL DEFAULT 98,
            resume_target_export_success_rate REAL NOT NULL DEFAULT 99,
            auto_post_per_day_min INTEGER NOT NULL DEFAULT 4,
            auto_post_per_day_max INTEGER NOT NULL DEFAULT 8,
            auto_post_scheduled_times_json TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    await add_column_if_missing(conn, "webapp_admin_settings", "version", "INTEGER NOT NULL DEFAULT 0")
