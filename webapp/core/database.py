import asyncio
import logging
import os
from collections.abc import AsyncGenerator

import aiosqlite

from src.db.migrate import run_migrations
from webapp.core.config import DB_PATH
from webapp.core.errors import api_error

_log = logging.getLogger(__name__)

# --- Connection pool -------------------------------------------------------
# One aiosqlite connection per request used to be opened and closed on every
# call. Under load that is a measurable cost (file open + PRAGMA round trips)
# and it left `synchronous` at the SQLite default (FULL). The pool below keeps
# a handful of connections warm per event loop.
#
# aiosqlite connections own a background thread bound to the loop that created
# them and are NOT safe to share between concurrent tasks, so a connection is
# handed to exactly one request at a time and the pool is keyed by event loop
# (pytest gives every test its own loop).
#
# Size: several routes hold their connection across an upstream HTTP call
# (``/jobs/search`` hits osonish.uz on a cache miss), so a tiny pool would turn
# a slow upstream into 503s where the old unpooled code simply worked. WAL
# allows many concurrent readers and writers serialize anyway, so the pool is
# sized for "never the bottleneck" rather than for contention control; the
# 5 s/503 path is a safety valve, not the normal case. Tunable per deployment.
POOL_SIZE = max(1, int(os.getenv("DB_POOL_SIZE", "16")))
ACQUIRE_TIMEOUT_SECONDS = float(os.getenv("DB_POOL_TIMEOUT", "5"))
JOURNAL_SIZE_LIMIT = 64 * 1024 * 1024

CONNECTION_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
    "PRAGMA foreign_keys=ON",
    f"PRAGMA journal_size_limit={JOURNAL_SIZE_LIMIT}",
)


async def apply_pragmas(conn: aiosqlite.Connection) -> None:
    """Row factory + the standard PRAGMAs every API connection runs with."""
    conn.row_factory = aiosqlite.Row
    for pragma in CONNECTION_PRAGMAS:
        try:
            await conn.execute(pragma)
        except Exception as exc:  # pragma: no cover - read-only FS / locked DB
            _log.debug("pragma failed (%s): %s", pragma, exc)


async def open_connection(db_path=None) -> aiosqlite.Connection:
    """A standalone (unpooled) connection with the same PRAGMAs."""
    conn = await aiosqlite.connect(str(db_path or DB_PATH))
    await apply_pragmas(conn)
    return conn


class ConnectionPool:
    """Fixed-size pool of aiosqlite connections opened lazily."""

    def __init__(self, db_path, size: int = POOL_SIZE) -> None:
        self._db_path = str(db_path)
        self._size = max(1, size)
        self._idle: asyncio.Queue = asyncio.Queue()
        self._open_lock = asyncio.Lock()
        self._opened = 0
        self._closed = False

    @property
    def size(self) -> int:
        return self._size

    @property
    def opened(self) -> int:
        return self._opened

    async def acquire(self, timeout: float = ACQUIRE_TIMEOUT_SECONDS) -> aiosqlite.Connection:
        if self._closed:
            raise RuntimeError("connection pool is closed")
        try:
            return self._idle.get_nowait()
        except asyncio.QueueEmpty:
            pass

        async with self._open_lock:
            if self._opened < self._size:
                conn = await open_connection(self._db_path)
                self._opened += 1
                return conn

        try:
            return await asyncio.wait_for(self._idle.get(), timeout)
        except (asyncio.TimeoutError, TimeoutError):
            _log.warning("db pool exhausted (size=%s, waited %ss)", self._size, timeout)
            raise api_error(503, "SERVER_BUSY") from None

    async def release(self, conn: aiosqlite.Connection) -> None:
        if self._closed:
            await _close_quietly(conn)
            return
        self._idle.put_nowait(conn)

    async def discard(self, conn: aiosqlite.Connection) -> None:
        """Drop a connection that is no longer trustworthy; a new one replaces it."""
        async with self._open_lock:
            self._opened = max(0, self._opened - 1)
        await _close_quietly(conn)

    async def close(self) -> None:
        self._closed = True
        while True:
            try:
                conn = self._idle.get_nowait()
            except asyncio.QueueEmpty:
                break
            await _close_quietly(conn)
        self._opened = 0


async def _close_quietly(conn: aiosqlite.Connection) -> None:
    try:
        await conn.close()
    except Exception as exc:  # pragma: no cover
        _log.debug("closing connection failed: %s", exc)


_pools: dict[int, tuple[asyncio.AbstractEventLoop, ConnectionPool]] = {}


def _pool_for_loop() -> ConnectionPool:
    loop = asyncio.get_running_loop()
    entry = _pools.get(id(loop))
    if entry is not None and entry[0] is loop:
        return entry[1]
    pool = ConnectionPool(DB_PATH, POOL_SIZE)
    _pools[id(loop)] = (loop, pool)
    return pool


def get_pool() -> ConnectionPool:
    """The pool bound to the running event loop (created on first use)."""
    return _pool_for_loop()


async def close_pool() -> None:
    """Close every pool created in this process (called on API shutdown)."""
    loop = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        pass
    for key, (pool_loop, pool) in list(_pools.items()):
        if loop is None or pool_loop is loop:
            await pool.close()
            _pools.pop(key, None)


async def reset_pool() -> None:
    """Test helper: close and forget the pool of the running loop."""
    await close_pool()


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
    # Also added by migration m009; kept here because the auth path SELECTs it
    # (webapp/core/users.py USER_COLUMNS) and init_db runs before migrations.
    "last_seen_at": "INTEGER",
}


# (table, CREATE INDEX statement) — shared with src/db/migrations/m001_indexes.py.
REPORTING_INDEXES: tuple[tuple[str, str], ...] = (
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

    # Same set as migration m001_indexes; repeated here because a table the
    # bot owns may still be missing when the migration runs on a fresh DB.
    for table, statement in REPORTING_INDEXES:
        if table in tables:
            await conn.execute(statement)


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
        await apply_pragmas(conn)

        await _ensure_user_columns(conn)

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
        # Indexes last: by now every table this process owns exists.
        await _ensure_performance_indexes(conn)
        await conn.commit()

        applied = await run_migrations(conn)
        if applied:
            _log.info("migrations applied: %s", ", ".join(applied))


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Request-scoped pooled connection.

    A pooled connection outlives the request, so anything the handler left
    behind must be undone before it goes back: an open transaction is rolled
    back both when the handler raised and when it simply forgot to commit.
    """
    pool = get_pool()
    conn = await pool.acquire()
    broken = False
    try:
        yield conn
    except BaseException:
        broken = not await _rollback_quietly(conn)
        raise
    else:
        if conn.in_transaction:
            _log.warning("handler left an open transaction; rolling back")
            broken = not await _rollback_quietly(conn)
    finally:
        if broken:
            await pool.discard(conn)
        else:
            await pool.release(conn)


async def _rollback_quietly(conn: aiosqlite.Connection) -> bool:
    """Roll back if needed. False means the connection is no longer usable."""
    try:
        if conn.in_transaction:
            await conn.rollback()
        return True
    except Exception as exc:
        _log.warning("rollback failed, dropping connection: %s", exc)
        return False
