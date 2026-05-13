# ============================================
# src/middleware/middlewares.py - Aiogram 3.x
# ============================================
import pytz
import aiosqlite
import logging
import datetime
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)


def _extract_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []

    data = payload.get("data")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("regions", "cities", "districts", "fields", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


async def _seed_from_osonish_api(conn: aiosqlite.Connection):
    """regions bo'sh bo'lsa osonish API dan viloyat va tumanlarni yuklab to'ldirish."""
    from src.functions.scraping import fetch_json

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "uz-UZ,uz;q=0.9,en;q=0.8,ru;q=0.7",
        "Referer": "https://osonish.uz/vacancies",
        "X-Requested-With": "XMLHttpRequest",
    }

    logger.info("Viloyatlar Osonish API dan yuklanmoqda...")
    regions_payload = await fetch_json("https://osonish.uz/api/v1/regions", headers=headers)
    regions = _extract_list(regions_payload)
    if not regions:
        logger.error("Osonish regions API dan yuklab bo'lmadi")
        return

    region_count = 0
    district_count = 0
    for region in regions:
        soato = str(region.get("soato") or "").strip()
        name_uz = (region.get("name_uz") or region.get("title") or region.get("name") or "").strip()
        if not soato or not name_uz:
            continue

        await conn.execute(
            "INSERT OR IGNORE INTO regions (soato, name_uz) VALUES (?, ?)",
            (soato, name_uz),
        )
        region_count += 1

        cities_payload = await fetch_json(
            "https://osonish.uz/api/v1/cities",
            params={"region_soato": soato},
            headers=headers,
        )
        cities = _extract_list(cities_payload)
        for city in cities:
            city_soato = str(city.get("soato") or "").strip()
            city_name = (city.get("name_uz") or city.get("title") or city.get("name") or "").strip()
            if not city_soato or not city_name:
                continue

            await conn.execute(
                "INSERT OR IGNORE INTO districts (soato, region_soato, name_uz) VALUES (?, ?, ?)",
                (city_soato, soato, city_name),
            )
            district_count += 1

    await conn.commit()
    logger.info(
        "Osonishdan hududlar saqlandi: regions=%d districts=%d",
        region_count,
        district_count,
    )


class StatsMiddleware(BaseMiddleware):
    def __init__(self, db_path: str):
        self.db_path = db_path
        super().__init__()

    async def init_db(self):
        """Bazani yaratish va kerak bo'lsa migratsiya + seed qilish."""
        async with aiosqlite.connect(self.db_path) as conn:
            # --- O'zgarishsiz jadvallar ---
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    date INTEGER,
                    lang TEXT,
                    region TEXT,
                    district TEXT,
                    specs TEXT,
                    money INTEGER
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id TEXT PRIMARY KEY
                )
            """)

            # --- saves: fake column o'chirish (agar mavjud bo'lsa) ---
            cursor = await conn.execute("PRAGMA table_info(saves)")
            cols = [row[1] for row in await cursor.fetchall()]
            if 'fake' in cols:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS saves_new (
                        user_id INTEGER,
                        save_id INTEGER,
                        PRIMARY KEY (user_id, save_id)
                    )
                """)
                await conn.execute("""
                    INSERT OR IGNORE INTO saves_new (user_id, save_id)
                        SELECT user_id, save_id FROM saves
                """)
                await conn.execute("DROP TABLE saves")
                await conn.execute("ALTER TABLE saves_new RENAME TO saves")
                logger.info("saves.fake column migratsiya bajarildi")
            else:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS saves (
                        user_id INTEGER,
                        save_id INTEGER,
                        PRIMARY KEY (user_id, save_id)
                    )
                """)

            # --- Yangi location jadvallari ---
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS regions (
                    soato TEXT PRIMARY KEY,
                    name_uz TEXT NOT NULL
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS districts (
                    soato TEXT PRIMARY KEY,
                    region_soato TEXT NOT NULL,
                    name_uz TEXT NOT NULL
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS webapp_sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_handoff_tokens (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0,
                    expires_at INTEGER NOT NULL
                )
            """)
            await conn.commit()

            # --- Eski jadvallardan migratsiya (bir martalik) ---
            cursor = await conn.execute("SELECT COUNT(*) FROM regions")
            regions_count = (await cursor.fetchone())[0]

            if regions_count == 0:
                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='locations'"
                )
                has_locations = await cursor.fetchone()

                if has_locations:
                    await conn.execute("""
                        INSERT OR IGNORE INTO regions (soato, name_uz)
                            SELECT DISTINCT reg_ids, regions FROM locations
                            WHERE reg_ids IS NOT NULL AND reg_ids != ''
                    """)
                    await conn.execute("""
                        INSERT OR IGNORE INTO districts (soato, region_soato, name_uz)
                            SELECT DISTINCT dist_ids, reg_ids, districts FROM locations
                            WHERE dist_ids IS NOT NULL AND dist_ids != ''
                              AND reg_ids IS NOT NULL AND reg_ids != ''
                    """)
                    await conn.commit()

                    cursor = await conn.execute("SELECT COUNT(*) FROM regions")
                    migrated_count = (await cursor.fetchone())[0]

                    if migrated_count > 0:
                        await conn.execute("DROP TABLE locations")
                        cursor = await conn.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='viloyatlar'"
                        )
                        if await cursor.fetchone():
                            await conn.execute("DROP TABLE viloyatlar")
                        await conn.commit()
                        logger.info(
                            "locations → regions/districts migratsiya bajarildi (%d viloyat)",
                            migrated_count
                        )
                    else:
                        await _seed_from_osonish_api(conn)
                else:
                    await _seed_from_osonish_api(conn)

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """Har bir xabar uchun foydalanuvchini bazaga qo'shish."""
        user_id = event.from_user.id
        lang = event.from_user.language_code or 'uz'

        tz_uzbekistan = pytz.timezone("Asia/Tashkent")
        today = int(datetime.datetime.now(tz_uzbekistan).timestamp())

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT user_id FROM users WHERE user_id = ?",
                (user_id,)
            )
            result = await cursor.fetchone()

            if not result:
                await conn.execute(
                    "INSERT INTO users (user_id, date, lang) VALUES (?, ?, ?)",
                    (user_id, today, lang)
                )
                await conn.commit()

        return await handler(event, data)
