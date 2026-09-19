"""
Haftalik statistika scheduleri.

Har juma soat 10:00 (Toshkent) kanalga grafik + matn statistika yuboradi.
Yuborilgan hafta webapp_admin_settings.last_weekly_stats_week da saqlanadi,
shuning uchun qayta ishga tushirish takroriy postga olib kelmaydi.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta

import aiosqlite
from aiogram.types import BufferedInputFile

from config import bot
from src.core.timeutil import TZ, now_tz, week_key
from src.db.connection import connect
from src.db.settings import get_admin_settings, set_admin_setting
from src.functions.scraping import fetch_osonish_list
from src.functions.stats_chart import WeeklyStats, generate_weekly_stats_chart
from src.i18n import DEFAULT_LANG, normalize_lang, t

logger = logging.getLogger(__name__)

TZ_UZB = TZ

SEND_WEEKDAY = 4      # juma
SEND_HOUR = 10
SEND_MINUTE_WINDOW = 5
TICK_SECONDS = 240


# ─── Yordamchi funktsiyalar ────────────────────────────────────────────────────

def _month_name(month: int, lang: str = DEFAULT_LANG) -> str:
    return t(lang, f"month.{month}")


def _week_label(lang: str = DEFAULT_LANG) -> str:
    """Joriy haftaning boshlanish-tugash sanasini formatlaydi."""
    now = now_tz()
    monday = now - timedelta(days=now.weekday())
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return t(
            lang,
            "stats.week_range_same_month",
            d1=monday.day,
            d2=sunday.day,
            month=_month_name(sunday.month, lang),
            year=sunday.year,
        )
    return t(
        lang,
        "stats.week_range",
        d1=monday.day,
        month1=_month_name(monday.month, lang),
        d2=sunday.day,
        month2=_month_name(sunday.month, lang),
        year=sunday.year,
    )


def _week_short(dt: datetime, lang: str = DEFAULT_LANG) -> str:
    """Hafta uchun qisqa yorliq: '19-may'."""
    return t(lang, "stats.week_short", day=dt.day, month=_month_name(dt.month, lang))


def _week_start(weeks_ago: int) -> int:
    """N hafta avvalgi dushanba 00:00 (Toshkent) ni Unix timestamp sifatida qaytaradi."""
    now = now_tz()
    monday = now - timedelta(days=now.weekday(), weeks=weeks_ago)
    return int(monday.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


# ─── Ma'lumot yig'ish ──────────────────────────────────────────────────────────

async def _count(conn: aiosqlite.Connection, sql: str, *args) -> int:
    cur = await conn.execute(f"SELECT COUNT(*) {sql}", args)
    row = await cur.fetchone()
    return int(row[0] if row else 0)


async def _get_spec_distribution(conn: aiosqlite.Connection) -> tuple[list[str], list[int]]:
    """vacancy_cache.data_json dan top soha taqsimotini hisoblaydi."""
    cur = await conn.execute(
        "SELECT data_json FROM vacancy_cache WHERE expires_at > ?", (int(time.time()),)
    )
    rows = await cur.fetchall()

    counts: dict[str, int] = {}
    for row in rows:
        try:
            data = json.loads(row[0])
            grp = data.get("mmk_group") or data.get("mmk_group_field") or {}
            if isinstance(grp, dict):
                name = str(grp.get("name_uz") or grp.get("name") or "").strip()
            else:
                name = str(grp).strip()
            if name:
                counts[name] = counts.get(name, 0) + 1
        except Exception:
            continue

    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    names = [i[0] for i in sorted_items[:5]]
    vals = [i[1] for i in sorted_items[:5]]
    return names, vals


async def _get_region_distribution(conn: aiosqlite.Connection) -> tuple[list[str], list[int]]:
    """vacancy_cache.data_json dan top hudud taqsimotini hisoblaydi."""
    cur = await conn.execute(
        "SELECT data_json FROM vacancy_cache WHERE expires_at > ?", (int(time.time()),)
    )
    rows = await cur.fetchall()

    counts: dict[str, int] = {}
    for row in rows:
        try:
            data = json.loads(row[0])
            region_obj = data.get("soato_region") if isinstance(data.get("soato_region"), dict) else {}
            name = str(region_obj.get("name_uz") or region_obj.get("name") or "").strip()
            if not name:
                name = str(data.get("region_name") or "").strip()
            if name:
                counts[name] = counts.get(name, 0) + 1
        except Exception:
            continue

    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    names = [i[0] for i in sorted_items[:5]]
    vals = [i[1] for i in sorted_items[:5]]
    return names, vals


async def _get_avg_salary(conn: aiosqlite.Connection) -> int:
    """vacancy_cache dan o'rtacha max maoshni hisoblaydi."""
    cur = await conn.execute(
        "SELECT data_json FROM vacancy_cache WHERE expires_at > ?", (int(time.time()),)
    )
    rows = await cur.fetchall()

    salaries: list[int] = []
    for row in rows:
        try:
            data = json.loads(row[0])
            sal = int(data.get("max_salary") or data.get("salary_max") or 0)
            if sal > 100_000:  # so'mda, 100k dan past bo'lsa noto'g'ri
                salaries.append(sal)
        except Exception:
            continue

    return int(sum(salaries) / len(salaries)) if salaries else 0


async def _get_4week_trend(
    conn: aiosqlite.Connection, lang: str = DEFAULT_LANG
) -> tuple[list[str], list[int]]:
    """Oxirgi 4 hafta bo'yicha yangi foydalanuvchilar soni.

    Maosh trendi qaytarilmaydi: vacancy_cache 4 soatlik kesh bo'lgani uchun
    o'tgan haftalarning maosh tarixi saqlanmaydi (avval bu qator to'qib chiqarilardi).
    """
    now = now_tz()

    week_labels: list[str] = []
    users_per_week: list[int] = []

    for weeks_ago in range(3, -1, -1):
        w_start = _week_start(weeks_ago)
        w_end = _week_start(weeks_ago - 1) if weeks_ago > 0 else int(time.time()) + 1

        monday = now - timedelta(days=now.weekday(), weeks=weeks_ago)
        week_labels.append(_week_short(monday, lang))

        cur = await conn.execute(
            "SELECT COUNT(*) FROM users WHERE date >= ? AND date < ?",
            (w_start, w_end),
        )
        row = await cur.fetchone()
        users_per_week.append(int(row[0] if row else 0))

    return week_labels, users_per_week


async def _fetch_total_vacancies() -> int:
    """Osonish API dan aktiv vakansiyalar taxminiy sonini oladi."""
    try:
        _, last_page = await fetch_osonish_list(
            page=1, salary=0, soato_region="", soato_district="",
            mmk_group_field_id=None, sort_key="", sort_type="", search="",
        )
        return last_page * 10  # per_page=10
    except Exception:
        return 0


async def collect_weekly_stats(channel: str = "", lang: str = DEFAULT_LANG) -> WeeklyStats:
    """DB + API dan haftalik statistika yig'adi."""
    week_ago = int(time.time()) - 7 * 86400

    async with connect() as conn:
        new_users = await _count(conn, "FROM users WHERE date >= ?", week_ago)
        total_users = await _count(conn, "FROM users")
        pro_users = await _count(conn, "FROM users WHERE user_pro = 1")
        total_saves = await _count(conn, "FROM saves")
        new_resumes = await _count(
            conn,
            "FROM resume_events WHERE event_name = 'builder_ready' AND created_at >= ?",
            week_ago,
        )

        avg_salary = await _get_avg_salary(conn)
        top_specs, top_specs_counts = await _get_spec_distribution(conn)
        top_regions, top_region_counts = await _get_region_distribution(conn)
        weeks_labels, users_per_week = await _get_4week_trend(conn, lang)

    total_vacancies = await _fetch_total_vacancies()

    return WeeklyStats(
        week_label=_week_label(lang),
        new_users=new_users,
        total_users=total_users,
        pro_users=pro_users,
        total_saves=total_saves,
        new_resumes=new_resumes,
        total_vacancies=total_vacancies,
        avg_salary=avg_salary,
        top_specs=top_specs,
        top_specs_counts=top_specs_counts,
        top_regions=top_regions,
        top_region_counts=top_region_counts,
        weeks_labels=weeks_labels,
        users_per_week=users_per_week,
        avg_salary_per_week=[],
        channel=channel,
    )


def _fmt(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def format_stats_message(stats: WeeklyStats, lang: str = DEFAULT_LANG) -> str:
    """Telegram xabari uchun matn formatlaydi."""
    lines: list[str] = [
        t(lang, "stats.header", label=stats.week_label),
        "",
        t(lang, "stats.users"),
        t(lang, "stats.users_line", new=_fmt(stats.new_users), total=_fmt(stats.total_users)),
        t(lang, "stats.pro_line", count=_fmt(stats.pro_users)),
        "",
    ]

    if stats.total_vacancies:
        lines.append(t(lang, "stats.vacancies"))
        lines.append(t(lang, "stats.active_line", count=_fmt(stats.total_vacancies)))
        if stats.avg_salary:
            lines.append(t(lang, "stats.avg_salary_line", amount=_fmt(stats.avg_salary)))
        lines.append("")

    if stats.top_specs:
        lines.append(t(lang, "stats.top_specs"))
        for i, (name, cnt) in enumerate(zip(stats.top_specs[:3], stats.top_specs_counts[:3]), 1):
            lines.append(t(lang, "stats.top_row", i=i, name=name, count=_fmt(cnt)))
        lines.append("")

    if stats.top_regions:
        lines.append(t(lang, "stats.top_regions"))
        for i, (name, cnt) in enumerate(zip(stats.top_regions[:3], stats.top_region_counts[:3]), 1):
            lines.append(t(lang, "stats.top_row", i=i, name=name, count=_fmt(cnt)))
        lines.append("")

    misc: list[str] = []
    if stats.new_resumes:
        misc.append(t(lang, "stats.resumes", count=_fmt(stats.new_resumes)))
    if stats.total_saves:
        misc.append(t(lang, "stats.saves", count=_fmt(stats.total_saves)))
    if misc:
        lines += misc
        lines.append("")

    if stats.channel:
        lines.append(f"📈 {stats.channel}")

    return "\n".join(lines).strip()


# ─── Scheduler ────────────────────────────────────────────────────────────────

async def send_weekly_stats(channel: str, lang: str = DEFAULT_LANG) -> None:
    stats = await collect_weekly_stats(channel=channel, lang=lang)
    text = format_stats_message(stats, lang)
    chart_bytes = generate_weekly_stats_chart(stats, lang)

    if chart_bytes:
        await bot.send_photo(
            chat_id=channel,
            photo=BufferedInputFile(chart_bytes, filename="stats.png"),
            caption=text,
            parse_mode="HTML",
        )
        logger.info("weekly_stats: grafik + matn yuborildi → %s", channel)
    else:
        await bot.send_message(
            chat_id=channel, text=text, parse_mode="HTML",
            disable_web_page_preview=True,
        )
        logger.info("weekly_stats: faqat matn yuborildi → %s", channel)


async def weekly_stats_loop() -> None:
    logger.info("Haftalik statistika scheduleri ishga tushdi")

    while True:
        try:
            now = now_tz()
            if (
                now.weekday() == SEND_WEEKDAY
                and now.hour == SEND_HOUR
                and now.minute < SEND_MINUTE_WINDOW
            ):
                current_week = week_key(now)

                async with connect() as conn:
                    settings = await get_admin_settings(conn, ttl=0, force=True)
                    channel = str(settings.get("auto_post_channel") or "").strip()
                    lang = normalize_lang(settings.get("channel_lang") or DEFAULT_LANG)
                    last_week = str(settings.get("last_weekly_stats_week") or "")

                    if last_week == current_week:
                        await asyncio.sleep(TICK_SECONDS)
                        continue

                    if not channel:
                        logger.warning("weekly_stats: kanal sozlanmagan, o'tkazib yuborildi")
                        try:
                            await set_admin_setting(
                                conn, "last_weekly_stats_week", current_week
                            )
                            await conn.commit()
                        except Exception as exc:
                            logger.debug("weekly_stats: marker yozilmadi: %s", exc)
                        await asyncio.sleep(3600)
                        continue

                    await send_weekly_stats(channel, lang)

                    try:
                        await set_admin_setting(conn, "last_weekly_stats_week", current_week)
                        await conn.commit()
                    except Exception as exc:
                        logger.error("weekly_stats: marker yozilmadi: %s", exc)

                await asyncio.sleep(3600)
                continue

        except Exception as exc:
            logger.error("weekly_stats_loop xato: %s", exc)

        await asyncio.sleep(TICK_SECONDS)
