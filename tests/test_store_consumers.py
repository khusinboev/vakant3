"""Vacancy store consumers on the bot side: formatting store rows, channel
auto-post selection, notifications and the ``/start vacancy_<uid>`` deeplink.

Store rows are written through ``src.ingest.repo`` (the real upsert path) on a
migrated temp SQLite file; Telegram is a mock / recording session. Synthetic
data only (ids from 900000000000).
"""
from __future__ import annotations

import time
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest
from aiogram.methods import SendMessage

from src.core.timeutil import TZ
from src.functions import auto_post_scheduler as ap
from src.functions import notification_scheduler as notif
from src.functions.vacancy_format import (
    HH_EXCERPT_LEN,
    format_vacancy_message_html,
    normalize_store_vacancy,
    parse_vacancy_uid,
)
from src.i18n import t
from src.ingest import repo
from src.ingest.base import NormalizedVacancy
from tests import test_autopost_admin as apt
from tests import test_c_bot_ux
from tests.test_c_bot_ux import USER, _inline

# Shared fixtures of the bot UX harness.
ux = test_c_bot_ux.ux
premium = test_c_bot_ux.premium

HOUR = 3600


def vac(source="hh", sid="900000000001", *, title="Python developer", employer="Synthetic LLC", region="1726",
        smin=6_000_000, smax=9_000_000, currency="UZS", age=HOUR, desc="Talablar: Python, SQL. " * 10,
        **kw) -> NormalizedVacancy:
    return NormalizedVacancy(
        source=source, source_id=sid, title=title, employer=employer, region_soato=region,
        salary_min=smin, salary_max=smax, currency=currency, published_at=int(time.time()) - age,
        description_text=desc, url=f"https://{'hh.uz' if source == 'hh' else 'osonish.uz'}/vacancy/{sid}", **kw,
    )


async def put(conn, *items: NormalizedVacancy) -> None:
    await repo.upsert_batch(conn, list(items), int(time.time()))


@pytest.fixture
async def conn(tmp_path):
    c = await apt._migrated_conn(tmp_path)
    await apt._add_auto_post_tables(c)
    yield c
    await c.close()


# ---------------------------------------------------------------- formatting


def test_parse_vacancy_uid_accepts_store_sources_only():
    assert parse_vacancy_uid("hh_123") == ("hh", "123")
    assert parse_vacancy_uid("osonish_900000000001") == ("osonish", "900000000001")
    for bad in ("hh_", "hh_0", "hh_012", "hh_1a", "zz_1", "osonish_-1", "hh_" + "1" * 17, None, 5):
        assert parse_vacancy_uid(bad) is None, bad


@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
def test_hh_row_labels_salary_and_excerpt(lang):
    row = {
        "uid": "hh_900000000001", "source": "hh", "source_id": "900000000001", "title": "Data analyst",
        "employer": "Synthetic LLC", "salary_min": 1500, "salary_max": 2500, "currency": "USD",
        "region_soato": "1726", "region_name": "Ташкент", "experience": "between1And3", "employment": "full",
        "schedule": "remote", "description_text": "x" * 2000, "url": "https://hh.uz/vacancy/900000000001",
        "contacts": {"phones": ["+998900000000"], "email": "hr@example.test"}, "published_at": 1_792_213_200,
    }
    n = normalize_store_vacancy(row, lang)
    assert n["experience"] == t(lang, "vacancy.hh.experience.between1And3")
    assert n["busyness_type"] == t(lang, "vacancy.hh.employment.full")
    assert n["work_type"] == t(lang, "vacancy.hh.schedule.remote")
    assert n["salary"] == t(lang, "vacancy.salary.cur_range", min="1 500", max="2 500", cur="USD")
    assert len(n["description"]) <= HH_EXCERPT_LEN
    # hh.uz terms: no contacts from hh, ever; the original link instead.
    assert n["hr_phone"] == "" and n["hr_email"] == ""
    assert n["url"] == n["source_url"] == "https://hh.uz/vacancy/900000000001"
    assert n["source"] == "hh" and n["source_label"] == "hh.uz"
    assert n["codes"]["experience"] is None
    assert n["posted_at"] == datetime.fromtimestamp(1_792_213_200, TZ).strftime("%Y-%m-%d")


def test_unknown_hh_id_is_left_blank_and_rur_is_rub():
    row = {"uid": "hh_1", "source": "hh", "source_id": "1", "title": "X", "experience": "galaxyBrain",
           "salary_min": 90_000, "salary_max": None, "currency": "RUR"}
    n = normalize_store_vacancy(row, "ru")
    assert n["experience"] == ""
    assert n["salary"] == "от 90 000 RUB"


def test_osonish_row_without_detail_uses_osonish_code_labels():
    row = {"uid": "osonish_7", "source": "osonish", "source_id": "7", "title": "Oshpaz", "experience": "3",
           "employment": "1", "schedule": "2", "salary_min": 3_000_000, "salary_max": None, "currency": "UZS",
           "contacts": {"phones": ["+998900000001"]}, "checked_at": None, "raw": {}}
    n = normalize_store_vacancy(row, "uz")
    assert n["experience"] == t("uz", "vacancy.experience.3")
    assert n["busyness_type"] == t("uz", "vacancy.busyness.1")
    assert n["work_type"] == t("uz", "vacancy.work_type.2")
    assert n["codes"]["experience"] == 3
    assert n["hr_phone"] == "+998900000001"
    assert n["salary"] == t("uz", "vacancy.salary.from", min="3 000 000")


def test_checked_osonish_row_renders_like_the_live_detail():
    raw = {"id": 7, "title": "Oshpaz", "hr": {"phone": "+998900000002"}, "work_experiance": 2,
           "company": {"name": "Restoran"}, "min_salary": 4_000_000, "max_salary": 5_000_000}
    row = {"uid": "osonish_7", "source": "osonish", "source_id": "7", "checked_at": 1, "raw": raw,
           "description_text": "Taom tayyorlash", "url": "https://osonish.uz/vacancies/7"}
    n = normalize_store_vacancy(row, "uz")
    assert n["hr_phone"] == "+998900000002" and n["company"] == "Restoran"
    assert n["description"] == "Taom tayyorlash" and n["codes"]["experience"] == 2


def test_channel_post_of_an_hh_row_is_escaped_short_and_plain():
    row = {"uid": "hh_5", "source": "hh", "source_id": "5", "title": "Dev <b>&", "employer": "A&B",
           "salary_min": 5_000_000, "salary_max": None, "currency": "UZS", "region_soato": "1726",
           "description_text": "word " * 400, "url": "https://hh.uz/vacancy/5"}
    text = format_vacancy_message_html("hh_5", row, "uz", plain=True)
    assert "Dev &lt;b&gt;&amp;" in text and "A&amp;B" in text
    assert "<tg-emoji" not in text
    assert text.count("word") <= 70  # excerpt (300 chars), never the full 2000-char text
    assert "Toshkent shahri" in text


# ---------------------------------------------------------------- auto-post


def _bot(message_id=1):
    mock = AsyncMock()
    mock.send_message.return_value = SimpleNamespace(message_id=message_id)
    return mock


async def _post(conn, **kw):
    mock = _bot()
    with patch.object(ap, "bot", mock):
        result = await ap.pick_and_post(conn, channel="@ch", lang="uz", **{"min_salary": 0, **kw})
    return result, mock


async def test_autopost_picks_fresh_quality_rows_with_salary_and_employer(conn):
    await put(
        conn,
        vac(sid="900000000001", title="Old", age=60 * HOUR),
        vac(sid="900000000002", title="No salary", smin=None, smax=None),
        vac(sid="900000000003", title="No employer", employer=""),
        vac(sid="900000000004", title="Cheap", smin=1_000_000, smax=1_500_000),
        vac(sid="900000000005", title="Good", age=2 * HOUR),
    )
    result, mock = await _post(conn, min_salary=3_000_000, min_quality=0)
    assert result["status"] == "sent" and result["uid"] == "hh_900000000005"
    kwargs = mock.send_message.call_args.kwargs
    buttons = _inline(kwargs["reply_markup"])
    assert [b.url for b in buttons] == [
        "https://t.me/bandlikuzbot?start=vacancy_hh_900000000005", "https://hh.uz/vacancy/900000000005",
    ]
    assert buttons[1].text.endswith(t("uz", "start.btn.open_original"))
    # Excluded once posted.
    again, _ = await _post(conn, min_salary=3_000_000, min_quality=0)
    assert again["status"] == "skipped" and again["error"] == "no_vacancy"


async def test_autopost_quality_floor(conn):
    await put(conn, vac(sid="900000000011", desc=""))  # short text -> lower quality score
    score = (await repo.get(conn, "hh_900000000011"))["quality_score"]
    result, _ = await _post(conn, min_quality=score + 1)
    assert result["status"] == "skipped"
    result, _ = await _post(conn, min_quality=score)
    assert result["status"] == "sent"


async def test_autopost_never_three_in_a_row_from_one_employer(conn):
    await put(
        conn,
        *[vac(sid=f"90000000002{i}", title=f"Role {i}", employer="Same Corp", age=HOUR + i) for i in range(4)],
        vac(sid="900000000030", title="Other", employer="Other Corp", age=10 * HOUR),
    )
    picked = [(await _post(conn, min_quality=0))[0]["uid"] for _ in range(3)]
    assert picked[:2] == ["hh_900000000020", "hh_900000000021"]
    assert picked[2] == "hh_900000000030"


async def test_autopost_alternates_sources_when_both_have_candidates(conn):
    await put(
        conn,
        vac("hh", "900000000041", title="Backend", employer="E1", age=HOUR),
        vac("hh", "900000000042", title="Frontend", employer="E2", age=HOUR + 1),
        vac("osonish", "900000000043", title="Haydovchi", employer="E3", age=5 * HOUR),
    )
    picked = [(await _post(conn, min_quality=0))[0]["uid"] for _ in range(3)]
    assert picked == ["hh_900000000041", "osonish_900000000043", "hh_900000000042"]


async def test_autopost_skips_a_duplicate_group_already_posted(conn):
    await put(conn, vac("osonish", "900000000051", title="Kassir", employer="Market", age=3 * HOUR))
    first, _ = await _post(conn, min_quality=0)
    assert first["uid"] == "osonish_900000000051"
    # The same job arrives from hh and becomes the group's canonical copy.
    await put(conn, vac("hh", "900000000052", title="Kassir", employer="Market", age=HOUR))
    r = await repo.get(conn, "hh_900000000052")
    assert r["dup_of"] is None and r["dedup_group"] == (await repo.get(conn, "osonish_900000000051"))["dedup_group"]
    second, _ = await _post(conn, min_quality=0)
    assert second["status"] == "skipped"


async def test_autopost_falls_back_to_vacancy_cache_when_store_is_empty(conn):
    await conn.execute(
        "INSERT INTO vacancy_cache (uid, data_json, expires_at) VALUES ('osonish_900000000061', ?, ?)",
        ('{"title": "Cached"}', int(time.time()) + HOUR),
    )
    await conn.commit()
    result, _ = await _post(conn)
    assert result == {"status": "sent", "uid": "osonish_900000000061", "message_id": 1, "error": None}


async def test_autopost_store_with_nothing_fresh_also_falls_back(conn):
    await put(conn, vac(sid="900000000071", age=100 * HOUR))
    await conn.execute(
        "INSERT INTO vacancy_cache (uid, data_json, expires_at) VALUES ('osonish_900000000072', ?, ?)",
        ('{"title": "Cached"}', int(time.time()) + HOUR),
    )
    await conn.commit()
    result, _ = await _post(conn)
    assert result["uid"] == "osonish_900000000072"


async def test_autopost_fresh_store_does_not_fall_back(conn):
    """A fresh store with no eligible row skips the slot instead of posting unfiltered cache rows."""
    await put(conn, vac(sid="900000000081", smin=None, smax=None))
    await conn.execute(
        "INSERT INTO vacancy_cache (uid, data_json, expires_at) VALUES ('osonish_900000000082', ?, ?)",
        ('{"title": "Cached"}', int(time.time()) + HOUR),
    )
    await conn.commit()
    result, _ = await _post(conn, min_quality=0)
    assert result["status"] == "skipped"


async def test_scheduler_tick_passes_min_quality_and_skips_cache_refresh(conn):
    await apt._seed_admin_settings(conn, autopost_min_quality=100)
    await put(conn, vac(sid="900000000091"))
    settings = dict(await (await conn.execute("SELECT * FROM webapp_admin_settings")).fetchone())
    now = int(time.time())
    settings.update(auto_post_scheduled_day=ap.day_key(),
                    auto_post_scheduled_times_json=f'[{{"ts": {now - 60}, "done": false, "uid": null}}]')
    refresh = AsyncMock()
    with patch.object(ap, "bot", _bot()), patch.object(ap, "_refresh_vacancy_cache", refresh):
        await ap._run_auto_post(conn, settings)
    refresh.assert_not_called()  # the store is fresh: no live osonish call
    log = await (await conn.execute("SELECT status, error FROM auto_post_log")).fetchall()
    assert [tuple(r) for r in log] == [("skipped", "no_vacancy")]  # quality 100 not reached


def test_min_quality_of_clamps_and_defaults():
    assert ap.min_quality_of({}) == 60
    assert ap.min_quality_of({"autopost_min_quality": None}) == 60
    assert ap.min_quality_of({"autopost_min_quality": 0}) == 0
    assert ap.min_quality_of({"autopost_min_quality": 250}) == 100
    assert ap.min_quality_of({"autopost_min_quality": "x"}) == 60


async def test_post_now_with_an_hh_uid_uses_the_store(conn):
    await put(conn, vac(sid="900000000101", title="Analyst"))
    result, mock = await _post(conn, uid="hh_900000000101")
    assert result["status"] == "sent"
    assert "Analyst" in mock.send_message.call_args.kwargs["text"]


# ---------------------------------------------------------------- notifications


async def _notif_db(tmp_path):
    c = await apt._migrated_conn(tmp_path, "notif.sqlite3")
    await c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    cols = {r[1] for r in await (await c.execute("PRAGMA table_info(users)")).fetchall()}
    for col, ddl in (("user_pro", "INTEGER DEFAULT 0"), ("pref_filters_json", "TEXT"), ("lang", "TEXT"),
                     ("blocked", "INTEGER NOT NULL DEFAULT 0")):
        if col not in cols:
            await c.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
    for ddl in (
        "CREATE TABLE IF NOT EXISTS notification_settings (user_id INTEGER PRIMARY KEY, "
        "enabled INTEGER NOT NULL DEFAULT 0, created_at INTEGER, updated_at INTEGER)",
        "CREATE TABLE IF NOT EXISTS sent_notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER NOT NULL, vacancy_uid TEXT NOT NULL, sent_at INTEGER NOT NULL)",
        "CREATE TABLE IF NOT EXISTS vacancy_cache (uid TEXT PRIMARY KEY, data_json TEXT, expires_at INTEGER)",
    ):
        await c.execute(ddl)
    await c.commit()
    return c


async def test_notification_candidates_come_from_the_store(tmp_path):
    c = await _notif_db(tmp_path)
    try:
        await put(
            c,
            vac(sid="900000000201", title="Fresh hh"),
            vac("osonish", "900000000202", title="Fresh osonish", employer="Other"),
            vac(sid="900000000203", title="Stale", employer="Third", age=100 * HOUR),
        )
        await c.execute(
            "INSERT INTO vacancy_cache VALUES ('vc1', '{\"title\": \"cache\"}', ?)", (int(time.time()) + HOUR,)
        )
        await c.commit()
        uids = [uid for uid, _ in await notif._load_candidates(c)]
        assert set(uids) == {"hh_900000000201", "osonish_900000000202"}
    finally:
        await c.close()


async def test_notification_matching_on_store_rows(tmp_path):
    c = await _notif_db(tmp_path)
    try:
        await put(
            c,
            vac(sid="900000000301", title="Toshkent", region="1726", smin=5_000_000, smax=8_000_000),
            vac(sid="900000000302", title="Samarqand", employer="S", region="1718", smin=9_000_000, smax=None),
            vac(sid="900000000303", title="Dollar", employer="D", region="1726", smin=3000, smax=4000,
                currency="USD"),
        )
        candidates = await notif._load_candidates(c)
        pool = lambda f: sorted(u for u, d in candidates if notif._matches_filters(d, f))  # noqa: E731
        assert pool({"region_soato": "1718"}) == ["hh_900000000302"]
        # A UZS floor: foreign currency never passes, salary_min counts when there is no max.
        assert pool({"min_salary": 7_000_000}) == ["hh_900000000301", "hh_900000000302"]
        assert pool({"min_salary": 8_500_000}) == ["hh_900000000302"]
        # No category on store rows: a category filter does not exclude them (as before).
        assert len(pool({"specs": "spec:12"})) == 3
    finally:
        await c.close()


async def test_notification_tick_from_store_keeps_bounded_queries(tmp_path):
    c = await _notif_db(tmp_path)
    try:
        await put(c, *[vac(sid=str(900000000400 + i), title=f"Ish {i}", employer=f"E{i}") for i in range(30)])
        users = list(range(900000000500, 900000000700))
        now = int(time.time())
        await c.executemany("INSERT INTO users (user_id, user_pro, lang) VALUES (?, 1, 'uz')", [(u,) for u in users])
        await c.executemany("INSERT INTO notification_settings VALUES (?, 1, ?, ?)", [(u, now, now) for u in users])
        await c.commit()

        from tests.test_notifications import WORK_HOUR_END, _at, _CountingConn, _FakeBot, _freeze

        counting = _CountingConn(c)
        fake = _FakeBot()
        with patch.object(notif, "bot", fake), patch.object(notif, "SEND_RATE_PER_SECOND", 100_000), \
                _freeze(_at(WORK_HOUR_END, 30)):
            await notif._run_notifications(counting)
        assert sorted(fake.sent) == users
        assert not any("vacancy_cache" in q for q in counting.queries)
        assert len(counting.queries) <= 10, counting.queries
        cur = await c.execute("SELECT COUNT(*) FROM sent_notifications WHERE vacancy_uid LIKE 'hh_%'")
        assert (await cur.fetchone())[0] == len(users)
    finally:
        await c.close()


async def test_notification_falls_back_to_cache_without_store_rows(tmp_path):
    c = await _notif_db(tmp_path)
    try:
        await c.execute(
            "INSERT INTO vacancy_cache VALUES ('osonish_900000000801', '{\"title\": \"cache\"}', ?)",
            (int(time.time()) + HOUR,),
        )
        await c.commit()
        assert [u for u, _ in await notif._load_candidates(c)] == ["osonish_900000000801"]
    finally:
        await c.close()


# ---------------------------------------------------------------- bot deeplink


async def _store_rows(db_path, *items):
    async with aiosqlite.connect(db_path) as c:
        c.row_factory = aiosqlite.Row
        await repo.upsert_batch(c, list(items), int(time.time()))


async def test_deeplink_to_an_hh_vacancy_renders_it_from_the_store(ux, premium):
    await _store_rows(ux.db_path, vac(sid="900000000901", title="Dasturchi <hh>", employer="Synthetic LLC"))
    await ux.send(USER, "/start vacancy_hh_900000000901")
    card = ux.session.of(SendMessage)[-1]
    assert "Dasturchi &lt;hh&gt;" in card.text and "Synthetic LLC" in card.text
    button = _inline(card.reply_markup)[0]
    assert button.web_app.url.endswith("?go=vacancy_hh_900000000901")


async def test_deeplink_to_an_unknown_hh_vacancy_says_not_found(ux):
    await ux.send(USER, "/start vacancy_hh_900000000999")
    assert ux.session.of(SendMessage)[-1].text == t("uz", "start.vacancy_not_found")


async def test_deeplink_with_a_bad_uid_is_rejected(ux):
    await ux.send(USER, "/start vacancy_hh_12a")
    assert ux.session.of(SendMessage)[-1].text == t("uz", "start.bad_vacancy_link")
