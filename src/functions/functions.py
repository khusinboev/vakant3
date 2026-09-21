# ============================================
# src/functions/functions.py - Aiogram 3.x
# ============================================
import html
import logging
import re
import time
from typing import NamedTuple

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

# Telegram javobi "bu user a'zo emas" degani — faqat shu holatda bloklaymiz.
_NOT_SUBSCRIBED_MARKERS = (
    "user not found",
    "participant_id_invalid",
)

# Bot kanalda admin emas / kanal yo'q — kanal o'tkazib yuboriladi (userni
# boshqa odamning xatosi uchun qulflamaymiz).
_BOT_NO_ACCESS_MARKERS = (
    "chat not found",
    "member list is inaccessible",
    "bot is not a member",
    "chat_admin_required",
    "not enough rights",
    "channel_private",
)

_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")
_LINK_HOST_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/(?P<rest>.+)$",
    re.IGNORECASE,
)


class ParsedChannel(NamedTuple):
    """Result of :func:`parse_channel_link`.

    ``kind`` is ``username`` (public @name), ``chat_id`` (numeric -100… id) or
    ``invite`` (private ``t.me/+hash`` / ``t.me/joinchat/hash`` link). Only the
    field matching ``kind`` is set.
    """

    kind: str
    username: str | None = None
    chat_id: int | None = None
    invite_link: str | None = None

    @property
    def target(self) -> str:
        """What Telegram's ``chat_id`` parameter accepts for this channel."""
        if self.kind == "username":
            return f"@{self.username}"
        if self.kind == "chat_id":
            return str(self.chat_id)
        return ""


def parse_channel_link(raw: str) -> ParsedChannel:
    """Parse whatever an admin pasted into a channel reference.

    Accepts ``@name``, a bare ``name``, ``t.me/name`` (with or without scheme,
    ``www.``, ``/s/`` or a trailing ``/``), ``t.me/+hash``, ``t.me/joinchat/hash``
    and a numeric ``-100…`` id. Raises ``ValueError`` whose argument is a short
    machine-readable reason (``empty``, ``bad_format``).
    """
    value = str(raw or "").strip()
    if not value:
        raise ValueError("empty")

    match = _LINK_HOST_RE.match(value)
    if match:
        rest = match.group("rest").split("?", 1)[0].split("#", 1)[0].strip("/")
        if not rest:
            raise ValueError("bad_format")
        if rest.startswith("+") or rest.lower().startswith("joinchat/"):
            normalized = value if value.lower().startswith("http") else f"https://{value.lstrip('/')}"
            return ParsedChannel(kind="invite", invite_link=normalized)
        if rest.lower().startswith("s/"):
            rest = rest[2:]
        rest = rest.split("/", 1)[0]
        if not _USERNAME_RE.match(rest):
            raise ValueError("bad_format")
        return ParsedChannel(kind="username", username=rest)

    if value.startswith("+"):
        raise ValueError("bad_format")

    lowered = value.lstrip("@")
    if re.fullmatch(r"-?\d{5,20}", value):
        return ParsedChannel(kind="chat_id", chat_id=int(value))
    if _USERNAME_RE.match(lowered):
        return ParsedChannel(kind="username", username=lowered)
    raise ValueError("bad_format")


def channel_row_target(row) -> str:
    """Telegram target for a ``channels`` row: numeric chat_id wins over the id.

    Legacy rows only have ``id`` (the pasted ``@NAME``); rows added from the
    admin panel also carry the resolved ``chat_id``, which keeps working after
    a channel is renamed.
    """
    try:
        chat_id = row["chat_id"]
    except (IndexError, KeyError, TypeError):
        chat_id = None
    if chat_id not in (None, ""):
        return str(chat_id)
    return str(row["id"])


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


async def load_channel_rows(conn, enabled_only: bool = True) -> list:
    """Kanallar ro'yxati (m006 dan keyingi kengaytirilgan jadval).

    Migratsiya hali ishlamagan bazada eski bir ustunli jadvalga qaytadi.
    """
    try:
        sql = "SELECT id, chat_id, title, username, invite_link, enabled FROM channels"
        if enabled_only:
            sql += " WHERE enabled = 1"
        cursor = await conn.execute(sql)
    except Exception:
        cursor = await conn.execute("SELECT id FROM channels")
    return list(await cursor.fetchall())


class functions:
    @staticmethod
    async def check_on_start(user_id: int, bot) -> bool:
        """Kanalga obuna tekshiruvi. Tranzient xatolarda fail-open (obuna deb hisoblaydi)."""
        try:
            async with connect() as conn:
                rows = await load_channel_rows(conn)
        except Exception as exc:
            logger.error("check_on_start: kanallarni o'qib bo'lmadi: %s", exc)
            return True

        if not rows:
            return True

        for row in rows:
            channel_id = channel_row_target(row)
            try:
                member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            except TelegramForbiddenError:
                # Bot kanaldan chiqarilgan — foydalanuvchini bloklamaymiz.
                logger.warning("check_on_start: botga kanal yopiq id=%s", channel_id)
                continue
            except TelegramBadRequest as exc:
                text = str(exc).lower()
                if any(marker in text for marker in _BOT_NO_ACCESS_MARKERS):
                    # Bot kanalda admin emas — bu userning aybi emas.
                    logger.warning("check_on_start: bot admin emas id=%s", channel_id)
                    continue
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
    async def channel_add(
        channel_id: str,
        *,
        title: str | None = None,
        username: str | None = None,
        invite_link: str | None = None,
        chat_id: int | None = None,
        added_by: int | None = None,
        bot_is_admin: bool | None = None,
    ):
        """Kanal qo'shish (admin panel va bot bir xil qatorni yozadi)."""
        now = int(time.time())
        async with connect() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO channels
                        (id, title, username, invite_link, chat_id, enabled,
                         added_by, added_at, last_check_ok, last_check_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title = COALESCE(excluded.title, channels.title),
                        username = COALESCE(excluded.username, channels.username),
                        invite_link = COALESCE(excluded.invite_link, channels.invite_link),
                        chat_id = COALESCE(excluded.chat_id, channels.chat_id),
                        enabled = 1,
                        last_check_ok = excluded.last_check_ok,
                        last_check_at = excluded.last_check_at
                    """,
                    (
                        channel_id,
                        title,
                        username,
                        invite_link,
                        chat_id,
                        added_by,
                        now,
                        None if bot_is_admin is None else int(bot_is_admin),
                        None if bot_is_admin is None else now,
                    ),
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
        """Kanallar ro'yxati (HTML-safe). Bazadagi metama'lumot ustun turadi."""
        async with connect() as conn:
            rows = await load_channel_rows(conn, enabled_only=False)

        blocks: list[str] = []
        for row in rows:
            channel_id = str(row["id"])
            target = channel_row_target(row)
            try:
                chat = await bot.get_chat(chat_id=target)
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
