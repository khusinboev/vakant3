# ============================================================
# src/db/settings.py
# webapp_admin_settings (singleton) ni o'qish uchun TTL keshli yordamchi.
# Schedulerlar har tikda bazaga urilmasligi uchun.
# ============================================================
from __future__ import annotations

import logging
import time
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

# Bot tomonidan qo'shiladigan ustunlar: (nom, SQL tipi + default)
BOT_SETTINGS_COLUMNS: tuple[tuple[str, str], ...] = (
    ("channel_lang", "TEXT NOT NULL DEFAULT 'uz'"),
    ("auto_post_scheduled_day", "TEXT NOT NULL DEFAULT ''"),
    ("last_weekly_stats_week", "TEXT NOT NULL DEFAULT ''"),
)

_cache: dict[str, Any] | None = None
_cache_at: float = 0.0
_cache_version: int = -1


def invalidate_settings_cache() -> None:
    global _cache, _cache_at, _cache_version
    _cache = None
    _cache_at = 0.0
    _cache_version = -1


async def read_settings_version(conn: aiosqlite.Connection) -> int:
    """`webapp_admin_settings.version` — ustun/jadval bo'lmasa 0.

    API har PATCH da versiyani oshiradi; bot shu arzon SELECT orqali TTL
    tugashini kutmasdan keshni yangilaydi.
    """
    try:
        cursor = await conn.execute(
            "SELECT version FROM webapp_admin_settings WHERE singleton = 1"
        )
        row = await cursor.fetchone()
    except Exception:  # ustun hali qo'shilmagan (m005) yoki jadval yo'q
        return 0
    if row is None:
        return 0
    try:
        return int(row[0] or 0)
    except (TypeError, ValueError):
        return 0


async def ensure_settings_columns(conn: aiosqlite.Connection) -> None:
    """Bot ishlatadigan ustunlarni idempotent qo'shadi (jadval yo'q bo'lsa jim o'tadi)."""
    try:
        cursor = await conn.execute("PRAGMA table_info(webapp_admin_settings)")
        existing = {row[1] for row in await cursor.fetchall()}
    except Exception as exc:
        logger.debug("webapp_admin_settings topilmadi: %s", exc)
        return

    if not existing:
        # Jadvalni webapp yaratadi; bot uni yaratmaydi.
        return

    for name, ddl in BOT_SETTINGS_COLUMNS:
        if name in existing:
            continue
        try:
            await conn.execute(
                f"ALTER TABLE webapp_admin_settings ADD COLUMN {name} {ddl}"
            )
            await conn.commit()
            logger.info("webapp_admin_settings.%s ustuni qo'shildi", name)
        except Exception as exc:  # duplicate column / race — e'tiborsiz
            logger.debug("ALTER TABLE %s: %s", name, exc)
    invalidate_settings_cache()


async def get_admin_settings(
    conn: aiosqlite.Connection, ttl: int = 60, force: bool = False
) -> dict[str, Any]:
    """Singleton sozlamalar qatorini dict ko'rinishida qaytaradi (TTL keshlangan)."""
    global _cache, _cache_at, _cache_version

    now = time.monotonic()
    version = await read_settings_version(conn)
    if (
        not force
        and _cache is not None
        and version == _cache_version
        and (now - _cache_at) < ttl
    ):
        return dict(_cache)

    try:
        cursor = await conn.execute(
            "SELECT * FROM webapp_admin_settings WHERE singleton = 1"
        )
        row = await cursor.fetchone()
    except Exception as exc:
        logger.debug("admin settings o'qib bo'lmadi: %s", exc)
        return dict(_cache) if _cache is not None else {}

    data: dict[str, Any] = dict(row) if row is not None else {}
    _cache = data
    _cache_at = now
    try:
        _cache_version = int(data.get("version") or 0)
    except (TypeError, ValueError):
        _cache_version = version
    return dict(data)


async def set_admin_setting(
    conn: aiosqlite.Connection, column: str, value: Any
) -> None:
    """Bitta ustunni yozadi va keshni bekor qiladi. `column` ichki konstantalardan keladi."""
    allowed = {name for name, _ in BOT_SETTINGS_COLUMNS} | {
        "auto_post_scheduled_times_json",
    }
    if column not in allowed:
        raise ValueError(f"ruxsat etilmagan ustun: {column}")
    await conn.execute(
        f"UPDATE webapp_admin_settings SET {column} = ? WHERE singleton = 1",
        (value,),
    )
    invalidate_settings_cache()
