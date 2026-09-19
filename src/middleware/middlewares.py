# ============================================================
# src/middleware/middlewares.py - Aiogram 3.x
# Foydalanuvchini ro'yxatga oladi, referralni ushlaydi va
# handlerlarga `lang` ni uzatadi (message + callback_query).
# ============================================================
import logging
from typing import Any, Awaitable, Callable, Dict

import aiosqlite
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from src.core.timeutil import now_tz
from src.db.connection import connect
from src.db.settings import ensure_settings_columns
from src.i18n import DEFAULT_LANG, LANGS, normalize_lang

logger = logging.getLogger(__name__)

DEFAULT_REFERRAL_REWARD = 2000

# users jadvaliga bot ishlashi uchun kerak bo'lgan ustunlar (webapp ham qo'shadi).
_USER_COLUMNS: tuple[tuple[str, str], ...] = (
    ("ref_by", "INTEGER"),
    ("user_balance", "INTEGER DEFAULT 0"),
    ("user_pro", "INTEGER DEFAULT 0"),
    ("pref_filters_json", "TEXT"),
    ("blocked", "INTEGER NOT NULL DEFAULT 0"),
)


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


def parse_referrer_id(text: Any, user_id: int) -> int | None:
    """`/start ref_123` dan taklif qiluvchi ID sini ajratadi."""
    if not isinstance(text, str):
        return None
    parts = text.split()
    if len(parts) < 2 or not parts[0].startswith("/start"):
        return None
    param = parts[1]
    if not param.startswith("ref_"):
        return None
    try:
        inviter_id = int(param[4:])
    except ValueError:
        return None
    if inviter_id <= 0 or inviter_id == user_id:
        return None
    return inviter_id


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


async def ensure_user_columns(conn: aiosqlite.Connection) -> None:
    """users jadvalidagi kerakli ustunlarni idempotent qo'shadi."""
    cursor = await conn.execute("PRAGMA table_info(users)")
    existing = {row[1] for row in await cursor.fetchall()}
    for name, ddl in _USER_COLUMNS:
        if name in existing:
            continue
        try:
            await conn.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl}")
            await conn.commit()
        except Exception as exc:  # duplicate column — boshqa process qo'shib ulgurgan
            logger.debug("users.%s ALTER: %s", name, exc)


async def pay_referral_reward(
    conn: aiosqlite.Connection, user_id: int, inviter_id: int
) -> int | None:
    """Taklif mukofotini BIR MARTA to'laydi. To'langan summa yoki None qaytaradi."""
    cursor = await conn.execute("SELECT user_id FROM users WHERE user_id = ?", (inviter_id,))
    if await cursor.fetchone() is None:
        return None

    reward = DEFAULT_REFERRAL_REWARD
    try:
        cursor = await conn.execute(
            "SELECT referral_reward FROM webapp_admin_settings WHERE singleton = 1"
        )
        row = await cursor.fetchone()
        if row is not None:
            reward = int(row[0] or DEFAULT_REFERRAL_REWARD)
    except Exception:
        reward = DEFAULT_REFERRAL_REWARD

    now_ts = int(now_tz().timestamp())
    cursor = await conn.execute(
        "INSERT OR IGNORE INTO referral_payouts (user_id, inviter_id, amount, ts) "
        "VALUES (?, ?, ?, ?)",
        (user_id, inviter_id, reward, now_ts),
    )
    if cursor.rowcount == 0:
        # Allaqachon to'langan.
        return None

    await conn.execute(
        "UPDATE users SET user_balance = COALESCE(user_balance, 0) + ? WHERE user_id = ?",
        (reward, inviter_id),
    )
    await conn.commit()
    return reward


async def _notify_inviter(conn: aiosqlite.Connection, inviter_id: int, reward: int) -> None:
    from config import bot
    from src.i18n import t

    lang = DEFAULT_LANG
    try:
        cursor = await conn.execute("SELECT lang FROM users WHERE user_id = ?", (inviter_id,))
        row = await cursor.fetchone()
        if row is not None:
            lang = normalize_lang(row[0])
    except Exception:
        lang = DEFAULT_LANG

    amount = f"{reward:,}".replace(",", " ")
    try:
        await bot.send_message(
            chat_id=inviter_id,
            text=t(lang, "referral.reward_notice", reward=amount),
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.info("referral: taklif qiluvchiga xabar yuborilmadi id=%s: %s", inviter_id, exc)


class StatsMiddleware(BaseMiddleware):
    def __init__(self, db_path: str):
        self.db_path = db_path
        super().__init__()

    async def init_db(self):
        """Bazani yaratish va kerak bo'lsa migratsiya + seed qilish."""
        async with connect(self.db_path) as conn:
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
            # Referral mukofoti bir marta to'lanishi uchun.
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS referral_payouts (
                    user_id INTEGER PRIMARY KEY,
                    inviter_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    ts INTEGER NOT NULL
                )
            """)
            await conn.commit()

            await ensure_user_columns(conn)
            await ensure_settings_columns(conn)

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

    async def resolve_user(
        self, user_id: int, language_code: Any, inviter_id: int | None
    ) -> tuple[str, bool]:
        """(lang, is_new) — foydalanuvchini kerak bo'lsa yozadi va tilini qaytaradi."""
        async with connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT lang, blocked FROM users WHERE user_id = ?", (user_id,)
            )
            row = await cursor.fetchone()

            if row is None:
                lang = normalize_lang(language_code)
                today = int(now_tz().timestamp())
                try:
                    await conn.execute(
                        "INSERT OR IGNORE INTO users (user_id, date, lang, ref_by) "
                        "VALUES (?, ?, ?, ?)",
                        (user_id, today, lang, inviter_id),
                    )
                except Exception:
                    await conn.execute(
                        "INSERT OR IGNORE INTO users (user_id, date, lang) VALUES (?, ?, ?)",
                        (user_id, today, lang),
                    )
                await conn.commit()

                if inviter_id:
                    try:
                        reward = await pay_referral_reward(conn, user_id, inviter_id)
                        if reward:
                            await _notify_inviter(conn, inviter_id, reward)
                    except Exception as exc:
                        logger.error("referral to'lovida xato user_id=%s: %s", user_id, exc)
                return lang, True

            stored = row[0]
            lang = normalize_lang(stored)
            if stored not in LANGS:
                try:
                    await conn.execute(
                        "UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id)
                    )
                    await conn.commit()
                except Exception:
                    pass

            try:
                blocked = row[1]
            except (IndexError, KeyError):
                blocked = 0
            if blocked:
                try:
                    await conn.execute(
                        "UPDATE users SET blocked = 0 WHERE user_id = ?", (user_id,)
                    )
                    await conn.commit()
                except Exception:
                    pass

            return lang, False

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Har bir xabar/callback uchun foydalanuvchini bazaga qo'shish va `lang` uzatish."""
        user = getattr(event, "from_user", None)
        if user is None:
            data.setdefault("lang", DEFAULT_LANG)
            data.setdefault("is_new_user", False)
            return await handler(event, data)

        inviter_id = (
            parse_referrer_id(event.text, user.id) if isinstance(event, Message) else None
        )

        try:
            lang, is_new = await self.resolve_user(user.id, user.language_code, inviter_id)
        except Exception as exc:
            logger.error("StatsMiddleware xato user_id=%s: %s", user.id, exc)
            lang, is_new = normalize_lang(user.language_code), False

        data["lang"] = lang
        data["is_new_user"] = is_new
        return await handler(event, data)
