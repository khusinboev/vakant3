import pytz
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.types import Message
import datetime
import sqlite3  # Yoki PostgreSQL/MySQL ishlatsang asyncpg yoki aiomysql
from pathlib import Path


class StatsMiddleware(BaseMiddleware):
    def __init__(self, db_path="/home/vakant2/vakant3/src/database/database.sqlite3"):
        self.db_path = db_path
        self.init_db()
        super().__init__()

    def init_db(self):
        """Bazani yaratish (faqat bir marta ishga tushiriladi)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS users ("user_id"  INTEGER,"date"  INTEGER, "lang" INTEGER, "region" INTEGER, "district" INTEGER, "money" INTEGER);""")
        conn.commit()
        cursor.execute("""CREATE TABLE IF NOT EXISTS channels ("id"  INTEGER);""")
        conn.commit()
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS locations ("regions"  INTEGER, "reg_ids"  INTEGER, "districts"  INTEGER, "dist_ids"  INTEGER, "addition"  INTEGER);""")
        conn.commit()
        conn.close()

    async def on_pre_process_message(self, message: Message, data: dict):
        """Foydalanuvchini bazaga qo'shish yoki sanani yangilash"""
        user_id = message.from_user.id
        lang = message.from_user.language_code

        # Toshkent vaqtini olish
        tz_uzbekistan = pytz.timezone("Asia/Tashkent")
        today = int(datetime.datetime.now(tz_uzbekistan).timestamp())  # UNIX timestamp (Toshkent vaqti bo‘yicha)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Foydalanuvchi bazada bor yoki yo‘qligini tekshiramiz
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result:
            pass
            # Agar foydalanuvchi bor bo‘lsa, sanasini yangilaymiz
            # cursor.execute("UPDATE users SET date = ? WHERE user_id = ?", (today, user_id))
        else:
            # Agar foydalanuvchi yangi bo‘lsa, qo‘shamiz
            cursor.execute("INSERT INTO users (user_id, date, lang) VALUES (?, ?, ?)", (user_id, today, lang))

        conn.commit()
        conn.close()
