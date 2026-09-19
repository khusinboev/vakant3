"""
Bildirishnomalar scheduleri — har 30 daqiqada ishga tushadi.
Pro foydalanuvchilar uchun, kuniga max MAX_PER_DAY ta, deterministik random vaqtlarda.
Faqat vacancy_cache dan, user filtrlariga mos keluvchi vakansiyalar.

Vaqt mantig'i: har bir foydalanuvchi uchun bugungi kunga MAX_PER_DAY ta slot
deterministik hisoblanadi. Vaqti o'tgan slotlar soni bugun yuborilganlar sonidan
ko'p bo'lsa — yangi bildirishnoma yuboriladi.
"""
import asyncio
import json
import logging
import random
import time
from datetime import datetime, timedelta

import aiosqlite

from config import bot
from src.core.timeutil import now_tz, today_start_ts
from src.db.connection import connect
from src.functions.vacancy_format import format_vacancy_message_html
from src.i18n import DEFAULT_LANG, normalize_lang

logger = logging.getLogger(__name__)

MAX_PER_DAY = 2
WORK_HOUR_START = 9
WORK_HOUR_END = 21
CHECK_INTERVAL_SECONDS = 30 * 60  # 30 daqiqa


def _now_uzb() -> datetime:
    return now_tz()


def _today_start_ts() -> int:
    return today_start_ts()


def _slot_seed(user_id: int, day: datetime) -> int:
    return user_id * 10000 + day.year * 365 + day.timetuple().tm_yday


def _slots_for_day(user_id: int, day: datetime) -> list[int]:
    """Berilgan kun uchun MAX_PER_DAY ta deterministik slot (unix ts, o'sish tartibida)."""
    rng = random.Random(_slot_seed(user_id, day))

    hours: list[int] = []
    span = WORK_HOUR_END - WORK_HOUR_START
    while len(hours) < min(MAX_PER_DAY, span):
        hour = rng.randint(WORK_HOUR_START, WORK_HOUR_END - 1)
        if hour not in hours:
            hours.append(hour)

    slots = [
        int(day.replace(hour=hour, minute=rng.randint(0, 59), second=0, microsecond=0).timestamp())
        for hour in hours
    ]
    return sorted(slots)


def today_slots(user_id: int, now: datetime | None = None) -> list[int]:
    return _slots_for_day(user_id, now or _now_uzb())


def due_slot_count(user_id: int, now: datetime | None = None) -> int:
    """Bugun vaqti kelgan slotlar soni (0..MAX_PER_DAY)."""
    moment = now or _now_uzb()
    now_ts = int(moment.timestamp())
    return sum(1 for slot in _slots_for_day(user_id, moment) if slot <= now_ts)


def _next_notification_ts(user_id: int) -> int:
    """Keyingi slot: bugun qolgani, bo'lmasa ertangi birinchisi."""
    now = _now_uzb()
    now_ts = int(now.timestamp())
    for slot in _slots_for_day(user_id, now):
        if slot > now_ts:
            return slot
    return _slots_for_day(user_id, now + timedelta(days=1))[0]


def _max_salary_of(data: dict) -> int:
    try:
        return int(data.get("salary_max") or data.get("max_salary") or 0)
    except (TypeError, ValueError):
        return 0


async def _pick_vacancy_for_user(
    conn: aiosqlite.Connection, user_id: int, filters: dict
) -> tuple[str, dict] | None:
    """Foydalanuvchi filtrlari asosida hali yuborilmagan vakansiya tanlaydi."""
    region_soato = filters.get("region_soato") or filters.get("region")
    specs = filters.get("specs")
    min_salary = int(filters.get("min_salary") or 0)

    # Yuborilganlarni SQL darajasida chiqarib tashlaymiz (butun tarixni yuklamaymiz).
    cursor = await conn.execute(
        """
        SELECT vc.uid, vc.data_json
        FROM vacancy_cache vc
        WHERE vc.expires_at > ?
          AND NOT EXISTS (
              SELECT 1 FROM sent_notifications sn
              WHERE sn.user_id = ? AND sn.vacancy_uid = vc.uid
          )
        ORDER BY vc.ROWID DESC
        LIMIT 200
        """,
        (int(time.time()), user_id),
    )
    rows = await cursor.fetchall()

    candidates: list[tuple[str, dict]] = []
    for row in rows:
        uid = row[0]
        try:
            data = json.loads(row[1])
        except Exception:
            continue
        if not isinstance(data, dict):
            continue

        if region_soato:
            vac_region = str(data.get("region_soato") or data.get("region_id") or "")
            if vac_region and vac_region != str(region_soato):
                continue

        if specs:
            vac_spec = str(data.get("specialization_id") or data.get("spec_id") or "")
            spec_val = str(specs).replace("spec:", "")
            if vac_spec and vac_spec != spec_val:
                continue

        # Maoshi ko'rsatilmagan vakansiya ham pol talabidan o'tmaydi.
        if min_salary and _max_salary_of(data) < min_salary:
            continue

        candidates.append((uid, data))

    if not candidates:
        return None

    return random.choice(candidates)


async def _run_notifications(conn: aiosqlite.Connection) -> None:
    now = _now_uzb()
    now_ts = int(now.timestamp())
    today_start = _today_start_ts()

    cursor = await conn.execute(
        """
        SELECT ns.user_id, u.pref_filters_json, u.lang
        FROM notification_settings ns
        JOIN users u ON u.user_id = ns.user_id
        WHERE ns.enabled = 1 AND u.user_pro = 1
        """
    )
    users = await cursor.fetchall()

    for row in users:
        user_id = int(row[0])
        filters_raw = row[1]
        lang = normalize_lang(row[2] if len(row) > 2 else DEFAULT_LANG)

        try:
            filters = json.loads(filters_raw) if filters_raw else {}
        except Exception:
            filters = {}
        if not isinstance(filters, dict):
            filters = {}

        c = await conn.execute(
            "SELECT COUNT(*) FROM sent_notifications WHERE user_id = ? AND sent_at >= ?",
            (user_id, today_start),
        )
        sent_count = int((await c.fetchone())[0] or 0)
        if sent_count >= MAX_PER_DAY:
            continue

        # Vaqti kelgan slotlar soni yuborilganlardan ko'p bo'lsagina yuboramiz.
        if sent_count >= due_slot_count(user_id, now):
            continue

        pick = await _pick_vacancy_for_user(conn, user_id, filters)
        if not pick:
            continue

        uid, data = pick

        try:
            text = format_vacancy_message_html(uid, data, lang, compact=True)
            await bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            await conn.execute(
                "INSERT OR IGNORE INTO sent_notifications (user_id, vacancy_uid, sent_at) "
                "VALUES (?, ?, ?)",
                (user_id, uid, now_ts),
            )
            await conn.commit()
            logger.info("notification_sent user_id=%s uid=%s", user_id, uid)
        except Exception as e:
            logger.warning("notification_failed user_id=%s error=%s", user_id, e)


async def notification_loop() -> None:
    logger.info("Notification scheduler started (interval=%ds)", CHECK_INTERVAL_SECONDS)
    while True:
        try:
            async with connect() as conn:
                await _run_notifications(conn)
        except Exception as e:
            logger.error("notification_loop_error error=%s", e)

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
