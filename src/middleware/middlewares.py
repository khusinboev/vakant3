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


async def _seed_from_api(conn: aiosqlite.Connection):
    """regions bo'sh bo'lsa API dan viloyat va tumanlarni yuklab to'ldirish."""
    from src.functions.scraping import fetch
    logger.info("Viloyatlar API dan yuklanmoqda...")
    data = await fetch("https://ishapi.mehnat.uz/api/v1/resources/regions")
    if not data or not data.get("success"):
        logger.error("Regions API dan yuklab bo'lmadi")
        return
    for r in data.get("data", []):
        soato = str(r["soato"])
        await conn.execute(
            "INSERT OR IGNORE INTO regions (soato, name_uz) VALUES (?, ?)",
            (soato, r["name_uz_ln"])
        )
        dist = await fetch(
            f"https://ishapi.mehnat.uz/api/v1/resources/districts?region_soato={soato}"
        )
        if dist and dist.get("success"):
            for d in dist.get("data", []):
                await conn.execute(
                    "INSERT OR IGNORE INTO districts (soato, region_soato, name_uz) VALUES (?, ?, ?)",
                    (str(d["soato"]), soato, d["name_uz_ln"])
                )
    await conn.commit()
    logger.info("Viloyatlar va tumanlar muvaffaqiyatli saqlandi")


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
                        await _seed_from_api(conn)
                else:
                    await _seed_from_api(conn)

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
