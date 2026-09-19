import logging
from collections.abc import AsyncGenerator

import aiosqlite

from webapp.core.config import DB_PATH

_log = logging.getLogger(__name__)


def _is_duplicate_column(exc: Exception) -> bool:
    """True only for the benign 'another worker already added it' race."""
    return "duplicate column name" in str(exc).lower()

USER_EXTRA_COLUMNS = {
    "ref_by": "INTEGER",
    "username": "TEXT",
    "first_name": "TEXT",
    "photo_url": "TEXT",
    "user_balance": "INTEGER",
    "user_pro": "INTEGER",
    "pref_filters_json": "TEXT",
    "blocked": "INTEGER NOT NULL DEFAULT 0",
}


async def _ensure_performance_indexes(conn: aiosqlite.Connection) -> None:
    cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in await cursor.fetchall()}

    if "users" in tables:
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_ref_by ON users(ref_by)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_user_pro ON users(user_pro)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_blocked ON users(blocked)")

    if "saves" in tables:
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_saves_user_id_save_id ON saves(user_id, save_id)")

    if "vacancy_cache" in tables:
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_vacancy_cache_expires_at ON vacancy_cache(expires_at)")


async def _ensure_user_columns(conn: aiosqlite.Connection) -> None:
    cursor = await conn.execute("PRAGMA table_info(users)")
    existing = {row[1] for row in await cursor.fetchall()}

    for column, col_type in USER_EXTRA_COLUMNS.items():
        if column not in existing:
            try:
                await conn.execute(f"ALTER TABLE users ADD COLUMN {column} {col_type}")
            except Exception as exc:
                if not _is_duplicate_column(exc):
                    _log.error("users migration failed for column %s: %s", column, exc)


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
            CREATE TABLE IF NOT EXISTS resume_profiles (
                user_id INTEGER PRIMARY KEY,
                profile_json TEXT NOT NULL,
                selected_template TEXT NOT NULL DEFAULT 'clean',
                updated_at INTEGER NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resume_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_name TEXT NOT NULL,
                step TEXT,
                meta_json TEXT,
                created_at INTEGER NOT NULL
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_resume_events_user_created ON resume_events(user_id, created_at)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_resume_events_name_created ON resume_events(event_name, created_at)"
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resume_idempotency (
                idempotency_key TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_resume_idempotency_user_action ON resume_idempotency(user_id, action, created_at)"
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resume_exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                fmt TEXT NOT NULL,
                template_id TEXT NOT NULL,
                status TEXT NOT NULL,
                error_text TEXT,
                created_at INTEGER NOT NULL,
                completed_at INTEGER
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_resume_exports_user_created ON resume_exports(user_id, created_at)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_resume_exports_status_created ON resume_exports(status, created_at)"
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
        # Migrate existing rows — add missing columns if not present
        cursor = await conn.execute("PRAGMA table_info(webapp_admin_settings)")
        admin_cols = {row[1] for row in await cursor.fetchall()}
        for col, default, col_type in [
            ("pro_price", 10000, "INTEGER"),
            ("referral_reward", 2000, "INTEGER"),
            ("pro_min_salary", 8000000, "INTEGER"),
            ("resume_target_creation_minutes", 8, "REAL"),
            ("resume_target_completion_rate", 60, "REAL"),
            ("resume_target_send_success_rate", 98, "REAL"),
            ("resume_target_export_success_rate", 99, "REAL"),
            ("auto_post_per_day_min", 4, "INTEGER"),
            ("auto_post_per_day_max", 8, "INTEGER"),
            # Columns the bot also adds (src/db/settings.py); kept here so either process can migrate.
            ("channel_lang", "'uz'", "TEXT"),
            ("auto_post_scheduled_day", "''", "TEXT"),
            ("last_weekly_stats_week", "''", "TEXT"),
        ]:
            if col not in admin_cols:
                try:
                    await conn.execute(
                        f"ALTER TABLE webapp_admin_settings ADD COLUMN {col} {col_type} NOT NULL DEFAULT {default}"
                    )
                except Exception as exc:
                    if not _is_duplicate_column(exc):
                        _log.error("admin settings migration failed for column %s: %s", col, exc)
        if "auto_post_scheduled_times_json" not in admin_cols:
            try:
                await conn.execute(
                    "ALTER TABLE webapp_admin_settings ADD COLUMN auto_post_scheduled_times_json TEXT NOT NULL DEFAULT '[]'"
                )
            except Exception as exc:
                if not _is_duplicate_column(exc):
                    _log.error("admin settings migration failed for auto_post_scheduled_times_json: %s", exc)
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
                pro_min_salary,
                resume_target_creation_minutes,
                resume_target_completion_rate,
                resume_target_send_success_rate,
                resume_target_export_success_rate,
                auto_post_per_day_min,
                auto_post_per_day_max,
                auto_post_scheduled_times_json
            )
            VALUES (1, 0, '', 8000000, 0, 0, 0, 10000, 2000, 8000000, 8, 60, 98, 99, 4, 8, '[]')
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vacancy_cache (
                uid        TEXT PRIMARY KEY,
                data_json  TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_vacancy_cache_expires_at ON vacancy_cache(expires_at)"
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS posted_vacancies (
                vacancy_uid TEXT NOT NULL,
                channel     TEXT NOT NULL,
                posted_at   INTEGER NOT NULL,
                PRIMARY KEY (vacancy_uid, channel)
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_posted_vac_time ON posted_vacancies(posted_at)"
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_settings (
                user_id    INTEGER PRIMARY KEY,
                enabled    INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_notifications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                vacancy_uid TEXT NOT NULL,
                sent_at     INTEGER NOT NULL
            )
            """
        )
        await conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_sent_notif_unique ON sent_notifications(user_id, vacancy_uid)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sent_notif_time ON sent_notifications(user_id, sent_at)"
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
