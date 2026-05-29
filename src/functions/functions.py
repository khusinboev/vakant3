# ============================================
# src/functions/functions.py - Aiogram 3.x
# ============================================
import aiosqlite
import logging

from config import BASE_DIR
from src.functions.scraping import fetch_osonish_list

logger = logging.getLogger(__name__)


# Legacy bot spec codes mapped to current osonish field IDs.
LEGACY_SPEC_TO_OSONISH_FIELD: dict[str, int] = {
    "22,322,323,324": 47,
    "71": 41,
    "91,522,523": 64,
    "61": 7,
    "214": 41,
    "213,312": 12,
    "23,33": 42,
    "83": 36,
}


def normalize_osonish_field_id(raw_spec: str) -> int | None:
    val = (raw_spec or "").strip()
    if not val:
        return None

    if val.startswith("spec:"):
        val = val[5:]

    if val in LEGACY_SPEC_TO_OSONISH_FIELD:
        return LEGACY_SPEC_TO_OSONISH_FIELD[val]

    if val.isdigit():
        return int(val)

    return None


async def search_vakant(page: int, money: int, yurt: str, specs: str) -> tuple[list, int]:
    """Backward-compatible search entrypoint used by legacy tests and handlers."""
    field_id = normalize_osonish_field_id(specs)
    return await fetch_osonish_list(
        page=page,
        salary=money,
        soato_region=yurt,
        mmk_group_field_id=field_id,
    )


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

