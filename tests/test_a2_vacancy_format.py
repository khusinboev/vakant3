"""Vacancy message: salary wording and Telegram's 4096-character limit."""
from __future__ import annotations

import html
import re

import pytest

from src.functions.vacancy_format import (
    TELEGRAM_TEXT_LIMIT,
    clean_html_text,
    format_vacancy_message_html,
    normalize_vacancy_detail,
    visible_length,
)

LANGS = ("uz", "ru", "en")

# Source HTML as osonish sends it: entities escape to longer HTML than they show.
_PARAGRAPH = {
    "uz": "<p>Nomzod Python va SQL ni yaxshi bilishi, jamoada ishlay olishi kerak &amp; &lt;tez&gt; o'rganuvchi.</p>",
    "ru": "<p>Кандидат должен хорошо знать Python и SQL, уметь работать в команде &amp; &lt;быстро&gt; учиться.</p>",
    "en": "<p>The candidate must know Python and SQL well, work in a team &amp; &lt;learn&gt; fast. 🚀</p>",
}


def _detail(lang: str, description: str, **extra) -> dict:
    detail = {
        "title": "Katta dasturchi / Старший разработчик / Senior developer",
        "company": {"name": "Acme & Co"},
        "min_salary": 5_000_000,
        "max_salary": 9_000_000,
        "gender": 1,
        "work_type": 2,
        "busyness_type": 1,
        "payment_type": 3,
        "min_education": 3,
        "work_experiance": 4,
        "count": 3,
        "working_time_from": "09:00",
        "working_time_to": "18:00",
        "created_at": "2026-10-01T10:00:00",
        "end_date": "2026-11-01",
        "address": "Toshkent shahri, Yunusobod tumani, Amir Temur ko'chasi 1",
        "info": description,
        "hr": {"name": "A & B", "phone": "+998901112233", "email": "hr@example.uz"},
    }
    detail.update(extra)
    return detail


def _telegram_visible(text: str) -> str:
    """What Telegram measures: tags removed, entities decoded."""
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def _utf16(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("repeat", [40, 45, 50, 60, 200])
def test_long_descriptions_stay_within_the_telegram_limit(lang, repeat):
    description = _PARAGRAPH[lang] * repeat
    text = format_vacancy_message_html("osonish_1", _detail(lang, description), lang)

    visible = _telegram_visible(text)
    assert _utf16(visible) <= TELEGRAM_TEXT_LIMIT
    assert visible_length(text) == _utf16(visible)
    # The contacts and the footer survive the cut.
    assert "+998901112233" in visible and visible.rstrip().endswith("@bandlikuzbot")
    # Either the whole description fits, or it was cut right at the limit.
    if "..." in visible:
        assert visible_length(text) >= TELEGRAM_TEXT_LIMIT - 4
    else:
        assert clean_html_text(description) in visible


@pytest.mark.parametrize("lang", LANGS)
def test_the_description_uses_the_whole_budget(lang):
    """Clipped to the limit, not to a fixed 3500: nothing is thrown away early."""
    text = format_vacancy_message_html("osonish_1", _detail(lang, _PARAGRAPH[lang] * 200), lang)
    assert TELEGRAM_TEXT_LIMIT - 4 <= visible_length(text) <= TELEGRAM_TEXT_LIMIT


@pytest.mark.parametrize("lang", LANGS)
def test_a_short_description_is_kept_whole(lang):
    description = _PARAGRAPH[lang]
    text = format_vacancy_message_html("osonish_1", _detail(lang, description), lang)
    assert html.escape(clean_html_text(description), quote=False) in text
    assert "..." not in _telegram_visible(text)


def test_astral_characters_count_twice():
    """Emoji are two UTF-16 units each; a char-count budget would overflow."""
    description = "🚀" * 5000
    text = format_vacancy_message_html("osonish_1", _detail("en", description), "en")
    assert visible_length(text) <= TELEGRAM_TEXT_LIMIT
    assert visible_length(text) > TELEGRAM_TEXT_LIMIT - 4


@pytest.mark.parametrize(
    "lang, expected",
    [("uz", "9 000 000 so'mgacha"), ("ru", "до 9 000 000 сум"), ("en", "up to 9 000 000 UZS")],
)
def test_max_salary_only_reads_up_to(lang, expected):
    normalized = normalize_vacancy_detail(
        "osonish_1", {"min_salary": None, "max_salary": 9_000_000}, lang
    )
    assert normalized["salary"] == expected
    text = format_vacancy_message_html(
        "osonish_1", {"min_salary": 0, "max_salary": "9000000"}, lang
    )
    assert expected in text


@pytest.mark.parametrize(
    "min_salary, max_salary, expected",
    [
        (5_000_000, 9_000_000, "5 000 000 – 9 000 000 so'm"),
        (5_000_000, None, "5 000 000 so'mdan"),
        (None, None, "Kelishiladi"),
    ],
)
def test_other_salary_shapes_are_unchanged(min_salary, max_salary, expected):
    normalized = normalize_vacancy_detail(
        "osonish_1", {"min_salary": min_salary, "max_salary": max_salary}, "uz"
    )
    assert normalized["salary"] == expected
