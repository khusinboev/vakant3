"""Indexes the admin panel and the schedulers read by.

Tables are created in two different places (bot middleware / API init_db), so a
fresh database may not have all of them yet when this runs. Missing tables are
skipped here and picked up by ``_ensure_performance_indexes`` in
``webapp/core/database.py``, which runs on every API start.
"""

ID = "m001_indexes"

INDEXES: tuple[tuple[str, str], ...] = (
    ("users", "CREATE INDEX IF NOT EXISTS idx_users_date ON users(date)"),
    ("users", "CREATE INDEX IF NOT EXISTS idx_users_user_pro ON users(user_pro)"),
    ("users", "CREATE INDEX IF NOT EXISTS idx_users_blocked ON users(blocked)"),
    ("resume_events", "CREATE INDEX IF NOT EXISTS idx_resume_events_created ON resume_events(created_at)"),
    ("resume_exports", "CREATE INDEX IF NOT EXISTS idx_resume_exports_created ON resume_exports(created_at)"),
    (
        "notification_settings",
        "CREATE INDEX IF NOT EXISTS idx_notification_settings_enabled ON notification_settings(enabled)",
    ),
    (
        "posted_vacancies",
        "CREATE INDEX IF NOT EXISTS idx_posted_vac_channel_time ON posted_vacancies(channel, posted_at)",
    ),
    ("referral_payouts", "CREATE INDEX IF NOT EXISTS idx_referral_payouts_ts ON referral_payouts(ts)"),
    ("webapp_sessions", "CREATE INDEX IF NOT EXISTS idx_webapp_sessions_expires_at ON webapp_sessions(expires_at)"),
)


async def apply(conn) -> None:
    cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    tables = {row[0] for row in await cursor.fetchall()}
    for table, statement in INDEXES:
        if table not in tables:
            continue
        cursor = await conn.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in await cursor.fetchall()}
        needed = statement.split("(")[-1].rstrip(")").split(",")
        if not all(col.strip() in columns for col in needed):
            continue
        await conn.execute(statement)
