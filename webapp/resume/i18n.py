"""Localized strings for generated resumes (uz / ru / en).

Everything the PDF renderers print that is not user data lives here: section
headings, month names and the fallbacks used when a field is empty.
DejaVu Sans (the embedded font) covers Cyrillic, so ru renders correctly.
"""

from webapp.core.i18n import DEFAULT_LANG, normalize_lang

MONTHS: dict[str, list[str]] = {
    "uz": [
        "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
        "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
    ],
    "ru": [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ],
    "en": [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ],
}

STRINGS: dict[str, dict[str, str]] = {
    "uz": {
        "summary": "Qisqacha",
        "about": "Haqida",
        "summary_pro": "Professional xulosa",
        "experience": "Ish tajribasi",
        "experience_alt": "Tajriba",
        "education": "Ta'lim",
        "skills": "Ko'nikmalar",
        "skills_alt": "Asosiy ko'nikmalar",
        "languages": "Tillar",
        "contact": "Aloqa",
        "photo": "RASM",
        "default_name": "Nomzod",
        "default_role": "Lavozim",
        "default_education": "Ta'lim",
        "unnamed": "Nomsiz nomzod",
        "caption": "Rezyumengiz tayyor. Faylni yuklab olishingiz mumkin.",
        "present": "Hozir",
    },
    "ru": {
        "summary": "Кратко",
        "about": "Обо мне",
        "summary_pro": "Профессиональное резюме",
        "experience": "Опыт работы",
        "experience_alt": "Опыт",
        "education": "Образование",
        "skills": "Навыки",
        "skills_alt": "Ключевые навыки",
        "languages": "Языки",
        "contact": "Контакты",
        "photo": "ФОТО",
        "default_name": "Кандидат",
        "default_role": "Должность",
        "default_education": "Образование",
        "unnamed": "Без имени",
        "caption": "Ваше резюме готово. Файл можно скачать.",
        "present": "Настоящее время",
    },
    "en": {
        "summary": "Summary",
        "about": "About",
        "summary_pro": "Professional Summary",
        "experience": "Work Experience",
        "experience_alt": "Experience",
        "education": "Education",
        "skills": "Skills",
        "skills_alt": "Core Competencies",
        "languages": "Languages",
        "contact": "Contact",
        "photo": "PHOTO",
        "default_name": "Candidate",
        "default_role": "Position",
        "default_education": "Education",
        "unnamed": "Unnamed candidate",
        "caption": "Your resume is ready. You can download the file.",
        "present": "Present",
    },
}

# Date tokens that mean "until now" and are passed through unchanged.
PRESENT_TOKENS = {"hozir", "present", "now", "сейчас", "по настоящее время", "настоящее время"}


def strings(lang: str | None) -> dict[str, str]:
    return STRINGS.get(normalize_lang(lang), STRINGS[DEFAULT_LANG])


def t(lang: str | None, key: str) -> str:
    table = strings(lang)
    return table.get(key) or STRINGS[DEFAULT_LANG].get(key, key)


def month_name(index: int, lang: str | None) -> str:
    months = MONTHS.get(normalize_lang(lang), MONTHS[DEFAULT_LANG])
    return months[index]


def fmt_date(raw: str, lang: str = DEFAULT_LANG) -> str:
    """Convert '05/2023' to 'May 2023' in ``lang``; '2023' and 'Hozir' pass through."""
    if not raw:
        return ""
    stripped = str(raw).strip()
    if stripped.lower() in PRESENT_TOKENS:
        return stripped
    parts = stripped.split("/")
    if len(parts) == 2:
        m_str, y_str = parts
        try:
            m_idx = int(m_str) - 1
            if 0 <= m_idx < 12:
                return f"{month_name(m_idx, lang)} {y_str}"
        except ValueError:
            pass
    return stripped


def fmt_period(start: str, end: str, lang: str = DEFAULT_LANG) -> str:
    parts = [x for x in [fmt_date(start or "", lang), fmt_date(end or "", lang)] if x]
    return " – ".join(parts)
