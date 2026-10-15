"""
Vakansiya matnini formatlash — bot va API uchun yagona manba.

Ommaviy API (webapp ham ishlatadi):
    normalize_vacancy_detail(uid, detail, lang="uz") -> dict
    format_vacancy_message_html(uid, detail, lang="uz", compact=False) -> str

`normalize_vacancy_detail` lokalizatsiya qilingan yorliqlar bilan birga
`codes` kalitini ham qaytaradi — u yerda xom butun kodlar (yoki None) turadi.
"""
from __future__ import annotations

import html
import re
from typing import Any

from config import BOT_USERNAME
from src.i18n import DEFAULT_LANG, t
from src.ui.emoji import e as _icon

_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_NL_RE = re.compile(r"\n{3,}")

#: Telegram rejects a message whose text is longer than this *after* entity
#: parsing (tags stripped, entities decoded), counted in UTF-16 code units.
TELEGRAM_TEXT_LIMIT = 4096
_ELLIPSIS = "..."
#: A title longer than this (UTF-16 units) is clipped before layout.
_MAX_TITLE = 512

# Kod -> i18n kalit prefiksi
_CODE_NAMESPACES = {
    "gender": "vacancy.gender",
    "work_type": "vacancy.work_type",
    "busyness_type": "vacancy.busyness",
    "payment_type": "vacancy.payment",
    "education": "vacancy.education",
    "experience": "vacancy.experience",
}

# Detaldagi xom maydon nomlari
_CODE_SOURCE_FIELDS = {
    "gender": ("gender",),
    "work_type": ("work_type",),
    "busyness_type": ("busyness_type",),
    "payment_type": ("payment_type",),
    "education": ("min_education", "education"),
    "experience": ("work_experiance", "work_experience", "experience"),
}


def _uz_map(namespace: str, codes: range) -> dict[int, str]:
    return {code: t(DEFAULT_LANG, f"{namespace}.{code}") for code in codes}


# Backward-compat: eski importlar uchun o'zbekcha lug'atlar.
GENDER_MAP = _uz_map("vacancy.gender", range(1, 4))
WORK_TYPE_MAP = _uz_map("vacancy.work_type", range(1, 4))
BUSYNESS_TYPE_MAP = _uz_map("vacancy.busyness", range(1, 3))
PAYMENT_TYPE_MAP = _uz_map("vacancy.payment", range(1, 5))
EDUCATION_MAP = _uz_map("vacancy.education", range(1, 5))
EXPERIENCE_MAP = _uz_map("vacancy.experience", range(1, 5))


def normalize_uid(uid: Any) -> str:
    """Eski vakansiya UID larini joriy `osonish_<id>` shakliga keltiradi."""
    value = str(uid or "").strip()
    if value.startswith("osonish_"):
        return value
    if value.startswith("ishapi_"):
        value = value[len("ishapi_"):]
    if value.isdigit():
        return f"osonish_{value}"
    return value


def _to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _fmt_amount(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _label_for_code(namespace: str, code: int | None, lang: str) -> str:
    if code is None:
        return ""
    key = f"{namespace}.{code}"
    label = t(lang, key)
    if label == key:
        return t(lang, "vacancy.code_unknown", code=code)
    return label


def _map_code(value: Any, mapping: dict[int, str]) -> str:
    """Eski yordamchi — o'zbekcha lug'atlar bilan ishlaydi (backward-compat)."""
    ivalue = _to_int(value)
    if ivalue is None:
        return ""
    return mapping.get(ivalue, t(DEFAULT_LANG, "vacancy.code_unknown", code=ivalue))


def clean_html_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value
    text = re.sub(r"<\s*br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<\s*/\s*(p|div|li|ul|ol|h[1-6])\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<\s*li\b[^>]*>", "- ", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = text.replace("\r", "")
    text = _MULTI_NL_RE.sub("\n\n", text)
    return text.strip()


def format_salary(
    min_salary: Any, max_salary: Any, lang: str = DEFAULT_LANG, allow_unspecified: bool = False
) -> str:
    """Maosh matnini tanlangan tilda qaytaradi."""
    min_val = _to_int(min_salary)
    max_val = _to_int(max_salary)

    if min_val and max_val:
        return t(lang, "vacancy.salary.range", min=_fmt_amount(min_val), max=_fmt_amount(max_val))
    if max_val:
        return t(lang, "vacancy.salary.upto", max=_fmt_amount(max_val))
    if min_val:
        return t(lang, "vacancy.salary.from", min=_fmt_amount(min_val))
    if allow_unspecified:
        return t(lang, "vacancy.salary.unspecified")
    return t(lang, "vacancy.salary.negotiable")


def extract_codes(detail: dict[str, Any]) -> dict[str, int | None]:
    """Xom butun kodlarni ajratib oladi (frontend o'z lug'atini ishlatishi uchun)."""
    codes: dict[str, int | None] = {}
    for name, fields in _CODE_SOURCE_FIELDS.items():
        value: int | None = None
        for field in fields:
            value = _to_int(detail.get(field))
            if value is not None:
                break
        codes[name] = value
    return codes


def normalize_vacancy_detail(
    uid: str, detail: dict[str, Any], lang: str = DEFAULT_LANG
) -> dict[str, Any]:
    company_obj = detail.get("company") if isinstance(detail.get("company"), dict) else {}
    district_obj = detail.get("soato_district") if isinstance(detail.get("soato_district"), dict) else {}
    region_obj = detail.get("soato_region") if isinstance(detail.get("soato_region"), dict) else {}
    hr_obj = detail.get("hr") if isinstance(detail.get("hr"), dict) else {}

    salary = format_salary(detail.get("min_salary"), detail.get("max_salary"), lang)

    district = str(district_obj.get("name_uz") or district_obj.get("name") or "").strip()
    region = str(region_obj.get("name_uz") or region_obj.get("name") or "").strip()
    address = str(detail.get("address") or "").strip() or ", ".join([v for v in [district, region] if v])

    codes = extract_codes(detail)

    return {
        "uid": uid,
        "title": str(detail.get("title") or t(lang, "vacancy.title_fallback")).strip(),
        "company": str(company_obj.get("name") or detail.get("company_name") or "").strip(),
        "salary": salary,
        "address": address,
        "district": district,
        "region": region,
        "work_type": _label_for_code(_CODE_NAMESPACES["work_type"], codes["work_type"], lang),
        "busyness_type": _label_for_code(
            _CODE_NAMESPACES["busyness_type"], codes["busyness_type"], lang
        ),
        "payment_type": _label_for_code(
            _CODE_NAMESPACES["payment_type"], codes["payment_type"], lang
        ),
        "education": _label_for_code(_CODE_NAMESPACES["education"], codes["education"], lang),
        "experience": _label_for_code(_CODE_NAMESPACES["experience"], codes["experience"], lang),
        "gender": _label_for_code(_CODE_NAMESPACES["gender"], codes["gender"], lang),
        "count": str(detail.get("count") or "").strip(),
        "working_hours": " - ".join(
            [
                part
                for part in [
                    str(detail.get("working_time_from") or "").strip(),
                    str(detail.get("working_time_to") or "").strip(),
                ]
                if part
            ]
        ),
        "posted_at": str(detail.get("created_at") or "").strip()[:10],
        "deadline": str(detail.get("end_date") or detail.get("deadline") or "").strip()[:10],
        "description": clean_html_text(
            detail.get("info") or detail.get("description") or detail.get("requirements")
        ),
        "hr_name": str(hr_obj.get("name") or hr_obj.get("full_name") or "").strip(),
        "hr_phone": str(hr_obj.get("phone") or detail.get("phone") or "").strip(),
        "hr_email": str(hr_obj.get("email") or detail.get("email") or "").strip(),
        "source_url": f"https://osonish.uz/vacancies/{uid.replace('osonish_', '')}",
        "codes": codes,
    }


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=False)


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def visible_length(html_text: str) -> int:
    """Length Telegram checks against ``TELEGRAM_TEXT_LIMIT`` for an HTML message."""
    return _utf16_len(html.unescape(_TAG_RE.sub("", html_text)))


def _fit_telegram(html_text: str) -> str:
    """Last resort: a message still over the limit (huge company/address...)
    is sent as clipped plain text, which is always valid HTML."""
    if visible_length(html_text) <= TELEGRAM_TEXT_LIMIT:
        return html_text
    plain = html.unescape(_TAG_RE.sub("", html_text))
    return _esc(_clip_utf16(plain, TELEGRAM_TEXT_LIMIT))


def _clip_utf16(text: str, budget: int) -> str:
    """``text`` cut to at most ``budget`` UTF-16 units, ellipsis included."""
    if _utf16_len(text) <= budget:
        return text
    limit = budget - len(_ELLIPSIS)
    if limit <= 0:
        return ""
    kept: list[str] = []
    used = 0
    for char in text:
        width = 2 if ord(char) > 0xFFFF else 1
        if used + width > limit:
            break
        kept.append(char)
        used += width
    clipped = "".join(kept).rstrip()
    return clipped + _ELLIPSIS if clipped else ""


def vacancy_deeplink(uid: str) -> str:
    """``t.me`` link that opens the vacancy card in the bot (``/start vacancy_<uid>``)."""
    return f"https://t.me/{BOT_USERNAME}?start=vacancy_{uid}"


def format_vacancy_message_html(
    uid: str,
    detail: dict[str, Any],
    lang: str = DEFAULT_LANG,
    compact: bool = False,
    plain: bool = False,
) -> str:
    """Telegram HTML xabari. `compact=True` — bildirishnoma uchun qisqa variant.

    ``plain=True`` writes plain fallback emoji instead of premium custom emoji:
    mandatory for CHANNEL posts (custom emoji only work in private/group chats
    for this bot).
    """
    normalized = normalize_vacancy_detail(uid, detail, lang)
    normalized["title"] = _clip_utf16(normalized["title"], _MAX_TITLE)

    def esc(key: str) -> str:
        return _esc(normalized.get(key, ""))

    def ic(key: str) -> str:
        return _icon(key, plain=plain)

    if compact:
        lines = [t(lang, "notify.header", plain_emoji=plain), ""]
        lines.append(f"{ic('position')} <b>{esc('title')}</b>")
        if normalized.get("company"):
            lines.append(f"{ic('company')} {esc('company')}")
        lines.append(f"{ic('salary')} {esc('salary')}")
        location = normalized.get("region") or normalized.get("address")
        if location:
            lines.append(f"{ic('location')} {_esc(location)}")
        lines.append(
            f"\n{ic('link')} <a href=\"{_esc(vacancy_deeplink(uid))}\">{_esc(t(lang, 'notify.details'))}</a>"
        )
        return _fit_telegram("\n".join(lines))

    lines: list[str] = [f"{ic('job')} <b>{esc('title')}</b>"]

    field_rows = (
        ("address", "location", "vacancy.label.address"),
        ("work_type", "work_type", "vacancy.label.work_type"),
        ("busyness_type", "busyness", "vacancy.label.busyness"),
        ("payment_type", "payment", "vacancy.label.payment"),
        ("education", "education", "vacancy.label.education"),
        ("experience", "experience", "vacancy.label.experience"),
        ("gender", "gender", "vacancy.label.gender"),
        ("count", "count", "vacancy.label.count"),
        ("working_hours", "hours", "vacancy.label.hours"),
        ("posted_at", "calendar", "vacancy.label.posted"),
        ("deadline", "deadline", "vacancy.label.deadline"),
    )

    if normalized.get("company"):
        lines.append(f"{ic('company')} <b>{_esc(t(lang, 'vacancy.label.company'))}:</b> {esc('company')}")
    lines.append(f"{ic('salary')} <b>{_esc(t(lang, 'vacancy.label.salary'))}:</b> {esc('salary')}")

    for field, icon, label_key in field_rows:
        if normalized.get(field):
            lines.append(f"{ic(icon)} <b>{_esc(t(lang, label_key))}:</b> {esc(field)}")

    tail: list[str] = []
    contacts: list[str] = []
    if normalized.get("hr_name"):
        contacts.append(esc("hr_name"))
    if normalized.get("hr_phone"):
        contacts.append(f"{_esc(t(lang, 'vacancy.label.phone'))}: {esc('hr_phone')}")
    if normalized.get("hr_email"):
        contacts.append(f"{_esc(t(lang, 'vacancy.label.email'))}: {esc('hr_email')}")
    if contacts:
        tail.append(f"\n{ic('phone')} <b>{_esc(t(lang, 'vacancy.label.contacts'))}:</b>\n" + "\n".join(contacts))

    tail.append("\n────────────────────")
    tail.append(
        f"{ic('bot')} <b>{_esc(t(lang, 'vacancy.label.source'))}:</b> @{_esc(BOT_USERNAME)}"
    )

    if normalized.get("description"):
        # The description is the only unbounded part: it gets whatever the
        # rest of the message leaves of Telegram's limit.
        header = f"\n{ic('description')} <b>{_esc(t(lang, 'vacancy.label.description'))}:</b>\n"
        budget = TELEGRAM_TEXT_LIMIT - visible_length("\n".join([*lines, header, *tail]))
        desc = _clip_utf16(normalized["description"], budget)
        if desc:
            lines.append(header + _esc(desc))

    return _fit_telegram("\n".join([*lines, *tail]))
