# ============================================
# middlewares.py - ASYNC VERSION
# ============================================
import pytz
import aiosqlite
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.types import Message
import datetime


class StatsMiddleware(BaseMiddleware):
    def __init__(self, db_path):
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
                    id INTEGER PRIMARY KEY
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
            await conn.commit()

    async def on_pre_process_message(self, message: Message, data: dict):
        """Foydalanuvchini bazaga qo'shish"""
        user_id = message.from_user.id
        lang = message.from_user.language_code or 'uz'

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
                    """INSERT INTO users (user_id, date, lang) 
                       VALUES (?, ?, ?)""",
                    (user_id, today, lang)
                )
                await conn.commit()
