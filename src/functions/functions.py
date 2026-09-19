# ============================================
# src/functions/functions.py - Aiogram 3.x
# ============================================
import html
import logging

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.db.connection import connect
from src.i18n import DEFAULT_LANG, t

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

# "chat not found" turidagi xatolar = obuna yo'q; qolganlari tranzient.
_NOT_SUBSCRIBED_MARKERS = (
    "user not found",
    "chat not found",
    "member list is inaccessible",
    "participant_id_invalid",
)


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


def _esc(value) -> str:
    return html.escape(str(value or ""), quote=False)


class functions:
    @staticmethod
    async def check_on_start(user_id: int, bot) -> bool:
        """Kanalga obuna tekshiruvi. Tranzient xatolarda fail-open (obuna deb hisoblaydi)."""
        try:
            async with connect() as conn:
                cursor = await conn.execute("SELECT id FROM channels")
                rows = await cursor.fetchall()
        except Exception as exc:
            logger.error("check_on_start: kanallarni o'qib bo'lmadi: %s", exc)
            return True

        if not rows:
            return True

        for row in rows:
            channel_id = row[0]
            try:
                member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            except TelegramForbiddenError:
                # Bot kanaldan chiqarilgan — foydalanuvchini bloklamaymiz.
                logger.warning("check_on_start: botga kanal yopiq id=%s", channel_id)
                continue
            except TelegramBadRequest as exc:
                text = str(exc).lower()
                if any(marker in text for marker in _NOT_SUBSCRIBED_MARKERS):
                    return False
                logger.warning("check_on_start: bad request id=%s: %s", channel_id, exc)
                continue
            except Exception as exc:
                # Telegram 5xx / tarmoq — hammani obuna devoriga tashlamaymiz.
                logger.warning("check_on_start: tranzient xato id=%s: %s", channel_id, exc)
                continue

            if member.status not in ("member", "creator", "administrator"):
                return False

        return True


class panel_func:
    @staticmethod
    async def channel_add(channel_id: str):
        """Kanal qo'shish"""
        async with connect() as conn:
            try:
                await conn.execute(
                    "INSERT OR IGNORE INTO channels (id) VALUES (?)",
                    (channel_id,),
                )
                await conn.commit()
            except Exception as exc:
                logger.error("channel_add xato id=%s: %s", channel_id, exc)

    @staticmethod
    async def channel_delete(channel_id: str):
        """Kanal o'chirish"""
        async with connect() as conn:
            await conn.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
            await conn.commit()

    @staticmethod
    async def channel_list(bot, lang: str = DEFAULT_LANG) -> str:
        """Kanallar ro'yxati (HTML-safe)."""
        async with connect() as conn:
            cursor = await conn.execute("SELECT id FROM channels")
            rows = await cursor.fetchall()

        blocks: list[str] = []
        for row in rows:
            channel_id = row[0]
            try:
                chat = await bot.get_chat(chat_id=channel_id)
                blocks.append(
                    "------------------------------------------------\n"
                    + t(
                        lang,
                        "admin.channel_info",
                        username=_esc(channel_id),
                        title=_esc(chat.title),
                        chat_id=_esc(chat.id),
                        about=_esc(chat.description) or t(lang, "common.not_available"),
                    )
                )
            except Exception:
                blocks.append(
                    t(lang, "admin.channel_no_admin", username=_esc(channel_id))
                )

        return "\n".join(blocks) if blocks else t(lang, "admin.channels_none")
