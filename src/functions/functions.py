# ============================================
# src/functions/functions.py - Aiogram 3.x
# ============================================
import aiosqlite
import logging

from config import BASE_DIR

logger = logging.getLogger(__name__)


class functions:
    @staticmethod
    async def check_on_start(user_id: int, bot):
        """Kanalga obuna tekshiruvi"""
        async with aiosqlite.connect(BASE_DIR) as conn:
            cursor = await conn.execute("SELECT id FROM channels")
            rows = await cursor.fetchall()

        if not rows:
            return True

        for (channel_id,) in rows:
            try:
                member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                if member.status not in ["member", "creator", "administrator"]:
                    return False
            except Exception:
                return False

        return True


class panel_func:
    @staticmethod
    async def channel_add(channel_id: str):
        """Kanal qo'shish"""
        async with aiosqlite.connect(BASE_DIR) as conn:
            try:
                await conn.execute(
                    "INSERT OR IGNORE INTO channels (id) VALUES (?)",
                    (channel_id,),
                )
                await conn.commit()
            except Exception:
                pass

    @staticmethod
    async def channel_delete(channel_id: str):
        """Kanal o'chirish"""
        async with aiosqlite.connect(BASE_DIR) as conn:
            await conn.execute(
                "DELETE FROM channels WHERE id = ?",
                (channel_id,),
            )
            await conn.commit()

    @staticmethod
    async def channel_list(bot):
        """Kanallar ro'yxati"""
        async with aiosqlite.connect(BASE_DIR) as conn:
            cursor = await conn.execute("SELECT id FROM channels")
            rows = await cursor.fetchall()

        result = ""
        for row in rows:
            try:
                chat = await bot.get_chat(chat_id=row[0])
                result += (
                    "------------------------------------------------\n"
                    f"Kanal useri: {row[0]}\n"
                    f"Kanal nomi: {chat.title}\n"
                    f"Kanal ID: {chat.id}\n"
                    f"Haqida: {chat.description or 'Mavjud emas'}\n"
                )
            except Exception:
                result += f"Kanal {row[0]} - botni admin qiling\n"

        return result or "Kanallar mavjud emas"

