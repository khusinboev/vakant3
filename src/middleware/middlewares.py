# ============================================
# src/middleware/middlewares.py - Aiogram 3.x
# ============================================
import pytz
import aiosqlite
import datetime
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message


class StatsMiddleware(BaseMiddleware):
    def __init__(self, db_path: str):
        self.db_path = db_path
        super().__init__()

    async def init_db(self):
        """Bazani yaratish"""
        async with aiosqlite.connect(self.db_path) as conn:
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
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS locations (
                    regions TEXT,
                    reg_ids TEXT,
                    districts TEXT,
                    dist_ids TEXT,
                    addition INTEGER
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS saves (
                    user_id INTEGER,
                    save_id INTEGER,
                    fake INTEGER,
                    PRIMARY KEY (user_id, save_id)
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS viloyatlar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nom TEXT,
                    my_num INTEGER
                )
            """)
            await conn.commit()

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """Har bir xabar uchun foydalanuvchini bazaga qo'shish"""
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
