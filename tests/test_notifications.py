"""
Notification scheduler testlari.

`_next_notification_ts` / slot mantiqi mock qilinmaydi — vaqt `_now_uzb` ni
almashtirish orqali "muzlatiladi", shuning uchun haqiqiy xatti-harakat sinaladi.
"""
import json
import time
from datetime import datetime, timedelta

import aiosqlite
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

from src.core.timeutil import TZ
from src.functions.notification_scheduler import (
    MAX_PER_DAY,
    WORK_HOUR_END,
    WORK_HOUR_START,
    _next_notification_ts,
    _pick_vacancy_for_user,
    _run_notifications,
    _slots_for_day,
    _today_start_ts,
    due_slot_count,
    today_slots,
)

MODULE = "src.functions.notification_scheduler"


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime.now(TZ).replace(hour=hour, minute=minute, second=0, microsecond=0)


def _freeze(moment: datetime):
    return patch(f"{MODULE}._now_uzb", return_value=moment)


# ───────────────────────────────────────────────
# Slot mantiqi
# ───────────────────────────────────────────────

class TestSlots:
    def test_two_slots_per_day(self):
        assert len(today_slots(12345)) == MAX_PER_DAY

    def test_slots_are_sorted_and_distinct(self):
        slots = today_slots(4242)
        assert slots == sorted(slots)
        assert len(set(slots)) == MAX_PER_DAY

    def test_slots_within_work_hours(self):
        for user_id in (1, 77777, 99991):
            for ts in today_slots(user_id):
                dt = datetime.fromtimestamp(ts, tz=TZ)
                assert WORK_HOUR_START <= dt.hour < WORK_HOUR_END

    def test_same_user_same_day_is_deterministic(self):
        assert today_slots(42) == today_slots(42)

    def test_different_users_get_different_slots(self):
        assert today_slots(111) != today_slots(999)

    def test_due_count_grows_through_the_day(self):
        user_id = 555
        day = _at(0)
        slots = _slots_for_day(user_id, day)
        before_first = datetime.fromtimestamp(slots[0], tz=TZ) - timedelta(minutes=1)
        between = datetime.fromtimestamp(slots[0], tz=TZ) + timedelta(minutes=1)
        after_last = datetime.fromtimestamp(slots[-1], tz=TZ) + timedelta(minutes=1)

        assert due_slot_count(user_id, before_first) == 0
        assert due_slot_count(user_id, between) == 1
        assert due_slot_count(user_id, after_last) == MAX_PER_DAY


class TestNextNotificationTs:
    def test_returns_upcoming_slot_today(self):
        user_id = 12345
        with _freeze(_at(0, 1)):
            ts = _next_notification_ts(user_id)
            assert ts == today_slots(user_id)[0]

    def test_rolls_over_to_tomorrow_after_last_slot(self):
        """Kun oxirida ertangi birinchi slot qaytadi — lekin bugungi slotlar hisobga olinadi."""
        user_id = 12345
        now = _at(23, 59)
        with _freeze(now):
            ts = _next_notification_ts(user_id)
        tomorrow_first = _slots_for_day(user_id, now + timedelta(days=1))[0]
        assert ts == tomorrow_first
        assert ts > int(now.timestamp())

    def test_hour_in_work_range(self):
        ts = _next_notification_ts(77777)
        dt = datetime.fromtimestamp(ts, tz=TZ)
        assert WORK_HOUR_START <= dt.hour < WORK_HOUR_END

    def test_deterministic(self):
        with _freeze(_at(0, 1)):
            assert _next_notification_ts(42) == _next_notification_ts(42)


class TestTodayStartTs:
    def test_returns_int(self):
        assert isinstance(_today_start_ts(), int)

    def test_within_24h_of_now(self):
        diff = int(time.time()) - _today_start_ts()
        assert 0 <= diff < 86400


# ───────────────────────────────────────────────
# _pick_vacancy_for_user
# ───────────────────────────────────────────────

@pytest_asyncio.fixture
async def mem_db():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            "CREATE TABLE vacancy_cache (uid TEXT PRIMARY KEY, data_json TEXT, expires_at INTEGER)"
        )
        await conn.execute(
            """CREATE TABLE sent_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                vacancy_uid TEXT NOT NULL,
                sent_at INTEGER NOT NULL
            )"""
        )
        await conn.execute(
            "CREATE UNIQUE INDEX idx_sn ON sent_notifications(user_id, vacancy_uid)"
        )
        yield conn


@pytest.mark.asyncio
async def test_pick_returns_vacancy(mem_db):
    future = int(time.time()) + 3600
    await mem_db.execute(
        "INSERT INTO vacancy_cache VALUES (?, ?, ?)",
        ("v1", json.dumps({"title": "Dev", "salary_max": 5000000}), future),
    )
    await mem_db.commit()

    result = await _pick_vacancy_for_user(mem_db, 1, {})
    assert result is not None
    uid, data = result
    assert uid == "v1"
    assert data["title"] == "Dev"


@pytest.mark.asyncio
async def test_pick_skips_sent_vacancies(mem_db):
    future = int(time.time()) + 3600
    await mem_db.execute(
        "INSERT INTO vacancy_cache VALUES (?, ?, ?)", ("v1", json.dumps({"title": "Dev"}), future)
    )
    await mem_db.execute(
        "INSERT INTO sent_notifications (user_id, vacancy_uid, sent_at) VALUES (1, 'v1', ?)",
        (int(time.time()),),
    )
    await mem_db.commit()

    assert await _pick_vacancy_for_user(mem_db, 1, {}) is None
    # Boshqa foydalanuvchi uchun hali ham mavjud.
    assert await _pick_vacancy_for_user(mem_db, 2, {}) is not None


@pytest.mark.asyncio
async def test_pick_skips_expired_vacancies(mem_db):
    past = int(time.time()) - 100
    await mem_db.execute(
        "INSERT INTO vacancy_cache VALUES (?, ?, ?)", ("v_old", json.dumps({"title": "Old"}), past)
    )
    await mem_db.commit()

    assert await _pick_vacancy_for_user(mem_db, 1, {}) is None


@pytest.mark.asyncio
async def test_pick_salary_filter(mem_db):
    future = int(time.time()) + 3600
    await mem_db.execute(
        "INSERT INTO vacancy_cache VALUES (?, ?, ?)",
        ("low_pay", json.dumps({"title": "Low", "salary_max": 1000000}), future),
    )
    await mem_db.execute(
        "INSERT INTO vacancy_cache VALUES (?, ?, ?)",
        ("high_pay", json.dumps({"title": "High", "salary_max": 8000000}), future),
    )
    await mem_db.commit()

    result = await _pick_vacancy_for_user(mem_db, 1, {"min_salary": 5000000})
    assert result is not None
    assert result[0] == "high_pay"


@pytest.mark.asyncio
async def test_pick_skips_salaryless_when_floor_set(mem_db):
    future = int(time.time()) + 3600
    await mem_db.execute(
        "INSERT INTO vacancy_cache VALUES (?, ?, ?)",
        ("no_salary", json.dumps({"title": "Maoshsiz"}), future),
    )
    await mem_db.commit()

    assert await _pick_vacancy_for_user(mem_db, 1, {"min_salary": 5000000}) is None
    assert await _pick_vacancy_for_user(mem_db, 1, {}) is not None


# ───────────────────────────────────────────────
# _run_notifications
# ───────────────────────────────────────────────

@pytest_asyncio.fixture
async def full_db():
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, user_pro INTEGER DEFAULT 0, "
            "pref_filters_json TEXT, lang TEXT)"
        )
        await conn.execute(
            """CREATE TABLE notification_settings (
                user_id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER,
                updated_at INTEGER
            )"""
        )
        await conn.execute(
            """CREATE TABLE sent_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                vacancy_uid TEXT NOT NULL,
                sent_at INTEGER NOT NULL
            )"""
        )
        await conn.execute(
            "CREATE UNIQUE INDEX idx_sn ON sent_notifications(user_id, vacancy_uid)"
        )
        await conn.execute(
            "CREATE TABLE vacancy_cache (uid TEXT PRIMARY KEY, data_json TEXT, expires_at INTEGER)"
        )
        yield conn


def _after_last_slot(user_id: int) -> datetime:
    return datetime.fromtimestamp(today_slots(user_id)[-1], tz=TZ) + timedelta(minutes=1)


def _before_first_slot(user_id: int) -> datetime:
    return datetime.fromtimestamp(today_slots(user_id)[0], tz=TZ) - timedelta(minutes=1)


async def _seed_user(conn, user_id: int, pro: int = 1, lang: str = "uz"):
    now = int(time.time())
    await conn.execute("INSERT INTO users VALUES (?, ?, NULL, ?)", (user_id, pro, lang))
    await conn.execute(
        "INSERT INTO notification_settings VALUES (?, 1, ?, ?)", (user_id, now, now)
    )
    await conn.execute(
        "INSERT INTO vacancy_cache VALUES (?, ?, ?)",
        (f"vc{user_id}", json.dumps({"title": "Senior Dev", "max_salary": 7000000}), now + 3600),
    )
    await conn.commit()


@pytest.mark.asyncio
async def test_run_sends_to_pro_user_after_slot(full_db):
    user_id = 101
    await _seed_user(full_db, user_id)

    mock_bot = AsyncMock()
    with patch(f"{MODULE}.bot", mock_bot), _freeze(_after_last_slot(user_id)):
        await _run_notifications(full_db)

    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args.kwargs["chat_id"] == user_id

    cur = await full_db.execute(
        "SELECT vacancy_uid FROM sent_notifications WHERE user_id = ?", (user_id,)
    )
    assert len(await cur.fetchall()) == 1


@pytest.mark.asyncio
async def test_run_waits_until_first_slot(full_db):
    """Birinchi slotdan oldin hech narsa yuborilmaydi (eski bug: hech qachon yuborilmasdi)."""
    user_id = 102
    await _seed_user(full_db, user_id)

    mock_bot = AsyncMock()
    with patch(f"{MODULE}.bot", mock_bot), _freeze(_before_first_slot(user_id)):
        await _run_notifications(full_db)

    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_run_skips_free_user(full_db):
    user_id = 202
    await _seed_user(full_db, user_id, pro=0)

    mock_bot = AsyncMock()
    with patch(f"{MODULE}.bot", mock_bot), _freeze(_after_last_slot(user_id)):
        await _run_notifications(full_db)

    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_run_respects_max_per_day(full_db):
    user_id = 303
    await _seed_user(full_db, user_id)
    today_start = _today_start_ts()
    for i in range(MAX_PER_DAY):
        await full_db.execute(
            "INSERT INTO sent_notifications (user_id, vacancy_uid, sent_at) VALUES (?, ?, ?)",
            (user_id, f"old_uid_{i}", today_start + i),
        )
    await full_db.commit()

    mock_bot = AsyncMock()
    with patch(f"{MODULE}.bot", mock_bot), _freeze(_after_last_slot(user_id)):
        await _run_notifications(full_db)

    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_run_sends_only_one_per_due_slot(full_db):
    """Birinchi slot o'tgach 1 ta yuboriladi, ikkinchisi kelmaguncha yana yuborilmaydi."""
    user_id = 404
    await _seed_user(full_db, user_id)
    now = int(time.time())
    await full_db.execute(
        "INSERT INTO vacancy_cache VALUES (?, ?, ?)",
        ("extra", json.dumps({"title": "Boshqa"}), now + 3600),
    )
    await full_db.commit()

    slots = today_slots(user_id)
    between = datetime.fromtimestamp(slots[0], tz=TZ) + timedelta(minutes=1)

    mock_bot = AsyncMock()
    with patch(f"{MODULE}.bot", mock_bot), _freeze(between):
        await _run_notifications(full_db)
        await _run_notifications(full_db)

    assert mock_bot.send_message.call_count == 1


@pytest.mark.asyncio
async def test_run_uses_user_language(full_db):
    user_id = 505
    await _seed_user(full_db, user_id, lang="ru")

    mock_bot = AsyncMock()
    with patch(f"{MODULE}.bot", mock_bot), _freeze(_after_last_slot(user_id)):
        await _run_notifications(full_db)

    text = mock_bot.send_message.call_args.kwargs["text"]
    assert "Вакансия для вас" in text


@pytest.mark.asyncio
async def test_notification_text_escapes_html(full_db):
    user_id = 606
    now = int(time.time())
    await full_db.execute("INSERT INTO users VALUES (?, 1, NULL, 'uz')", (user_id,))
    await full_db.execute(
        "INSERT INTO notification_settings VALUES (?, 1, ?, ?)", (user_id, now, now)
    )
    await full_db.execute(
        "INSERT INTO vacancy_cache VALUES (?, ?, ?)",
        ("evil", json.dumps({"title": "<b>hack</b> & co"}), now + 3600),
    )
    await full_db.commit()

    mock_bot = AsyncMock()
    with patch(f"{MODULE}.bot", mock_bot), _freeze(_after_last_slot(user_id)):
        await _run_notifications(full_db)

    text = mock_bot.send_message.call_args.kwargs["text"]
    assert "&lt;b&gt;hack&lt;/b&gt; &amp; co" in text
