"""
Weekly stats scheduler testlari.
"""
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest

from src.core.timeutil import TZ, week_key
from src.functions.stats_chart import WeeklyStats, generate_weekly_stats_chart
from src.functions.weekly_stats_scheduler import (
    _week_label,
    _week_short,
    _week_start,
    collect_weekly_stats,
    format_stats_message,
)

MODULE = "src.functions.weekly_stats_scheduler"
TZ_UZB = TZ


def _patch_connect(db):
    @asynccontextmanager
    async def fake_connect(*args, **kwargs):
        yield db

    return patch(f"{MODULE}.connect", fake_connect)


# ─── _week_label ─────────────────────────────────────────────────────────────

def test_week_label_returns_string():
    label = _week_label()
    assert isinstance(label, str)
    assert "–" in label


def test_week_label_contains_year():
    assert str(datetime.now(TZ_UZB).year) in _week_label()


def test_week_label_localized():
    ru = _week_label("ru")
    en = _week_label("en")
    assert ru != en
    assert any(ch.isalpha() for ch in ru)


def test_week_short_localized():
    dt = datetime(2026, 5, 19, tzinfo=TZ_UZB)
    assert _week_short(dt, "uz") == "19-may"
    assert _week_short(dt, "ru") == "19 мая"
    assert _week_short(dt, "en") == "19 May"


# ─── _week_start ─────────────────────────────────────────────────────────────

def test_week_start_returns_int():
    assert isinstance(_week_start(0), int)


def test_week_start_monday():
    dt = datetime.fromtimestamp(_week_start(0), tz=TZ_UZB)
    assert dt.weekday() == 0


def test_week_start_is_midnight():
    dt = datetime.fromtimestamp(_week_start(1), tz=TZ_UZB)
    assert (dt.hour, dt.minute, dt.second) == (0, 0, 0)


def test_week_start_order():
    assert _week_start(1) < _week_start(0)


def test_week_key_format():
    key = week_key()
    assert len(key) == 8 and "-W" in key


# ─── format_stats_message ────────────────────────────────────────────────────

def _sample_stats(**kwargs) -> WeeklyStats:
    defaults = dict(
        week_label="1–7 yanvar 2026",
        new_users=150,
        total_users=5000,
        pro_users=200,
        total_saves=1200,
        new_resumes=45,
        total_vacancies=2000,
        avg_salary=3_500_000,
        top_specs=["IT", "Savdo", "Qurilish"],
        top_specs_counts=[300, 250, 180],
        top_regions=["Toshkent", "Samarqand", "Andijon"],
        top_region_counts=[900, 150, 120],
        weeks_labels=["23-dek", "30-dek", "6-yan", "13-yan"],
        users_per_week=[100, 120, 140, 150],
        avg_salary_per_week=[],
        channel="@testchannel",
    )
    defaults.update(kwargs)
    return WeeklyStats(**defaults)


def test_format_stats_message_contains_week_label():
    assert "1–7 yanvar 2026" in format_stats_message(_sample_stats())


def test_format_stats_message_contains_users():
    msg = format_stats_message(_sample_stats())
    assert "+150" in msg
    assert "5 000" in msg


def test_format_stats_message_contains_pro():
    assert "200" in format_stats_message(_sample_stats())


def test_format_stats_message_contains_vacancies():
    assert "2 000" in format_stats_message(_sample_stats())


def test_format_stats_message_contains_top_specs():
    assert "IT" in format_stats_message(_sample_stats())


def test_format_stats_message_contains_top_regions():
    assert "Toshkent" in format_stats_message(_sample_stats())


def test_format_stats_message_contains_channel():
    assert "@testchannel" in format_stats_message(_sample_stats())


def test_format_stats_message_no_vacancies():
    msg = format_stats_message(_sample_stats(total_vacancies=0))
    assert "Vakansiyalar" not in msg


def test_format_stats_message_no_specs():
    msg = format_stats_message(_sample_stats(top_specs=[], top_specs_counts=[]))
    assert "Top sohalar" not in msg


def test_format_stats_message_russian():
    msg = format_stats_message(_sample_stats(), "ru")
    assert "Статистика за неделю" in msg
    assert "Пользователи" in msg


def test_format_stats_message_english():
    msg = format_stats_message(_sample_stats(), "en")
    assert "Weekly statistics" in msg
    assert "Top regions" in msg


# ─── generate_weekly_stats_chart ────────────────────────────────────────────

def test_chart_returns_bytes_or_none():
    result = generate_weekly_stats_chart(_sample_stats())
    assert result is None or isinstance(result, bytes)


def test_chart_png_header():
    pytest.importorskip("matplotlib")
    result = generate_weekly_stats_chart(_sample_stats())
    assert result is not None
    assert result[:4] == b"\x89PNG"


def test_chart_localized_renders():
    pytest.importorskip("matplotlib")
    assert generate_weekly_stats_chart(_sample_stats(), "ru") is not None


def test_chart_empty_data():
    pytest.importorskip("matplotlib")
    stats = _sample_stats(
        top_specs=[], top_specs_counts=[],
        top_regions=[], top_region_counts=[],
        weeks_labels=[], users_per_week=[],
        avg_salary_per_week=[],
    )
    assert generate_weekly_stats_chart(stats) is not None


# ─── collect_weekly_stats ────────────────────────────────────────────────────

@pytest.fixture
async def mem_db():
    async with aiosqlite.connect(":memory:") as db:
        db.row_factory = aiosqlite.Row
        await db.execute("""CREATE TABLE users (
            user_id INTEGER PRIMARY KEY, date INTEGER, lang TEXT,
            region TEXT, district TEXT, specs TEXT, money INTEGER,
            ref_by INTEGER, username TEXT, first_name TEXT, photo_url TEXT,
            user_balance INTEGER, user_pro INTEGER, pref_filters_json TEXT
        )""")
        await db.execute("CREATE TABLE saves (user_id INTEGER, save_id INTEGER)")
        await db.execute("""CREATE TABLE resume_events (
            user_id INTEGER, event_name TEXT, step TEXT,
            created_at INTEGER, meta_json TEXT
        )""")
        await db.execute("""CREATE TABLE vacancy_cache (
            uid TEXT PRIMARY KEY, data_json TEXT, expires_at INTEGER
        )""")

        now = int(time.time())
        week_ago = now - 7 * 86400

        for i in range(3):
            await db.execute(
                "INSERT INTO users VALUES (?,?,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,NULL)",
                (i + 1, now - i * 3600),
            )
        for i in range(2):
            await db.execute(
                "INSERT INTO users VALUES (?,?,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,1,NULL)",
                (100 + i, week_ago - 86400 * (i + 1)),
            )
        for i in range(5):
            await db.execute("INSERT INTO saves VALUES (?, ?)", (i + 1, 1000 + i))
        for i in range(2):
            await db.execute(
                "INSERT INTO resume_events VALUES (?,?,NULL,?,NULL)",
                (i + 1, "builder_ready", now - i * 3600),
            )
        regions = ["Toshkent", "Samarqand", "Toshkent", "Andijon"]
        for i, reg in enumerate(regions):
            data = {
                "max_salary": 3_000_000 + i * 100_000,
                "soato_region": {"name_uz": reg},
                "mmk_group": {"name_uz": "IT" if i < 2 else "Savdo"},
            }
            await db.execute(
                "INSERT INTO vacancy_cache VALUES (?,?,?)",
                (f"uid{i}", json.dumps(data), now + 3600),
            )
        await db.commit()
        yield db


@pytest.mark.asyncio
async def test_collect_weekly_stats_users(mem_db):
    with _patch_connect(mem_db), patch(
        f"{MODULE}._fetch_total_vacancies", new_callable=AsyncMock, return_value=500
    ):
        stats = await collect_weekly_stats(channel="@test")

    assert stats.total_users == 5
    assert stats.new_users == 3
    assert stats.pro_users == 2
    assert stats.total_saves == 5
    assert stats.new_resumes == 2
    assert stats.total_vacancies == 500
    assert stats.channel == "@test"


@pytest.mark.asyncio
async def test_collect_weekly_stats_regions(mem_db):
    with _patch_connect(mem_db), patch(
        f"{MODULE}._fetch_total_vacancies", new_callable=AsyncMock, return_value=0
    ):
        stats = await collect_weekly_stats()

    assert "Toshkent" in stats.top_regions
    assert len(stats.top_regions) <= 5


@pytest.mark.asyncio
async def test_collect_weekly_stats_avg_salary(mem_db):
    with _patch_connect(mem_db), patch(
        f"{MODULE}._fetch_total_vacancies", new_callable=AsyncMock, return_value=0
    ):
        stats = await collect_weekly_stats()

    assert stats.avg_salary > 0


@pytest.mark.asyncio
async def test_collect_weekly_stats_no_fabricated_salary_trend(mem_db):
    """Haftalik maosh trendi endi to'qib chiqarilmaydi."""
    with _patch_connect(mem_db), patch(
        f"{MODULE}._fetch_total_vacancies", new_callable=AsyncMock, return_value=0
    ):
        stats = await collect_weekly_stats()

    assert stats.avg_salary_per_week == []
    assert len(stats.weeks_labels) == 4
    assert len(stats.users_per_week) == 4


@pytest.mark.asyncio
async def test_collect_weekly_stats_localized_labels(mem_db):
    with _patch_connect(mem_db), patch(
        f"{MODULE}._fetch_total_vacancies", new_callable=AsyncMock, return_value=0
    ):
        stats_ru = await collect_weekly_stats(lang="ru")

    assert isinstance(stats_ru.week_label, str) and stats_ru.week_label
    # Ruscha oy nomi lotin harflarisiz bo'ladi.
    assert not any(ch in stats_ru.week_label for ch in ("yanvar", "fevral", "dekabr"))


def test_timeutil_month_arithmetic_handles_february():
    from src.core.timeutil import month_end, month_step_back

    march = datetime(2026, 3, 15, tzinfo=TZ_UZB)
    feb = month_step_back(march, 1)
    assert (feb.year, feb.month, feb.day) == (2026, 2, 1)
    assert month_end(feb).day == 28

    jan = month_step_back(march, 2)
    assert (jan.year, jan.month) == (2026, 1)
    dec = month_step_back(datetime(2026, 1, 10, tzinfo=TZ_UZB), 1)
    assert (dec.year, dec.month) == (2025, 12)
    assert month_end(dec) == datetime(2025, 12, 31, 23, 59, 59, tzinfo=TZ_UZB) + timedelta(0)
