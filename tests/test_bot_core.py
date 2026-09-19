"""
Bot yadrosi testlari: referral (ushlash + mukofot), referral gate holati,
vakansiya formatlash (HTML escaping + til) va statik ma'lumot yordamchilari.
"""
import json
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest

from src.functions.referral_gate import compute_referral_state
from src.functions.vacancy_format import (
    format_vacancy_message_html,
    normalize_vacancy_detail,
)
from src.middleware.middlewares import (
    StatsMiddleware,
    pay_referral_reward,
    parse_referrer_id,
)

MW_MODULE = "src.middleware.middlewares"


# ─── /start ref_<id> parsing ────────────────────────────────────────────────

class TestParseReferrerId:
    def test_valid(self):
        assert parse_referrer_id("/start ref_777", 1) == 777

    def test_with_bot_mention(self):
        assert parse_referrer_id("/start@bandlikuzbot ref_5", 1) == 5

    def test_self_referral_rejected(self):
        assert parse_referrer_id("/start ref_42", 42) is None

    def test_other_params(self):
        assert parse_referrer_id("/start vacancy_osonish_1", 1) is None
        assert parse_referrer_id("/start", 1) is None
        assert parse_referrer_id("salom", 1) is None
        assert parse_referrer_id(None, 1) is None

    def test_garbage_id(self):
        assert parse_referrer_id("/start ref_abc", 1) is None
        assert parse_referrer_id("/start ref_-5", 1) is None


# ─── Referral mukofoti ──────────────────────────────────────────────────────

async def _referral_db():
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute(
        "CREATE TABLE users (user_id INTEGER PRIMARY KEY, date INTEGER, lang TEXT, "
        "ref_by INTEGER, user_balance INTEGER DEFAULT 0)"
    )
    await conn.execute(
        "CREATE TABLE referral_payouts (user_id INTEGER PRIMARY KEY, inviter_id INTEGER, "
        "amount INTEGER, ts INTEGER)"
    )
    await conn.execute(
        "CREATE TABLE webapp_admin_settings (singleton INTEGER PRIMARY KEY, "
        "referral_enabled INTEGER DEFAULT 0, referral_required_count INTEGER DEFAULT 0, "
        "referral_reward INTEGER DEFAULT 2000)"
    )
    await conn.execute("INSERT INTO webapp_admin_settings VALUES (1, 0, 0, 3000)")
    await conn.commit()
    return conn


@pytest.mark.asyncio
async def test_reward_paid_once():
    conn = await _referral_db()
    await conn.execute("INSERT INTO users VALUES (10, 0, 'uz', NULL, 0)")  # inviter
    await conn.execute("INSERT INTO users VALUES (20, 0, 'uz', 10, 0)")    # invitee
    await conn.commit()

    assert await pay_referral_reward(conn, 20, 10) == 3000
    # Ikkinchi urinish — to'lanmaydi.
    assert await pay_referral_reward(conn, 20, 10) is None

    cur = await conn.execute("SELECT user_balance FROM users WHERE user_id = 10")
    assert (await cur.fetchone())[0] == 3000
    await conn.close()


@pytest.mark.asyncio
async def test_reward_skipped_for_unknown_inviter():
    conn = await _referral_db()
    await conn.execute("INSERT INTO users VALUES (20, 0, 'uz', 999, 0)")
    await conn.commit()

    assert await pay_referral_reward(conn, 20, 999) is None
    await conn.close()


@pytest.mark.asyncio
async def test_middleware_captures_ref_by_for_new_user(tmp_path):
    db_path = str(tmp_path / "bot.sqlite3")
    middleware = StatsMiddleware(db_path)

    with patch(f"{MW_MODULE}._seed_from_osonish_api", new_callable=AsyncMock):
        await middleware.init_db()

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO users (user_id, date, lang) VALUES (10, 0, 'uz')"
        )
        await conn.commit()

    with patch(f"{MW_MODULE}._notify_inviter", new_callable=AsyncMock) as notify:
        lang, is_new = await middleware.resolve_user(20, "ru-RU", 10)
        assert (lang, is_new) == ("ru", True)
        notify.assert_awaited_once()

        # Ikkinchi /start — endi yangi emas, mukofot qayta to'lanmaydi.
        lang2, is_new2 = await middleware.resolve_user(20, "ru-RU", 10)
        assert (lang2, is_new2) == ("ru", False)
        assert notify.await_count == 1

    async with aiosqlite.connect(db_path) as conn:
        cur = await conn.execute("SELECT ref_by FROM users WHERE user_id = 20")
        assert (await cur.fetchone())[0] == 10
        cur = await conn.execute("SELECT user_balance FROM users WHERE user_id = 10")
        assert (await cur.fetchone())[0] == 2000
        cur = await conn.execute("SELECT COUNT(*) FROM referral_payouts")
        assert (await cur.fetchone())[0] == 1


@pytest.mark.asyncio
async def test_middleware_normalizes_legacy_lang(tmp_path):
    db_path = str(tmp_path / "bot2.sqlite3")
    middleware = StatsMiddleware(db_path)
    with patch(f"{MW_MODULE}._seed_from_osonish_api", new_callable=AsyncMock):
        await middleware.init_db()

    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("INSERT INTO users (user_id, date, lang) VALUES (5, 0, 'en-US')")
        await conn.commit()

    lang, is_new = await middleware.resolve_user(5, "en", None)
    assert (lang, is_new) == ("en", False)

    async with aiosqlite.connect(db_path) as conn:
        cur = await conn.execute("SELECT lang FROM users WHERE user_id = 5")
        assert (await cur.fetchone())[0] == "en"


# ─── compute_referral_state ─────────────────────────────────────────────────

async def _gate_db(enabled: int, required: int, invited: int):
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute(
        "CREATE TABLE webapp_admin_settings (singleton INTEGER PRIMARY KEY, "
        "referral_enabled INTEGER, referral_required_count INTEGER)"
    )
    await conn.execute(
        "INSERT INTO webapp_admin_settings VALUES (1, ?, ?)", (enabled, required)
    )
    await conn.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY, ref_by INTEGER)")
    await conn.execute("INSERT INTO users VALUES (1, NULL)")
    for i in range(invited):
        await conn.execute("INSERT INTO users VALUES (?, 1)", (100 + i,))
    await conn.commit()
    return conn


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "enabled,required,invited,unlocked",
    [
        (0, 3, 0, True),    # o'chirilgan
        (1, 0, 0, True),    # talab yo'q
        (1, 3, 0, False),
        (1, 3, 2, False),
        (1, 3, 3, True),
        (1, 3, 5, True),
    ],
)
async def test_compute_referral_state_matrix(enabled, required, invited, unlocked):
    conn = await _gate_db(enabled, required, invited)
    state = await compute_referral_state(conn, 1)
    assert state == {
        "enabled": bool(enabled),
        "required": required,
        "count": invited,
        "unlocked": unlocked,
    }
    await conn.close()


@pytest.mark.asyncio
async def test_compute_referral_state_without_settings_table():
    """webapp hali ishga tushmagan bo'lsa — gate ochiq qoladi."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    state = await compute_referral_state(conn, 1)
    assert state["unlocked"] is True
    assert state["enabled"] is False
    await conn.close()


# ─── Vakansiya formatlash ───────────────────────────────────────────────────

_DETAIL = {
    "title": "Dasturchi <script>alert(1)</script>",
    "company": {"name": "Acme & Co"},
    "min_salary": 5_000_000,
    "max_salary": 9_000_000,
    "gender": 1,
    "work_type": 2,
    "busyness_type": 1,
    "payment_type": 3,
    "min_education": 3,
    "work_experiance": 4,
    "info": "<p>Talablar</p><li>Python</li>",
    "hr": {"name": "A & B", "phone": "+998901112233"},
}


def test_format_escapes_html_from_api():
    text = format_vacancy_message_html("osonish_1", _DETAIL)
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "Acme &amp; Co" in text


def test_format_localizes_labels():
    uz = format_vacancy_message_html("osonish_1", _DETAIL, "uz")
    ru = format_vacancy_message_html("osonish_1", _DETAIL, "ru")
    en = format_vacancy_message_html("osonish_1", _DETAIL, "en")

    assert "Maosh" in uz and "Doimiy" not in uz  # work_type=2 -> vaqtinchalik
    assert "Зарплата" in ru and "Временная работа" in ru
    assert "Salary" in en and "Temporary" in en


def test_format_compact_is_notification_shape():
    text = format_vacancy_message_html("osonish_7", _DETAIL, "uz", compact=True)
    assert "Siz uchun ish tavsiyasi" in text
    assert "start=vacancy_osonish_7" in text
    assert "Tavsif" not in text


def test_normalize_returns_raw_codes():
    normalized = normalize_vacancy_detail("osonish_1", _DETAIL, "ru")
    assert normalized["codes"] == {
        "gender": 1,
        "work_type": 2,
        "busyness_type": 1,
        "payment_type": 3,
        "education": 3,
        "experience": 4,
    }
    assert normalized["salary"].endswith("сум")


def test_normalize_unknown_code_is_labelled():
    normalized = normalize_vacancy_detail("osonish_1", {"gender": 99}, "en")
    assert normalized["gender"] == "Code 99"
    assert normalized["codes"]["gender"] == 99


def test_normalize_missing_fields_are_empty():
    normalized = normalize_vacancy_detail("osonish_1", {}, "uz")
    assert normalized["title"] == "Vakansiya"
    assert normalized["salary"] == "Kelishiladi"
    assert normalized["work_type"] == ""
    assert normalized["codes"]["work_type"] is None


def test_json_roundtrip_of_normalized_is_serialisable():
    normalized = normalize_vacancy_detail("osonish_1", _DETAIL, "en")
    assert json.loads(json.dumps(normalized))["codes"]["education"] == 3


# ─── Statik ma'lumotlar (law / hr) ──────────────────────────────────────────

def test_law_articles_multilingual_shape():
    from src.data.law_articles import ARTICLES, CATEGORIES, get_article_by_id

    assert CATEGORIES and isinstance(CATEGORIES[0], str)
    article = ARTICLES[0]
    for field in ("title", "summary", "full_text", "source_label", "category"):
        assert isinstance(article[field], dict)
        assert "uz" in article[field]
    assert get_article_by_id(article["id"]) is article


def test_law_articles_flat_helpers_fallback_to_uz():
    from src.data.law_articles import get_article, get_articles, get_categories

    uz = get_articles("uz")
    ru = get_articles("ru")
    assert len(uz) == len(ru)
    # Barcha maqolalar ru/en ga tarjima qilingan — uz dan farq qilishi kerak.
    assert uz[0]["full_text"] != ru[0]["full_text"]
    # Kategoriya ham tarjima qilingan.
    assert uz[0]["category"] != ru[0]["category"]

    one = get_article(uz[0]["id"], "en")
    assert one is not None and isinstance(one["title"], str)
    assert get_article("yo-q-maqola", "uz") is None

    cats = get_categories("en")
    assert cats and set(cats[0]) == {"id", "name"}


def test_hr_tips_helpers():
    from src.data.hr_tips import HR_TIPS, get_tip, get_tips

    assert isinstance(HR_TIPS[0]["title"], dict)
    tips = get_tips("ru")
    assert tips and isinstance(tips[0]["title"], str)
    assert get_tip(tips[0]["id"], "ru")["full_text"] == tips[0]["full_text"]
    assert get_tip("yo-q", "uz") is None


# ─── Filtrlar ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_text_key_filter_matches_every_language():
    from types import SimpleNamespace

    from src.filters.text_key import TextKey
    from src.i18n import t

    flt = TextKey("menu.laws")
    for lang in ("uz", "ru", "en"):
        assert await flt(SimpleNamespace(text=t(lang, "menu.laws"))) is True
    assert await flt(SimpleNamespace(text="boshqa matn")) is False
    assert await flt(SimpleNamespace(text=None)) is False


@pytest.mark.asyncio
async def test_is_admin_filter():
    from types import SimpleNamespace

    import config
    from src.filters.admin import IsAdmin

    flt = IsAdmin()
    with patch.object(config, "ADMIN_IDS", [4242]):
        assert await flt(SimpleNamespace(from_user=SimpleNamespace(id=4242))) is True
        assert await flt(SimpleNamespace(from_user=SimpleNamespace(id=4243))) is False
        assert await flt(SimpleNamespace(from_user=None)) is False
