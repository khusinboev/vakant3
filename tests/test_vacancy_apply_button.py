"""Source hiding (owner decision A) and premium emoji split (B) on the bot side.

Channel posts, notifications and the ``/start vacancy_<uid>`` card never name
the vacancy source (hh.uz / osonish / vacancy.gov.uz); they carry ONE neutral
"Apply" URL button to the original page. Channel output stays plain emoji,
private output uses premium emoji. Telegram is a mock / recording session.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.methods import SendMessage

from src.buttons.buttuns import channel_vacancy_kb, open_app_kb
from src.functions import auto_post_scheduler as ap
from src.functions import notification_scheduler as notif
from src.functions.vacancy_format import format_vacancy_message_html, vacancy_apply_url
from src.i18n import t
from src.i18n.en import STRINGS as EN
from src.i18n.ru import STRINGS as RU
from src.i18n.uz import STRINGS as UZ
from src.ui.emoji import ICONS
from tests import test_autopost_admin as apt
from tests import test_c_bot_ux
from tests.test_c_bot_ux import USER, _inline
from tests.test_store_consumers import put, vac

ux = test_c_bot_ux.ux
premium = test_c_bot_ux.premium

SOURCE_NAMES = re.compile(r"hh\.uz|osonish|vacancy\.gov|hh\.ru", re.IGNORECASE)
TAGS = re.compile(r"<[^>]+>")
APPLY = {"uz": "Ariza topshirish", "ru": "Откликнуться", "en": "Apply"}
OSONISH_DETAIL = {"id": 42, "title": "Oshpaz", "company": {"name": "Restoran"}, "min_salary": 5_000_000}


def visible(html_text: str) -> str:
    """The text a user reads: tags (and so hrefs) removed."""
    return TAGS.sub("", html_text)


def assert_no_source(markup, text: str) -> None:
    assert not SOURCE_NAMES.search(visible(text)), text
    for button in _inline(markup):
        assert not SOURCE_NAMES.search(button.text), button.text


@pytest.fixture
async def conn(tmp_path):
    c = await apt._migrated_conn(tmp_path)
    await apt._add_auto_post_tables(c)
    yield c
    await c.close()


def _bot():
    mock = AsyncMock()
    mock.send_message.return_value = SimpleNamespace(message_id=1)
    return mock


# ---------------------------------------------------------------- i18n


def test_apply_label_in_every_language_and_no_old_original_key():
    for lang, d in (("uz", UZ), ("ru", RU), ("en", EN)):
        assert d["start.btn.apply"] == APPLY[lang]
        assert "start.btn.open_original" not in d


def test_no_user_facing_bot_string_names_a_vacancy_source():
    for lang, d in (("uz", UZ), ("ru", RU), ("en", EN)):
        for key, value in d.items():
            assert not SOURCE_NAMES.search(value), (lang, key, value)


def test_no_user_facing_miniapp_vacancy_string_names_a_vacancy_source():
    root = Path(__file__).resolve().parent.parent / "webapp" / "frontend" / "src" / "i18n"
    for lang in ("uz", "ru", "en"):
        for line in (root / lang / "vacancy.ts").read_text(encoding="utf-8").splitlines():
            code = line.strip()
            if code.startswith(("//", "/*", "*")):
                continue  # comments are internal
            assert not SOURCE_NAMES.search(code), (lang, line)
        assert '"vacancy.apply"' in (root / lang / "vacancy.ts").read_text(encoding="utf-8")


def test_miniapp_renders_no_source_badge():
    src = Path(__file__).resolve().parent.parent / "webapp" / "frontend" / "src"
    assert not (src / "components" / "Jobs" / "SourceBadge.tsx").exists()
    for path in src.rglob("*.tsx"):
        if "pages/Admin" in path.as_posix():
            continue  # the admin panel may show the source (internal)
        assert "SourceBadge" not in path.read_text(encoding="utf-8"), path


# ---------------------------------------------------------------- vacancy_apply_url


def test_apply_url_is_the_original_page_only_when_https():
    assert vacancy_apply_url("hh_1", {"source": "hh", "source_id": "1", "url": "https://hh.uz/vacancy/1"}) == (
        "https://hh.uz/vacancy/1"
    )
    assert vacancy_apply_url("osonish_42", OSONISH_DETAIL) == "https://osonish.uz/vacancies/42"
    for bad in ("", "http://hh.uz/vacancy/1", "javascript:alert(1)", "https://a b"):
        row = {"source": "hh", "source_id": "1", "url": bad}
        assert vacancy_apply_url("hh_1", row) is None, bad
    assert vacancy_apply_url("zz_1", {"title": "x"}) is None


def test_keyboards_without_an_apply_url_have_no_apply_button():
    """Pro-locked / no link: the button is simply absent."""
    for kb in (channel_vacancy_kb("uz", "https://t.me/b?start=vacancy_hh_1"), open_app_kb("uz", "https://x.uz/app")):
        assert len(_inline(kb)) == 1
        assert all(b.text != "Ariza topshirish" and "Ariza" not in b.text for b in _inline(kb))
    assert len(_inline(channel_vacancy_kb("uz", "https://t.me/b", "http://insecure"))) == 1


# ---------------------------------------------------------------- channel posts (plain)


@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
@pytest.mark.parametrize("source", ["hh", "osonish"])
async def test_channel_post_has_one_apply_button_and_names_no_source(conn, premium, source, lang):
    await put(conn, vac(source, "900000000601", title="Dasturchi", employer="Synthetic LLC"))
    mock = _bot()
    with patch.object(ap, "bot", mock):
        result = await ap.pick_and_post(conn, channel="@ch", min_salary=0, lang=lang, min_quality=0)
    assert result["status"] == "sent"
    kwargs = mock.send_message.call_args.kwargs
    assert_no_source(kwargs["reply_markup"], kwargs["text"])
    buttons = _inline(kwargs["reply_markup"])
    host = "hh.uz" if source == "hh" else "osonish.uz"
    assert [b.url for b in buttons] == [
        f"https://t.me/bandlikuzbot?start=vacancy_{source}_900000000601",
        f"https://{host}/vacancy/900000000601",
    ]
    apply = buttons[1]
    assert apply.text == f"{ICONS['description'].fallback} {APPLY[lang]}"  # plain label, never a custom icon
    assert apply.icon_custom_emoji_id is None
    assert "https://" not in visible(kwargs["text"])  # the URL text itself is never shown


async def test_channel_post_stays_plain_even_with_premium_on(conn, premium):
    await put(conn, vac("hh", "900000000602"))
    mock = _bot()
    with patch.object(ap, "bot", mock):
        await ap.pick_and_post(conn, channel="@ch", min_salary=0, lang="uz", min_quality=0)
    kwargs = mock.send_message.call_args.kwargs
    assert "<tg-emoji" not in kwargs["text"]
    assert all(b.icon_custom_emoji_id is None for b in _inline(kwargs["reply_markup"]))


async def test_channel_post_from_the_osonish_cache_gets_the_apply_button(tmp_path):
    c = await apt._migrated_conn(tmp_path)
    await apt._add_auto_post_tables(c)
    await c.execute(
        "INSERT INTO vacancy_cache (uid, data_json, expires_at) VALUES (?, ?, ?)",
        ("osonish_42", json.dumps(OSONISH_DETAIL), int(time.time()) + 3600),
    )
    await c.commit()
    mock = _bot()
    try:
        with patch.object(ap, "bot", mock):
            result = await ap.pick_and_post(c, channel="@ch", min_salary=0, lang="uz", use_store=False)
    finally:
        await c.close()
    assert result["status"] == "sent"
    kwargs = mock.send_message.call_args.kwargs
    assert_no_source(kwargs["reply_markup"], kwargs["text"])
    assert [b.url for b in _inline(kwargs["reply_markup"])][1] == "https://osonish.uz/vacancies/42"


# ---------------------------------------------------------------- notifications (premium)


@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
async def test_notification_is_premium_names_no_source_and_has_apply(premium, lang):
    row = {"uid": "hh_900000000603", "source": "hh", "source_id": "900000000603", "title": "Backend",
           "employer": "Synthetic LLC", "salary_min": 6_000_000, "salary_max": 9_000_000, "currency": "UZS",
           "region_soato": "1726", "description_text": "x", "url": "https://hh.uz/vacancy/900000000603"}
    mock = _bot()
    with patch.object(notif, "bot", mock):
        assert await notif._send_notification(USER, lang, row["uid"], row) == "sent"
    kwargs = mock.send_message.call_args.kwargs
    text = kwargs["text"]
    assert text.count("<tg-emoji") >= 4  # bell, position, company, salary, location, link
    assert_no_source(kwargs["reply_markup"], text)
    app, apply = _inline(kwargs["reply_markup"])
    assert app.web_app.url.endswith("?go=vacancy_hh_900000000603")
    assert apply.url == "https://hh.uz/vacancy/900000000603"
    assert (apply.text, apply.icon_custom_emoji_id) == (APPLY[lang], ICONS["description"].id)
    assert "https://" not in visible(text)


async def test_notification_is_plain_when_premium_is_off(monkeypatch):
    monkeypatch.setenv("BOT_PREMIUM_EMOJI", "0")
    mock = _bot()
    with patch.object(notif, "bot", mock):
        await notif._send_notification(USER, "uz", "osonish_42", OSONISH_DETAIL)
    kwargs = mock.send_message.call_args.kwargs
    assert "<tg-emoji" not in kwargs["text"]
    apply = _inline(kwargs["reply_markup"])[1]
    assert apply.icon_custom_emoji_id is None and apply.text == f"{ICONS['description'].fallback} Ariza topshirish"


# ---------------------------------------------------------------- bot deeplink (premium)


async def test_deeplink_card_has_the_apply_button_and_no_source_name(ux, premium):
    await ux.send(USER, "/start vacancy_osonish_123")
    card = ux.session.of(SendMessage)[-1]
    assert_no_source(card.reply_markup, card.text)
    app, apply = _inline(card.reply_markup)
    assert app.web_app is not None
    assert apply.url == "https://osonish.uz/vacancies/123"
    assert (apply.text, apply.icon_custom_emoji_id) == ("Ariza topshirish", ICONS["description"].id)
    assert '<tg-emoji emoji-id="' in card.text


async def test_deeplink_of_an_hh_row_applies_via_the_stored_url(ux, premium):
    from tests.test_store_consumers import _store_rows

    await _store_rows(ux.db_path, vac(sid="900000000604", title="Dasturchi"))
    await ux.send(USER, "/start vacancy_hh_900000000604")
    card = ux.session.of(SendMessage)[-1]
    assert_no_source(card.reply_markup, card.text)
    assert _inline(card.reply_markup)[1].url == "https://hh.uz/vacancy/900000000604"


def test_full_card_text_never_prints_a_url_or_source_for_any_source():
    for uid, row in (
        ("hh_5", {"uid": "hh_5", "source": "hh", "source_id": "5", "title": "T", "employer": "E",
                  "url": "https://hh.uz/vacancy/5", "description_text": "d"}),
        ("osonish_5", OSONISH_DETAIL),
    ):
        text = visible(format_vacancy_message_html(uid, row, "ru"))
        assert "https://" not in text and not SOURCE_NAMES.search(text), text
    assert t("uz", "vacancy.label.source") == "Manba"  # the footer names OUR bot, see below
    assert "@bandlikuzbot" in visible(format_vacancy_message_html("osonish_5", OSONISH_DETAIL, "uz"))
