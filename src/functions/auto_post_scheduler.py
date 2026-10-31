"""
Auto-post scheduler — multi-session daily poster.

Har kuni N ta (per_day_min–per_day_max) random vaqtda kanal uchun vakansiya yuboradi.
- Jadval auto_post_scheduled_times_json (webapp_admin_settings) da saqlanadi,
  qaysi kunga tegishli ekani esa auto_post_scheduled_day da.
- Bir marta yuborilgan vakansiya qayta yuborilmaydi (posted_vacancies — 30 kun).
- Kanal posti tili webapp_admin_settings.channel_lang bilan boshqariladi.

Candidates come from the vacancy store (``src/ingest/``, osonish + hh mixed):
open canonical rows published in the last ``FRESH_SECONDS``, with a salary
(at least ``auto_post_min_salary`` when set), a named employer and
``quality_score >= autopost_min_quality``; never a uid or a duplicate group
already posted to the channel; never a third post in a row from one
employer; the source alternates when both have candidates. When the store has
nothing fresh at all (ingestion off or stalled) the old ``vacancy_cache`` path
(live osonish list + detail) takes over so posting never stops.
"""
import asyncio
import json
import logging
import random
import time

import aiosqlite

from config import bot
from src.core.timeutil import day_key, now_tz, today_start_ts
from src.db.connection import connect
from src.db.settings import get_admin_settings, invalidate_settings_cache
from src.functions.bot_jobs import register_job
from src.functions.scraping import fetch_osonish_detail, fetch_osonish_list
from src.buttons.buttuns import channel_vacancy_kb
from src.functions.vacancy_format import format_vacancy_message_html, vacancy_apply_url, vacancy_deeplink
from src.i18n import DEFAULT_LANG, normalize_lang
from src.ingest import repo as store

logger = logging.getLogger(__name__)

DEDUP_WINDOW = 30 * 86400   # 30 days
CACHE_TTL = 4 * 3600        # 4 hours in vacancy_cache
WORK_HOUR_START = 9
WORK_HOUR_END = 22
STALE_SLOT_SECONDS = 2 * 3600   # 2 soatdan eski slot yuborilmaydi
DETAIL_CONCURRENCY = 4
TICK_SECONDS = 30
#: Store candidates must be published within this window (newest first).
FRESH_SECONDS = 48 * 3600
#: Default of ``webapp_admin_settings.autopost_min_quality`` (m024).
DEFAULT_MIN_QUALITY = 60
#: At most this many consecutive channel posts from one employer.
MAX_SAME_EMPLOYER_RUN = 2
STORE_CANDIDATES = 50


def _now_uzb():
    return now_tz()


def _today_start_ts() -> int:
    return today_start_ts()


def schedule_today_posts(per_day_min: int, per_day_max: int) -> list[dict]:
    """Bugun uchun N ta random vaqt ro'yxatini yaratadi (Toshkent, 09-22 orasida)."""
    count = random.randint(max(1, per_day_min), max(1, per_day_max))
    now_uzb = _now_uzb()
    now_ts = int(now_uzb.timestamp())

    times: set[int] = set()
    attempts = 0
    while len(times) < count and attempts < 200:
        h = random.randint(WORK_HOUR_START, WORK_HOUR_END - 1)
        m = random.randint(0, 59)
        t = now_uzb.replace(hour=h, minute=m, second=0, microsecond=0)
        ts = int(t.timestamp())
        if ts > now_ts:
            times.add(ts)
        attempts += 1

    return [{"ts": ts, "done": False, "uid": None} for ts in sorted(times)]


async def _fetch_details(vacancies) -> list[tuple[str, dict]]:
    """Detallarni parallel (semafor bilan) oladi — DB tranzaksiyasidan tashqarida."""
    semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)

    async def one(vac):
        try:
            raw_id = int(vac.uid.split("_", 1)[1])
        except (IndexError, ValueError):
            return None
        async with semaphore:
            detail = await fetch_osonish_detail(raw_id)
        return (vac.uid, detail) if isinstance(detail, dict) else None

    results = await asyncio.gather(*(one(v) for v in vacancies), return_exceptions=True)
    pairs: list[tuple[str, dict]] = []
    for item in results:
        if isinstance(item, tuple):
            pairs.append(item)
        elif isinstance(item, BaseException):
            logger.debug("auto_post: detail olishda xato: %s", item)
    return pairs


async def _refresh_vacancy_cache(conn: aiosqlite.Connection, min_salary: int) -> None:
    """API dan vakansiyalar olib, vacancy_cache ga yozadi (avval fetch, keyin yozuv)."""
    try:
        vacancies, _ = await fetch_osonish_list(
            page=1,
            salary=min_salary,
            soato_region="",
            soato_district="",
            mmk_group_field_id=None,
            sort_key="",
            sort_type="",
            search="",
        )
        if not vacancies:
            return

        pairs = await _fetch_details(vacancies[:50])
        if not pairs:
            return

        expires_at = int(time.time()) + CACHE_TTL
        await conn.executemany(
            "INSERT OR REPLACE INTO vacancy_cache (uid, data_json, expires_at) VALUES (?, ?, ?)",
            [(uid, json.dumps(detail), expires_at) for uid, detail in pairs],
        )
        await conn.commit()
        logger.debug("auto_post: vacancy_cache refreshed (%d vacancies)", len(pairs))
    except Exception as exc:
        logger.warning("auto_post: cache refresh error: %s", exc)


def _max_salary_of(data: dict) -> int:
    try:
        return int(data.get("salary_max") or data.get("max_salary") or 0)
    except (TypeError, ValueError):
        return 0


async def _pick_unposted_vacancy(
    conn: aiosqlite.Connection, channel: str, min_salary: int
) -> tuple[str, dict] | None:
    """vacancy_cache dan 30 kun ichida kanalga yuborilmagan vakansiya tanlaydi."""
    cutoff = int(time.time()) - DEDUP_WINDOW
    cursor = await conn.execute(
        """
        SELECT vc.uid, vc.data_json
        FROM vacancy_cache vc
        LEFT JOIN posted_vacancies pv
               ON vc.uid = pv.vacancy_uid AND pv.channel = ? AND pv.posted_at > ?
        WHERE pv.vacancy_uid IS NULL
          AND vc.expires_at > ?
        ORDER BY RANDOM()
        LIMIT 20
        """,
        (channel, cutoff, int(time.time())),
    )
    rows = await cursor.fetchall()
    for row in rows:
        uid = str(row[0])
        try:
            data = json.loads(row[1])
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        # Maosh ko'rsatilmagan vakansiya ham pol talabidan o'tmaydi.
        if min_salary > 0 and _max_salary_of(data) < min_salary:
            continue
        return uid, data
    return None


async def _store_has_fresh(conn: aiosqlite.Connection, now_ts: int) -> bool:
    """True when the store holds any open vacancy published within ``FRESH_SECONDS``."""
    if not await store.has_open(conn):
        return False
    cursor = await conn.execute(
        "SELECT 1 FROM vacancies WHERE status = 'open' AND published_at >= ? LIMIT 1",
        (now_ts - FRESH_SECONDS,),
    )
    return await cursor.fetchone() is not None


async def _recent_posts(conn: aiosqlite.Connection, channel: str, limit: int) -> list[dict]:
    """Latest posts to ``channel`` with the store's employer key and source (newest first)."""
    cursor = await conn.execute(
        """SELECT p.vacancy_uid, v.employer_key, v.source
           FROM posted_vacancies p LEFT JOIN vacancies v ON v.uid = p.vacancy_uid
           WHERE p.channel = ? ORDER BY p.posted_at DESC, p.rowid DESC LIMIT ?""",
        (channel, limit),
    )
    out = []
    for row in await cursor.fetchall():
        uid = str(row[0] or "")
        out.append({"uid": uid, "employer_key": row[1] or "", "source": row[2] or uid.split("_", 1)[0]})
    return out


async def _candidate_keys(conn: aiosqlite.Connection, uids: list[str], channel: str) -> dict[str, dict]:
    """uid -> {employer_key, group_posted} for the candidates (one query each)."""
    if not uids:
        return {}
    marks = ",".join("?" * len(uids))
    cursor = await conn.execute(
        f"""SELECT v.uid, v.employer_key,
                   EXISTS (SELECT 1 FROM posted_vacancies p JOIN vacancies d ON d.uid = p.vacancy_uid
                           WHERE p.channel = ? AND v.dedup_group IS NOT NULL
                             AND d.dedup_group = v.dedup_group) AS group_posted
            FROM vacancies v WHERE v.uid IN ({marks})""",
        (channel, *uids),
    )
    return {
        str(row[0]): {"employer_key": row[1] or "", "group_posted": bool(row[2])}
        for row in await cursor.fetchall()
    }


async def _pick_from_store(
    conn: aiosqlite.Connection, channel: str, min_salary: int, min_quality: int
) -> tuple[str, dict] | None:
    """The best fresh store vacancy for ``channel`` (rules in the module docstring)."""
    now_ts = int(time.time())
    candidates = await store.freshest_for_post(
        conn,
        since=now_ts - FRESH_SECONDS,
        min_quality=min_quality,
        min_salary=min_salary,
        exclude_posted=True,
        channel=channel,
        limit=STORE_CANDIDATES,
        require_salary=True,
        require_employer=True,
    )
    if not candidates:
        return None
    keys = await _candidate_keys(conn, [c["uid"] for c in candidates], channel)
    recent = await _recent_posts(conn, channel, MAX_SAME_EMPLOYER_RUN)
    run_employers = {r["employer_key"] for r in recent}
    blocked_employer = (
        next(iter(run_employers))
        if len(recent) == MAX_SAME_EMPLOYER_RUN and len(run_employers) == 1 and "" not in run_employers
        else None
    )

    eligible = []
    for cand in candidates:
        info = keys.get(cand["uid"], {})
        if info.get("group_posted"):
            continue
        if blocked_employer and info.get("employer_key") == blocked_employer:
            continue
        eligible.append(cand)
    if not eligible:
        return None

    last_source = recent[0]["source"] if recent else None
    other = next((c for c in eligible if last_source and c["source"] != last_source), None)
    chosen = other or eligible[0]
    return chosen["uid"], chosen


async def _store_row(conn: aiosqlite.Connection, uid: str) -> dict | None:
    """An open store vacancy by uid (with the source payload), else ``None``."""
    if not await store.has_open(conn):
        return None
    row = await store.get(conn, uid, with_raw=True)
    return row if row is not None and row.get("status") == "open" else None


async def _log_attempt(
    conn: aiosqlite.Connection,
    *,
    uid: str | None,
    channel: str,
    message_id: int | None,
    status: str,
    error: str | None,
) -> None:
    """Every post attempt (scheduled tick or admin "post now") gets one row here."""
    await conn.execute(
        "INSERT INTO auto_post_log (uid, channel, message_id, status, error, posted_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (uid, channel, message_id, status, error, int(time.time())),
    )
    await conn.commit()


async def _get_or_fetch_vacancy(conn: aiosqlite.Connection, uid: str) -> dict | None:
    """The store, then ``vacancy_cache``, then a live osonish.uz detail fetch (used by "post now")."""
    row = await _store_row(conn, uid)
    if row is not None:
        return row
    cursor = await conn.execute(
        "SELECT data_json FROM vacancy_cache WHERE uid = ?", (uid,)
    )
    row = await cursor.fetchone()
    if row is not None:
        try:
            data = json.loads(row[0])
        except Exception:
            data = None
        if isinstance(data, dict):
            return data

    try:
        raw_id = int(uid.split("_", 1)[1])
    except (IndexError, ValueError):
        return None
    detail = await fetch_osonish_detail(raw_id)
    return detail if isinstance(detail, dict) else None


async def pick_and_post(
    conn: aiosqlite.Connection,
    *,
    channel: str,
    min_salary: int,
    lang: str,
    uid: str | None = None,
    min_quality: int = DEFAULT_MIN_QUALITY,
    use_store: bool | None = None,
) -> dict:
    """Pick (or use the given) vacancy, send it to ``channel``, log the attempt.

    Never raises: every outcome — sent, skipped (nothing to post) or failed
    (send error) — is written to ``auto_post_log`` before returning. Shared by
    the scheduler tick and the ``auto_post.post_now`` bot job.

    ``use_store`` picks from the vacancy store, ``False`` from ``vacancy_cache``
    as before; ``None`` (default) uses the store whenever it has anything fresh.

    Returns ``{"status": "sent"|"skipped"|"failed", "uid", "message_id", "error"}``.
    """
    now_ts = int(time.time())

    if uid:
        data = await _get_or_fetch_vacancy(conn, uid)
        pick = (uid, data) if isinstance(data, dict) else None
    elif use_store or (use_store is None and await _store_has_fresh(conn, now_ts)):
        pick = await _pick_from_store(conn, channel, min_salary, min_quality)
    else:
        pick = await _pick_unposted_vacancy(conn, channel, min_salary)

    if pick is None:
        await _log_attempt(
            conn, uid=uid, channel=channel, message_id=None, status="skipped", error="no_vacancy"
        )
        return {"status": "skipped", "uid": uid, "message_id": None, "error": "no_vacancy"}

    picked_uid, data = pick
    try:
        # Channel post: plain emoji only (custom emoji need a Fragment username there).
        text = format_vacancy_message_html(picked_uid, data, lang, plain=True)
        # One neutral "Apply" button to the vacancy page for every source (the source is never named).
        apply_url = vacancy_apply_url(picked_uid, data)
        message = await bot.send_message(
            chat_id=channel,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=channel_vacancy_kb(lang, vacancy_deeplink(picked_uid), apply_url),
        )
        try:
            message_id = int(getattr(message, "message_id", None))
        except (TypeError, ValueError):
            message_id = None  # unit tests stub `bot` with a generic mock
        await conn.execute(
            "INSERT OR REPLACE INTO posted_vacancies (vacancy_uid, channel, posted_at) "
            "VALUES (?, ?, ?)",
            (picked_uid, channel, now_ts),
        )
        await _log_attempt(
            conn, uid=picked_uid, channel=channel, message_id=message_id, status="sent", error=None
        )
        logger.info("auto_post: yuborildi %s → %s", picked_uid, channel)
        return {"status": "sent", "uid": picked_uid, "message_id": message_id, "error": None}
    except Exception as exc:
        logger.error("auto_post: yuborishda xato %s: %s", picked_uid, exc)
        await _log_attempt(
            conn, uid=picked_uid, channel=channel, message_id=None, status="failed", error=str(exc)
        )
        return {"status": "failed", "uid": picked_uid, "message_id": None, "error": str(exc)}


@register_job("auto_post.post_now")
async def _handle_post_now(payload: dict) -> dict:
    """``bot_jobs`` handler: admin "post now" (payload ``{uid?: str}``)."""
    async with connect() as conn:
        settings = await get_admin_settings(conn, force=True)
        channel = str(settings.get("auto_post_channel") or "").strip()
        if not channel:
            raise RuntimeError("auto_post_channel sozlanmagan")
        min_salary = int(settings.get("auto_post_min_salary") or 0)
        lang = normalize_lang(settings.get("channel_lang") or DEFAULT_LANG)
        result = await pick_and_post(
            conn,
            channel=channel,
            min_salary=min_salary,
            lang=lang,
            uid=(payload or {}).get("uid") or None,
            min_quality=min_quality_of(settings),
        )

    if result["status"] != "sent":
        raise RuntimeError(result.get("error") or "vakansiya topilmadi")
    return {"message_id": result["message_id"], "uid": result["uid"]}


def min_quality_of(settings: dict) -> int:
    """``autopost_min_quality`` clamped to 0..100 (the default when absent)."""
    value = settings.get("autopost_min_quality")
    try:
        number = int(value) if value is not None else DEFAULT_MIN_QUALITY
    except (TypeError, ValueError):
        number = DEFAULT_MIN_QUALITY
    return max(0, min(100, number))


async def _save_schedule(
    conn: aiosqlite.Connection, schedule: list[dict], day: str | None = None
) -> None:
    payload = json.dumps(schedule)
    try:
        if day is None:
            await conn.execute(
                "UPDATE webapp_admin_settings SET auto_post_scheduled_times_json = ? "
                "WHERE singleton = 1",
                (payload,),
            )
        else:
            await conn.execute(
                "UPDATE webapp_admin_settings SET auto_post_scheduled_times_json = ?, "
                "auto_post_scheduled_day = ? WHERE singleton = 1",
                (payload, day),
            )
    except Exception as exc:
        # auto_post_scheduled_day ustuni hali qo'shilmagan bo'lsa.
        logger.debug("auto_post: jadvalni kun markeri bilan yozib bo'lmadi: %s", exc)
        await conn.execute(
            "UPDATE webapp_admin_settings SET auto_post_scheduled_times_json = ? "
            "WHERE singleton = 1",
            (payload,),
        )
    await conn.commit()
    invalidate_settings_cache()


async def _run_auto_post(conn: aiosqlite.Connection, settings: dict) -> None:
    enabled = bool(int(settings.get("auto_post_enabled") or 0))
    channel = str(settings.get("auto_post_channel") or "").strip()
    min_salary = int(settings.get("auto_post_min_salary") or 0)
    per_day_min = int(settings.get("auto_post_per_day_min") or 4)
    per_day_max = int(settings.get("auto_post_per_day_max") or 8)
    schedule_raw = settings.get("auto_post_scheduled_times_json") or "[]"
    scheduled_day = str(settings.get("auto_post_scheduled_day") or "")
    lang = normalize_lang(settings.get("channel_lang") or DEFAULT_LANG)

    if not enabled or not channel:
        return

    now_ts = int(time.time())
    today_start = _today_start_ts()
    today = day_key()

    try:
        schedule: list[dict] = json.loads(schedule_raw)
        if not isinstance(schedule, list):
            schedule = []
    except Exception:
        schedule = []

    # Faqat bugungi yozuvlarni qoldiramiz.
    schedule = [
        item
        for item in schedule
        if isinstance(item, dict) and int(item.get("ts", 0)) >= today_start
    ]

    # Kun almashgan bo'lsa (yoki marker yo'q) — bir marta yangi jadval quramiz.
    if scheduled_day != today:
        schedule = schedule_today_posts(per_day_min, per_day_max)
        await _save_schedule(conn, schedule, today)
        logger.info("auto_post: %d ta post rejalashtirildi (%s)", len(schedule), today)
        return

    pending = [item for item in schedule if not item.get("done")]
    if not pending:
        return

    # Juda eski slotlarni yubormasdan yopamiz (uzilishdan keyin burst bo'lmasligi uchun).
    stale_cutoff = now_ts - STALE_SLOT_SECONDS
    stale = [item for item in pending if int(item.get("ts", 0)) < stale_cutoff]
    if stale:
        for item in stale:
            item["done"] = True
            await _log_attempt(
                conn,
                uid=item.get("uid"),
                channel=channel,
                message_id=None,
                status="skipped",
                error="stale_slot",
            )
        logger.info("auto_post: %d ta eskirgan slot o'tkazib yuborildi", len(stale))
        await _save_schedule(conn, schedule)
        pending = [item for item in schedule if not item.get("done")]

    due = next(
        (item for item in pending if int(item.get("ts", 0)) <= now_ts),
        None,
    )
    if not due:
        return

    # vacancy_cache is still refreshed as before: it is the fallback pool when
    # the store has nothing fresh, and the weekly stats charts read it.
    count_cur = await conn.execute(
        "SELECT COUNT(*) FROM vacancy_cache WHERE expires_at > ?", (now_ts,)
    )
    count_row = await count_cur.fetchone()
    cached_count = int(count_row[0] if count_row else 0)
    if cached_count < 5:
        await _refresh_vacancy_cache(conn, min_salary)
    use_store = await _store_has_fresh(conn, now_ts)

    # pick_and_post never raises and always writes one auto_post_log row —
    # the slot is closed either way so a broken pick/send is not retried.
    result = await pick_and_post(
        conn,
        channel=channel,
        min_salary=min_salary,
        lang=lang,
        min_quality=min_quality_of(settings),
        use_store=use_store,
    )
    due["done"] = True
    if result["status"] == "sent":
        due["uid"] = result["uid"]
    elif result["status"] == "skipped":
        logger.warning("auto_post: mos vakansiya topilmadi, slot o'tkazib yuborildi")
    else:
        logger.error("auto_post: slot bajarilmadi: %s", result.get("error"))

    await _save_schedule(conn, schedule)


async def auto_post_loop() -> None:
    logger.info("Auto-post scheduler ishga tushdi")
    last_cleanup_day = ""

    while True:
        try:
            async with connect() as conn:
                settings = await get_admin_settings(conn, ttl=60)
                if settings:
                    await _run_auto_post(conn, settings)

                # Kunlik tozalash — 30 kundan eski yozuvlarni o'chirish
                today = day_key()
                if today != last_cleanup_day:
                    cutoff = int(time.time()) - DEDUP_WINDOW
                    await conn.execute(
                        "DELETE FROM posted_vacancies WHERE posted_at < ?", (cutoff,)
                    )
                    await conn.execute(
                        "DELETE FROM vacancy_cache WHERE expires_at < ?", (int(time.time()),)
                    )
                    await conn.commit()
                    last_cleanup_day = today
        except Exception as exc:
            logger.error("auto_post_loop xato: %s", exc)

        await asyncio.sleep(TICK_SECONDS)
