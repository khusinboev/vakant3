"""
Auto-post scheduler testlari.
"""
import json
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest

from src.core.timeutil import TZ, day_key
from src.functions.auto_post_scheduler import (
    STALE_SLOT_SECONDS,
    _pick_unposted_vacancy,
    _run_auto_post,
    _today_start_ts,
    schedule_today_posts,
)

TZ_UZB = TZ


def _at(hour: int, minute: int = 0) -> datetime:
    """Bugungi kunning berilgan soati (Toshkent)."""
    return datetime.now(TZ_UZB).replace(hour=hour, minute=minute, second=0, microsecond=0)


# ─── schedule_today_posts ────────────────────────────────────────────────────

class TestScheduleTodayPosts:
    def test_exact_count_when_whole_day_ahead(self):
        """08:00 da butun ish kuni oldinda — aynan so'ralgan diapazonda slot bo'ladi."""
        with patch("src.functions.auto_post_scheduler._now_uzb", return_value=_at(8)):
            for _ in range(20):
                result = schedule_today_posts(2, 4)
                assert 2 <= len(result) <= 4

    def test_empty_after_working_hours(self):
        """22:30 da bugunga slot qolmaydi."""
        with patch("src.functions.auto_post_scheduler._now_uzb", return_value=_at(22, 30)):
            assert schedule_today_posts(2, 4) == []

    def test_items_have_required_keys(self):
        with patch("src.functions.auto_post_scheduler._now_uzb", return_value=_at(8)):
            result = schedule_today_posts(1, 3)
        assert result
        for item in result:
            assert item["done"] is False
            assert item["uid"] is None
            assert isinstance(item["ts"], int)

    def test_timestamps_are_future_and_sorted(self):
        now = _at(8)
        with patch("src.functions.auto_post_scheduler._now_uzb", return_value=now):
            result = schedule_today_posts(2, 5)
        ts_list = [item["ts"] for item in result]
        assert ts_list == sorted(ts_list)
        assert all(ts > int(now.timestamp()) for ts in ts_list)

    def test_timestamps_in_work_hours_uzb(self):
        with patch("src.functions.auto_post_scheduler._now_uzb", return_value=_at(8)):
            result = schedule_today_posts(3, 6)
        for item in result:
            dt = datetime.fromtimestamp(item["ts"], tz=TZ_UZB)
            assert 9 <= dt.hour <= 21


# ─── _today_start_ts ─────────────────────────────────────────────────────────

class TestTodayStartTs:
    def test_returns_int(self):
        assert isinstance(_today_start_ts(), int)

    def test_is_less_than_now(self):
        assert _today_start_ts() <= int(time.time())

    def test_within_24h(self):
        assert int(time.time()) - _today_start_ts() < 86400


# ─── Async helpers ────────────────────────────────────────────────────────────

async def _make_db():
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute(
        """CREATE TABLE vacancy_cache (
            uid TEXT PRIMARY KEY, data_json TEXT NOT NULL, expires_at INTEGER NOT NULL
        )"""
    )
    await conn.execute(
        """CREATE TABLE posted_vacancies (
            vacancy_uid TEXT NOT NULL, channel TEXT NOT NULL, posted_at INTEGER NOT NULL,
            PRIMARY KEY (vacancy_uid, channel)
        )"""
    )
    await conn.execute(
        """CREATE TABLE webapp_admin_settings (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            auto_post_enabled INTEGER NOT NULL DEFAULT 0,
            auto_post_channel TEXT NOT NULL DEFAULT '',
            auto_post_min_salary INTEGER NOT NULL DEFAULT 0,
            auto_post_per_day_min INTEGER NOT NULL DEFAULT 4,
            auto_post_per_day_max INTEGER NOT NULL DEFAULT 8,
            auto_post_scheduled_times_json TEXT NOT NULL DEFAULT '[]',
            auto_post_scheduled_day TEXT NOT NULL DEFAULT '',
            channel_lang TEXT NOT NULL DEFAULT 'uz'
        )"""
    )
    await conn.execute(
        "INSERT INTO webapp_admin_settings VALUES (1, 1, '@test_channel', 0, 2, 4, '[]', '', 'uz')"
    )
    await conn.commit()
    return conn


def _settings(**overrides) -> dict:
    base = {
        "auto_post_enabled": 1,
        "auto_post_channel": "@ch",
        "auto_post_min_salary": 0,
        "auto_post_per_day_min": 2,
        "auto_post_per_day_max": 4,
        "auto_post_scheduled_times_json": "[]",
        "auto_post_scheduled_day": "",
        "channel_lang": "uz",
    }
    base.update(overrides)
    return base


async def _stored_schedule(conn) -> list[dict]:
    cur = await conn.execute(
        "SELECT auto_post_scheduled_times_json FROM webapp_admin_settings WHERE singleton = 1"
    )
    return json.loads((await cur.fetchone())[0])


# ─── _pick_unposted_vacancy ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pick_returns_vacancy():
    conn = await _make_db()
    expires = int(time.time()) + 3600
    data = json.dumps({"title": "Python dev", "salary_max": 5000000})
    await conn.execute("INSERT INTO vacancy_cache VALUES ('uid1', ?, ?)", (data, expires))
    await conn.commit()

    result = await _pick_unposted_vacancy(conn, "@test_channel", 0)
    assert result is not None
    uid, detail = result
    assert uid == "uid1"
    assert detail["title"] == "Python dev"
    await conn.close()


@pytest.mark.asyncio
async def test_pick_skips_already_posted():
    conn = await _make_db()
    expires = int(time.time()) + 3600
    data = json.dumps({"title": "Dev", "salary_max": 5000000})
    await conn.execute("INSERT INTO vacancy_cache VALUES ('uid1', ?, ?)", (data, expires))
    await conn.execute(
        "INSERT INTO posted_vacancies VALUES ('uid1', '@test_channel', ?)", (int(time.time()),)
    )
    await conn.commit()

    assert await _pick_unposted_vacancy(conn, "@test_channel", 0) is None
    await conn.close()


@pytest.mark.asyncio
async def test_pick_skips_expired():
    conn = await _make_db()
    past = int(time.time()) - 100
    await conn.execute(
        "INSERT INTO vacancy_cache VALUES ('uid1', ?, ?)", (json.dumps({"title": "Old"}), past)
    )
    await conn.commit()

    assert await _pick_unposted_vacancy(conn, "@test_channel", 0) is None
    await conn.close()


@pytest.mark.asyncio
async def test_pick_salary_filter():
    conn = await _make_db()
    expires = int(time.time()) + 3600
    await conn.execute(
        "INSERT INTO vacancy_cache VALUES ('low', ?, ?)",
        (json.dumps({"title": "Low", "salary_max": 1_000_000}), expires),
    )
    await conn.execute(
        "INSERT INTO vacancy_cache VALUES ('high', ?, ?)",
        (json.dumps({"title": "High", "salary_max": 15_000_000}), expires),
    )
    await conn.commit()

    result = await _pick_unposted_vacancy(conn, "@test_channel", 10_000_000)
    assert result is not None
    assert result[0] == "high"
    await conn.close()


@pytest.mark.asyncio
async def test_pick_skips_vacancy_without_salary_when_floor_set():
    """Maoshi ko'rsatilmagan vakansiya maosh polidan o'tmasligi kerak."""
    conn = await _make_db()
    expires = int(time.time()) + 3600
    await conn.execute(
        "INSERT INTO vacancy_cache VALUES ('nosalary', ?, ?)",
        (json.dumps({"title": "Maoshsiz"}), expires),
    )
    await conn.commit()

    assert await _pick_unposted_vacancy(conn, "@test_channel", 5_000_000) is None
    # Pol 0 bo'lsa — o'tadi.
    assert await _pick_unposted_vacancy(conn, "@test_channel", 0) is not None
    await conn.close()


@pytest.mark.asyncio
async def test_pick_different_channel_not_blocked():
    conn = await _make_db()
    expires = int(time.time()) + 3600
    await conn.execute(
        "INSERT INTO vacancy_cache VALUES ('uid1', ?, ?)", (json.dumps({"title": "Dev"}), expires)
    )
    await conn.execute(
        "INSERT INTO posted_vacancies VALUES ('uid1', '@other_channel', ?)", (int(time.time()),)
    )
    await conn.commit()

    assert await _pick_unposted_vacancy(conn, "@test_channel", 0) is not None
    await conn.close()


# ─── _run_auto_post integration ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_creates_schedule_once_per_day():
    conn = await _make_db()
    with patch("src.functions.auto_post_scheduler._now_uzb", return_value=_at(8)):
        await _run_auto_post(conn, _settings())

    schedule = await _stored_schedule(conn)
    assert len(schedule) >= 2

    cur = await conn.execute(
        "SELECT auto_post_scheduled_day FROM webapp_admin_settings WHERE singleton = 1"
    )
    assert (await cur.fetchone())[0] == day_key()

    # Ikkinchi tik: kun o'zgarmagani uchun jadval QAYTA YARATILMAYDI
    # (slot bajarilishi mumkin, lekin vaqtlar ro'yxati o'sha-o'sha qoladi).
    with patch("src.functions.auto_post_scheduler.bot", AsyncMock()), \
         patch("src.functions.auto_post_scheduler._refresh_vacancy_cache", new_callable=AsyncMock):
        await _run_auto_post(
            conn,
            _settings(
                auto_post_scheduled_times_json=json.dumps(schedule),
                auto_post_scheduled_day=day_key(),
            ),
        )

    again = await _stored_schedule(conn)
    assert [item["ts"] for item in again] == [item["ts"] for item in schedule]
    await conn.close()


@pytest.mark.asyncio
async def test_run_skips_when_disabled():
    conn = await _make_db()
    await _run_auto_post(conn, _settings(auto_post_enabled=0))
    assert await _stored_schedule(conn) == []
    await conn.close()


@pytest.mark.asyncio
async def test_run_posts_due_vacancy():
    conn = await _make_db()
    now_ts = int(time.time())
    schedule = [{"ts": now_ts - 60, "done": False, "uid": None}]

    await conn.execute(
        "INSERT INTO vacancy_cache VALUES ('vac1', ?, ?)",
        (json.dumps({"title": "Dev", "salary_max": 0}), now_ts + 3600),
    )
    await conn.commit()

    settings = _settings(
        auto_post_scheduled_times_json=json.dumps(schedule),
        auto_post_scheduled_day=day_key(),
    )

    mock_bot = AsyncMock()
    with patch("src.functions.auto_post_scheduler.bot", mock_bot), \
         patch("src.functions.auto_post_scheduler._refresh_vacancy_cache", new_callable=AsyncMock):
        await _run_auto_post(conn, settings)

    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args.kwargs.get("chat_id") == "@ch"

    cur = await conn.execute("SELECT vacancy_uid FROM posted_vacancies WHERE channel = '@ch'")
    rows = await cur.fetchall()
    assert [row[0] for row in rows] == ["vac1"]

    stored = await _stored_schedule(conn)
    assert stored[0]["done"] is True
    assert stored[0]["uid"] == "vac1"
    await conn.close()


@pytest.mark.asyncio
async def test_run_skips_stale_slots_without_sending():
    """Uzilishdan keyin 2 soatdan eski slotlar yuborilmasdan yopiladi."""
    conn = await _make_db()
    now_ts = int(time.time())
    stale = now_ts - STALE_SLOT_SECONDS - 600
    schedule = [{"ts": stale, "done": False, "uid": None}]

    await conn.execute(
        "INSERT INTO vacancy_cache VALUES ('vac1', ?, ?)",
        (json.dumps({"title": "Dev"}), now_ts + 3600),
    )
    await conn.commit()

    mock_bot = AsyncMock()
    with patch("src.functions.auto_post_scheduler.bot", mock_bot), \
         patch("src.functions.auto_post_scheduler._refresh_vacancy_cache", new_callable=AsyncMock):
        await _run_auto_post(
            conn,
            _settings(
                auto_post_scheduled_times_json=json.dumps(schedule),
                auto_post_scheduled_day=day_key(),
            ),
        )

    mock_bot.send_message.assert_not_called()
    stored = await _stored_schedule(conn)
    assert stored[0]["done"] is True
    assert stored[0].get("skipped") is True
    await conn.close()


@pytest.mark.asyncio
async def test_run_marks_slot_done_when_send_fails():
    """Yuborish xato bersa ham slot yopiladi — 30 soniyada bir qayta urinilmaydi."""
    conn = await _make_db()
    now_ts = int(time.time())
    schedule = [{"ts": now_ts - 60, "done": False, "uid": None}]

    await conn.execute(
        "INSERT INTO vacancy_cache VALUES ('vac1', ?, ?)",
        (json.dumps({"title": "Dev"}), now_ts + 3600),
    )
    await conn.commit()

    mock_bot = AsyncMock()
    mock_bot.send_message.side_effect = RuntimeError("telegram down")
    with patch("src.functions.auto_post_scheduler.bot", mock_bot), \
         patch("src.functions.auto_post_scheduler._refresh_vacancy_cache", new_callable=AsyncMock):
        await _run_auto_post(
            conn,
            _settings(
                auto_post_scheduled_times_json=json.dumps(schedule),
                auto_post_scheduled_day=day_key(),
            ),
        )

    stored = await _stored_schedule(conn)
    assert stored[0]["done"] is True
    assert stored[0].get("failed") is True
    await conn.close()


@pytest.mark.asyncio
async def test_run_refreshes_posted_at_on_repost():
    """INSERT OR REPLACE — qayta post posted_at ni yangilaydi."""
    conn = await _make_db()
    now_ts = int(time.time())
    old_ts = now_ts - 40 * 86400  # dedup oynasidan tashqarida

    await conn.execute(
        "INSERT INTO vacancy_cache VALUES ('vac1', ?, ?)",
        (json.dumps({"title": "Dev"}), now_ts + 3600),
    )
    await conn.execute("INSERT INTO posted_vacancies VALUES ('vac1', '@ch', ?)", (old_ts,))
    await conn.commit()

    schedule = [{"ts": now_ts - 60, "done": False, "uid": None}]
    with patch("src.functions.auto_post_scheduler.bot", AsyncMock()), \
         patch("src.functions.auto_post_scheduler._refresh_vacancy_cache", new_callable=AsyncMock):
        await _run_auto_post(
            conn,
            _settings(
                auto_post_scheduled_times_json=json.dumps(schedule),
                auto_post_scheduled_day=day_key(),
            ),
        )

    cur = await conn.execute("SELECT posted_at FROM posted_vacancies WHERE vacancy_uid = 'vac1'")
    assert int((await cur.fetchone())[0]) > old_ts
    await conn.close()


@pytest.mark.asyncio
async def test_run_uses_channel_lang():
    """channel_lang = ru bo'lsa post ruscha yorliqlar bilan ketadi."""
    conn = await _make_db()
    now_ts = int(time.time())
    await conn.execute(
        "INSERT INTO vacancy_cache VALUES ('vac1', ?, ?)",
        (json.dumps({"title": "Dev", "min_salary": 1_000_000, "max_salary": 2_000_000}),
         now_ts + 3600),
    )
    await conn.commit()

    mock_bot = AsyncMock()
    with patch("src.functions.auto_post_scheduler.bot", mock_bot), \
         patch("src.functions.auto_post_scheduler._refresh_vacancy_cache", new_callable=AsyncMock):
        await _run_auto_post(
            conn,
            _settings(
                auto_post_scheduled_times_json=json.dumps(
                    [{"ts": now_ts - 60, "done": False, "uid": None}]
                ),
                auto_post_scheduled_day=day_key(),
                channel_lang="ru",
            ),
        )

    text = mock_bot.send_message.call_args.kwargs["text"]
    assert "Зарплата" in text
    await conn.close()


def test_stale_window_is_two_hours():
    assert STALE_SLOT_SECONDS == int(timedelta(hours=2).total_seconds())
