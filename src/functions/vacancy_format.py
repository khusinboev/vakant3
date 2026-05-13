import html
import re
from typing import Any


_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_NL_RE = re.compile(r"\n{3,}")

GENDER_MAP = {
    1: "Erkak",
    2: "Ayol",
    3: "Farqi yo'q",
}

WORK_TYPE_MAP = {
    1: "Doimiy ish",
    2: "Vaqtinchalik ish",
    3: "Mavsumiy ish",
}

BUSYNESS_TYPE_MAP = {
    1: "To'liq bandlik",
    2: "Qisman bandlik",
}

PAYMENT_TYPE_MAP = {
    1: "Oylik",
    2: "Kunlik",
    3: "Soatbay",
    4: "Ishbay",
}

EDUCATION_MAP = {
    1: "Umumiy o'rta",
    2: "O'rta maxsus",
    3: "Bakalavr",
    4: "Magistr",
}

EXPERIENCE_MAP = {
    1: "Tajriba talab etilmaydi",
    2: "1 yilgacha",
    3: "1-3 yil",
    4: "3+ yil",
}


def _to_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _map_code(value: Any, mapping: dict[int, str]) -> str:
    ivalue = _to_int(value)
    if ivalue is None:
        return ""
    return mapping.get(ivalue, f"Kod {ivalue}")


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


def normalize_vacancy_detail(uid: str, detail: dict[str, Any]) -> dict[str, str]:
    company_obj = detail.get("company") if isinstance(detail.get("company"), dict) else {}
    district_obj = detail.get("soato_district") if isinstance(detail.get("soato_district"), dict) else {}
    region_obj = detail.get("soato_region") if isinstance(detail.get("soato_region"), dict) else {}
    hr_obj = detail.get("hr") if isinstance(detail.get("hr"), dict) else {}

    min_salary = _to_int(detail.get("min_salary"))
    max_salary = _to_int(detail.get("max_salary"))
    if min_salary and max_salary:
        salary = f"{min_salary:,} - {max_salary:,} so'm".replace(",", " ")
    elif min_salary:
        salary = f"{min_salary:,} so'mdan".replace(",", " ")
    else:
        salary = "Kelishiladi"

    district = str(district_obj.get("name_uz") or district_obj.get("name") or "").strip()
    region = str(region_obj.get("name_uz") or region_obj.get("name") or "").strip()
    address = str(detail.get("address") or "").strip() or ", ".join([v for v in [district, region] if v])

    return {
        "uid": uid,
        "title": str(detail.get("title") or "Vakansiya").strip(),
        "company": str(company_obj.get("name") or detail.get("company_name") or "").strip(),
        "salary": salary,
        "address": address,
        "district": district,
        "region": region,
        "work_type": _map_code(detail.get("work_type"), WORK_TYPE_MAP),
        "busyness_type": _map_code(detail.get("busyness_type"), BUSYNESS_TYPE_MAP),
        "payment_type": _map_code(detail.get("payment_type"), PAYMENT_TYPE_MAP),
        "education": _map_code(detail.get("min_education"), EDUCATION_MAP),
        "experience": _map_code(detail.get("work_experiance"), EXPERIENCE_MAP),
        "gender": _map_code(detail.get("gender"), GENDER_MAP),
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
        "description": clean_html_text(detail.get("info") or detail.get("description") or detail.get("requirements")),
        "hr_name": str(hr_obj.get("name") or hr_obj.get("full_name") or "").strip(),
        "hr_phone": str(hr_obj.get("phone") or detail.get("phone") or "").strip(),
        "hr_email": str(hr_obj.get("email") or detail.get("email") or "").strip(),
        "source_url": f"https://osonish.uz/vacancies/{uid.replace('osonish_', '')}",
    }


def format_vacancy_message_html(uid: str, detail: dict[str, Any]) -> str:
    normalized = normalize_vacancy_detail(uid, detail)

    def esc(key: str) -> str:
        return html.escape(normalized.get(key, ""), quote=False)

    lines: list[str] = [f"<b>{esc('title')}</b>"]
    if normalized.get("company"):
        lines.append(f"Tashkilot: {esc('company')}")
    lines.append(f"Maosh: {esc('salary')}")
    if normalized.get("address"):
        lines.append(f"Manzil: {esc('address')}")
    if normalized.get("work_type"):
        lines.append(f"Ish turi: {esc('work_type')}")
    if normalized.get("busyness_type"):
        lines.append(f"Bandlik: {esc('busyness_type')}")
    if normalized.get("payment_type"):
        lines.append(f"To'lov turi: {esc('payment_type')}")
    if normalized.get("education"):
        lines.append(f"Ta'lim: {esc('education')}")
    if normalized.get("experience"):
        lines.append(f"Tajriba: {esc('experience')}")
    if normalized.get("gender"):
        lines.append(f"Jins: {esc('gender')}")
    if normalized.get("count"):
        lines.append(f"O'rinlar soni: {esc('count')}")
    if normalized.get("working_hours"):
        lines.append(f"Ish vaqti: {esc('working_hours')}")
    if normalized.get("posted_at"):
        lines.append(f"E'lon sanasi: {esc('posted_at')}")
    if normalized.get("deadline"):
        lines.append(f"Muddati: {esc('deadline')}")

    if normalized.get("description"):
        desc = normalized["description"]
        if len(desc) > 3500:
            desc = desc[:3500].rstrip() + "..."
        lines.append(f"\n<b>Tavsif:</b>\n{html.escape(desc, quote=False)}")

    contacts: list[str] = []
    if normalized.get("hr_name"):
        contacts.append(esc("hr_name"))
    if normalized.get("hr_phone"):
        contacts.append(f"Tel: {esc('hr_phone')}")
    if normalized.get("hr_email"):
        contacts.append(f"Email: {esc('hr_email')}")
    if contacts:
        lines.append("\n<b>Aloqa:</b>\n" + "\n".join(contacts))

    lines.append(f"\n<a href='{html.escape(normalized['source_url'], quote=True)}'>Osonish sahifasi</a>")
    return "\n".join(lines)