"""Tiny i18n layer for the API (uz / ru / en).

Deliberately independent of ``src.i18n`` (the bot's copy) — see CONTRACT.md.
Only *data* lives here: user-facing prose is never returned in error details,
it is returned as localized content fields (region names, spec labels, salary text).
"""

import re
from typing import Any

from fastapi import Depends, Request

from webapp.core.database import get_db
from webapp.core.district_names import DISTRICT_NAMES

LANGS: tuple[str, ...] = ("uz", "ru", "en")
DEFAULT_LANG = "uz"


def normalize_lang(code: Any) -> str:
    """Map anything to one of LANGS. Everything that is not ru*/en* becomes uz."""
    if not code:
        return DEFAULT_LANG
    raw = str(code).strip().lower()
    if not raw:
        return DEFAULT_LANG
    raw = re.split(r"[-_;,]", raw)[0].strip()
    if raw.startswith("ru"):
        return "ru"
    if raw.startswith("en"):
        return "en"
    return DEFAULT_LANG


def _accept_language_lang(header: str | None) -> str | None:
    if not header:
        return None
    first = header.split(",")[0].strip()
    if not first:
        return None
    return normalize_lang(first)


async def get_lang(request: Request, db=Depends(get_db)) -> str:
    """Resolve the request language: ?lang -> users.lang -> Accept-Language -> uz."""
    query_lang = request.query_params.get("lang")
    if query_lang:
        return normalize_lang(query_lang)

    # Deferred import: webapp.core.auth imports normalize_lang from this module.
    from webapp.core.auth import resolve_optional_user

    user = await resolve_optional_user(request, db)
    if user and user.get("lang"):
        return normalize_lang(user["lang"])

    return _accept_language_lang(request.headers.get("accept-language")) or DEFAULT_LANG


# ---------------------------------------------------------------------------
# Static localized data
# ---------------------------------------------------------------------------

# 14 regions, keyed by SOATO code (uz names come from the DB).
REGION_NAMES: dict[str, dict[str, str]] = {
    "1703": {"ru": "Андижанская область", "en": "Andijan Region"},
    "1706": {"ru": "Бухарская область", "en": "Bukhara Region"},
    "1708": {"ru": "Джизакская область", "en": "Jizzakh Region"},
    "1710": {"ru": "Кашкадарьинская область", "en": "Kashkadarya Region"},
    "1712": {"ru": "Навоийская область", "en": "Navoiy Region"},
    "1714": {"ru": "Наманганская область", "en": "Namangan Region"},
    "1718": {"ru": "Самаркандская область", "en": "Samarkand Region"},
    "1722": {"ru": "Сурхандарьинская область", "en": "Surkhandarya Region"},
    "1724": {"ru": "Сырдарьинская область", "en": "Sirdaryo Region"},
    "1726": {"ru": "город Ташкент", "en": "Tashkent City"},
    "1727": {"ru": "Ташкентская область", "en": "Tashkent Region"},
    "1730": {"ru": "Ферганская область", "en": "Fergana Region"},
    "1733": {"ru": "Хорезмская область", "en": "Khorezm Region"},
    "1735": {"ru": "Республика Каракалпакстан", "en": "Republic of Karakalpakstan"},
}


def region_name(soato: str, name_uz: str, lang: str) -> str:
    if lang == "uz":
        return name_uz
    entry = REGION_NAMES.get(str(soato).strip())
    if not entry:
        return name_uz
    return entry.get(lang) or name_uz


def district_name(soato: str, name_uz: str, lang: str) -> str:
    if lang == "uz":
        return name_uz
    entry = DISTRICT_NAMES.get(str(soato).strip())
    if not entry:
        return name_uz
    return entry.get(lang) or name_uz


# Specialization filter: stable id (osonish field id) -> stable key + per-lang label.
SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "spec:47",
        "key": "healthcare",
        "labels": {"uz": "Sog'liqni saqlash", "ru": "Здравоохранение", "en": "Healthcare"},
    },
    {
        "id": "spec:41",
        "key": "construction",
        "labels": {"uz": "Qurilish", "ru": "Строительство", "en": "Construction"},
    },
    {
        "id": "spec:64",
        "key": "sales_marketing",
        "labels": {"uz": "Savdo va marketing", "ru": "Продажи и маркетинг", "en": "Sales & marketing"},
    },
    {
        "id": "spec:7",
        "key": "agriculture",
        "labels": {"uz": "Qishloq xo'jaligi", "ru": "Сельское хозяйство", "en": "Agriculture"},
    },
    {
        "id": "spec:12",
        "key": "it",
        "labels": {"uz": "Axborot texnologiyalari", "ru": "Информационные технологии", "en": "Information technology"},
    },
    {
        "id": "spec:42",
        "key": "education_culture_sport",
        "labels": {
            "uz": "Ta'lim, madaniyat, sport",
            "ru": "Образование, культура, спорт",
            "en": "Education, culture, sport",
        },
    },
    {
        "id": "spec:36",
        "key": "transport",
        "labels": {"uz": "Transport", "ru": "Транспорт", "en": "Transport"},
    },
    {
        "id": "spec:1",
        "key": "finance_management",
        "labels": {
            "uz": "Moliya, iqtisod, boshqaruv",
            "ru": "Финансы, экономика, управление",
            "en": "Finance, economics, management",
        },
    },
    {
        "id": "spec:21",
        "key": "industry",
        "labels": {"uz": "Sanoat va ishlab chiqarish", "ru": "Промышленность и производство", "en": "Industry & manufacturing"},
    },
    {
        "id": "spec:48",
        "key": "services",
        "labels": {"uz": "Xizmatlar", "ru": "Услуги", "en": "Services"},
    },
)


# Salary phrasing. The scraper renders Uzbek text; the API re-renders it per language.
_SALARY_STRINGS: dict[str, dict[str, str]] = {
    "uz": {
        "range": "{min} – {max} so'm",
        "from": "{min} so'mdan",
        "negotiable": "Kelishiladi",
        "pro_locked": "🔒 Pro",
    },
    "ru": {
        "range": "{min} – {max} сум",
        "from": "от {min} сум",
        "negotiable": "Договорная",
        "pro_locked": "🔒 Pro",
    },
    "en": {
        "range": "{min} – {max} UZS",
        "from": "from {min} UZS",
        "negotiable": "Negotiable",
        "pro_locked": "🔒 Pro",
    },
}

_NUMBER_RE = re.compile(r"\d[\d\s ,]*\d|\d")


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def salary_strings(lang: str) -> dict[str, str]:
    return _SALARY_STRINGS.get(lang) or _SALARY_STRINGS[DEFAULT_LANG]


def format_salary(min_salary: int | None, max_salary: int | None, lang: str) -> str:
    strings = salary_strings(lang)
    if min_salary and max_salary:
        return strings["range"].format(min=_fmt_int(min_salary), max=_fmt_int(max_salary))
    if min_salary:
        return strings["from"].format(min=_fmt_int(min_salary))
    return strings["negotiable"]


def localize_salary_text(raw: str | None, lang: str) -> str:
    """Re-render an Uzbek salary string (produced by the scraper) in ``lang``."""
    text = str(raw or "").strip()
    if not text:
        return salary_strings(lang)["negotiable"]
    numbers: list[int] = []
    for match in _NUMBER_RE.findall(text):
        digits = re.sub(r"\D", "", match)
        if digits:
            numbers.append(int(digits))
    if not numbers:
        return salary_strings(lang)["negotiable"]
    if len(numbers) >= 2:
        return format_salary(numbers[0], numbers[1], lang)
    return format_salary(numbers[0], None, lang)


def pro_locked_salary(lang: str) -> str:
    return salary_strings(lang)["pro_locked"]
