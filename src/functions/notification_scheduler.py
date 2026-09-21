"""
Bildirishnomalar scheduleri — har 30 daqiqada ishga tushadi.
Pro foydalanuvchilar uchun, kuniga max MAX_PER_DAY ta, deterministik random vaqtlarda.
Faqat vacancy_cache dan, user filtrlariga mos keluvchi vakansiyalar.

Vaqt mantig'i: har bir foydalanuvchi uchun bugungi kunga MAX_PER_DAY ta slot
deterministik hisoblanadi. Vaqti o'tgan slotlar soni bugun yuborilganlar sonidan
ko'p bo'lsa — yangi bildirishnoma yuboriladi.

Masshtab: bir tick ichida so'rovlar soni foydalanuvchilar soniga bog'liq emas —
nomzodlar to'plami bir marta yuklanadi, bugungi hisoblar bitta GROUP BY so'rovida
olinadi, yuborilganlar faqat vaqti kelgan foydalanuvchilar uchun bo'lak-bo'lak
o'qiladi. Yuborish cheklangan parallellik + token bucket bilan, yozuv esa
tarmoq ishi tugagach bitta qisqa tranzaksiyada (executemany) bajariladi.
"""
import asyncio
import json
import logging
import random
import time
from datetime import datetime, timedelta

import aiosqlite
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

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

# Masshtab parametrlari.
CANDIDATE_LIMIT = 200          # bir tickda parse qilinadigan vacancy_cache qatorlari
SENT_LOOKUP_CHUNK = 500        # sent_notifications uchun `user_id IN (...)` bo'lagi
MAX_CONCURRENT_SENDS = 10      # bir vaqtda ochiq Telegram so'rovlari
SEND_RATE_PER_SECOND = 20      # token bucket: sekundiga max xabar
MAX_RETRY_AFTER_SECONDS = 60   # flood wait shu qiymatdan katta bo'lsa kutilmaydi


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


# ───────────────────────────────────────────────
# Nomzodlar: bir marta yuklash, Python'da filtrlash
# ───────────────────────────────────────────────

async def _load_candidates(conn: aiosqlite.Connection) -> list[tuple[str, dict]]:
    """Tirik vacancy_cache qatorlari — bir tickda BIR marta o'qiladi va parse qilinadi."""
    cursor = await conn.execute(
        """
        SELECT uid, data_json
        FROM vacancy_cache
        WHERE expires_at > ?
        ORDER BY ROWID DESC
        LIMIT ?
        """,
        (int(time.time()), CANDIDATE_LIMIT),
    )
    rows = await cursor.fetchall()

    candidates: list[tuple[str, dict]] = []
    for row in rows:
        try:
            data = json.loads(row[1])
        except Exception:
            continue
        if isinstance(data, dict):
            candidates.append((row[0], data))
    return candidates


async def _load_sent_uids(
    conn: aiosqlite.Connection, user_ids: list[int]
) -> dict[int, set[str]]:
    """Faqat kerakli foydalanuvchilar uchun yuborilgan uid'lar (500 talik bo'laklarda)."""
    sent: dict[int, set[str]] = {uid: set() for uid in user_ids}
    for start in range(0, len(user_ids), SENT_LOOKUP_CHUNK):
        chunk = user_ids[start:start + SENT_LOOKUP_CHUNK]
        placeholders = ",".join("?" * len(chunk))
        cursor = await conn.execute(
            f"SELECT user_id, vacancy_uid FROM sent_notifications WHERE user_id IN ({placeholders})",
            tuple(chunk),
        )
        for row in await cursor.fetchall():
            sent.setdefault(int(row[0]), set()).add(row[1])
    return sent


def _matches_filters(data: dict, filters: dict) -> bool:
    region_soato = filters.get("region_soato") or filters.get("region")
    specs = filters.get("specs")
    try:
        min_salary = int(filters.get("min_salary") or 0)
    except (TypeError, ValueError):
        min_salary = 0

    if region_soato:
        vac_region = str(data.get("region_soato") or data.get("region_id") or "")
        if vac_region and vac_region != str(region_soato):
            return False

    if specs:
        vac_spec = str(data.get("specialization_id") or data.get("spec_id") or "")
        spec_val = str(specs).replace("spec:", "")
        if vac_spec and vac_spec != spec_val:
            return False

    # Maoshi ko'rsatilmagan vakansiya ham pol talabidan o'tmaydi.
    if min_salary and _max_salary_of(data) < min_salary:
        return False

    return True


def _choose_vacancy(
    candidates: list[tuple[str, dict]], filters: dict, sent_uids: set[str]
) -> tuple[str, dict] | None:
    """Oldindan parse qilingan to'plamdan foydalanuvchiga mos tasodifiy vakansiya."""
    pool = [
        (uid, data)
        for uid, data in candidates
        if uid not in sent_uids and _matches_filters(data, filters)
    ]
    if not pool:
        return None
    return random.choice(pool)


async def _pick_vacancy_for_user(
    conn: aiosqlite.Connection, user_id: int, filters: dict
) -> tuple[str, dict] | None:
    """Bitta foydalanuvchi uchun tanlov (bot deeplink/testlar uchun qulay o'ram)."""
    candidates = await _load_candidates(conn)
    sent = await _load_sent_uids(conn, [user_id])
    return _choose_vacancy(candidates, filters, sent.get(user_id, set()))


# ───────────────────────────────────────────────
# Yuborish: cheklangan parallellik + token bucket
# ───────────────────────────────────────────────

class _TokenBucket:
    """Sekundiga `rate` tadan ko'p bo'lmagan yuborish uchun oddiy token bucket."""

    def __init__(self, rate: float) -> None:
        self._rate = max(float(rate), 0.001)
        self._capacity = self._rate
        self._tokens = self._capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self._capacity, self._tokens + (now - self._updated) * self._rate
                )
                self._updated = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                wait = (1 - self._tokens) / self._rate
            await asyncio.sleep(wait)


async def _send_notification(user_id: int, lang: str, uid: str, data: dict) -> str:
    """Bitta xabar. Natija: 'sent' | 'blocked' | 'failed'. DB ga tegmaydi."""
    text = format_vacancy_message_html(uid, data, lang, compact=True)

    async def _send() -> None:
        await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    try:
        await _send()
        return "sent"
    except TelegramRetryAfter as exc:
        retry_after = getattr(exc, "retry_after", 0) or 0
        if retry_after > MAX_RETRY_AFTER_SECONDS:
            logger.warning("notification_flood_skip user_id=%s retry_after=%s", user_id, retry_after)
            return "failed"
        await asyncio.sleep(retry_after)
        try:
            await _send()
            return "sent"
        except TelegramForbiddenError:
            return "blocked"
        except Exception as retry_exc:
            logger.warning("notification_failed user_id=%s error=%s", user_id, retry_exc)
            return "failed"
    except TelegramForbiddenError:
        return "blocked"
    except Exception as exc:
        logger.warning("notification_failed user_id=%s error=%s", user_id, exc)
        return "failed"


async def _run_notifications(conn: aiosqlite.Connection) -> None:
    started = time.monotonic()
    now = _now_uzb()
    now_ts = int(now.timestamp())
    today_start = _today_start_ts()

    cursor = await conn.execute(
        """
        SELECT ns.user_id, u.pref_filters_json, u.lang
        FROM notification_settings ns
        JOIN users u ON u.user_id = ns.user_id
        WHERE ns.enabled = 1 AND u.user_pro = 1 AND u.blocked = 0
        """
    )
    rows = await cursor.fetchall()

    # 1) Slot vaqti kelmaganlar hech qanday I/O dan oldin chiqarib tashlanadi.
    due: list[tuple[int, dict, str, int]] = []
    for row in rows:
        user_id = int(row[0])
        due_count = due_slot_count(user_id, now)
        if due_count <= 0:
            continue

        try:
            filters = json.loads(row[1]) if row[1] else {}
        except Exception:
            filters = {}
        if not isinstance(filters, dict):
            filters = {}

        lang = normalize_lang(row[2] if len(row) > 2 else DEFAULT_LANG)
        due.append((user_id, filters, lang, due_count))

    if not due:
        return

    # 2) Bugungi hisoblar — har bir user uchun COUNT emas, bitta GROUP BY.
    cursor = await conn.execute(
        "SELECT user_id, COUNT(*) FROM sent_notifications WHERE sent_at >= ? GROUP BY user_id",
        (today_start,),
    )
    sent_today = {int(r[0]): int(r[1] or 0) for r in await cursor.fetchall()}

    eligible = [
        (user_id, filters, lang)
        for user_id, filters, lang, due_count in due
        if sent_today.get(user_id, 0) < MAX_PER_DAY
        and sent_today.get(user_id, 0) < due_count
    ]
    if not eligible:
        return

    # 3) Nomzodlar bir marta, yuborilganlar faqat shu foydalanuvchilar uchun.
    candidates = await _load_candidates(conn)
    if not candidates:
        return
    sent_uids = await _load_sent_uids(conn, [user_id for user_id, _, _ in eligible])

    picks: list[tuple[int, str, str, dict]] = []
    for user_id, filters, lang in eligible:
        pick = _choose_vacancy(candidates, filters, sent_uids.get(user_id, set()))
        if pick:
            picks.append((user_id, lang, pick[0], pick[1]))

    if not picks:
        return

    # 4) Yuborish: tarmoq ishi paytida hech qanday ochiq tranzaksiya yo'q.
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SENDS)
    bucket = _TokenBucket(SEND_RATE_PER_SECOND)

    async def _worker(user_id: int, lang: str, uid: str, data: dict) -> tuple[int, str, str]:
        async with semaphore:
            await bucket.acquire()
            result = await _send_notification(user_id, lang, uid, data)
        return user_id, uid, result

    results = await asyncio.gather(
        *(_worker(*pick) for pick in picks), return_exceptions=True
    )

    sent_rows: list[tuple[int, str, int]] = []
    blocked_ids: list[tuple[int]] = []
    failed = 0
    for item in results:
        if isinstance(item, BaseException):
            failed += 1
            logger.warning("notification_worker_error error=%s", item)
            continue
        user_id, uid, result = item
        if result == "sent":
            sent_rows.append((user_id, uid, now_ts))
        elif result == "blocked":
            blocked_ids.append((user_id,))
        else:
            failed += 1

    # 5) Yozuv: sendlardan keyin, bitta qisqa tranzaksiyada.
    if sent_rows or blocked_ids:
        try:
            if sent_rows:
                await conn.executemany(
                    "INSERT OR IGNORE INTO sent_notifications (user_id, vacancy_uid, sent_at) "
                    "VALUES (?, ?, ?)",
                    sent_rows,
                )
            if blocked_ids:
                await conn.executemany(
                    "UPDATE users SET blocked = 1 WHERE user_id = ? AND blocked != 1",
                    blocked_ids,
                )
            await conn.commit()
        except Exception as exc:
            logger.error("notification_persist_failed error=%s", exc)
            try:
                await conn.rollback()
            except Exception:
                pass

    logger.info(
        "notification_tick due=%s sent=%s failed=%s blocked=%s elapsed_ms=%s",
        len(picks),
        len(sent_rows),
        failed,
        len(blocked_ids),
        int((time.monotonic() - started) * 1000),
    )


async def notification_loop() -> None:
    logger.info("Notification scheduler started (interval=%ds)", CHECK_INTERVAL_SECONDS)
    while True:
        try:
            async with connect() as conn:
                await _run_notifications(conn)
        except Exception as e:
            logger.error("notification_loop_error error=%s", e)

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
