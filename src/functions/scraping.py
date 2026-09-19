import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import aiohttp

from src.functions.vacancy_format import format_salary
from src.i18n import DEFAULT_LANG

logger = logging.getLogger(__name__)

OSONISH_BASE = "https://osonish.uz/api/v1"


@dataclass
class Vacancy:
    uid: str
    title: str
    company: str
    salary_text: str
    location: str
    district: str
    posted_at: str
    raw_id: int
    max_salary: int = 0
    source: str = "osonish"


def _osonish_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "uz-UZ,uz;q=0.9,en;q=0.8,ru;q=0.7",
        "Referer": "https://osonish.uz/vacancies",
        "X-Requested-With": "XMLHttpRequest",
    }


async def fetch_json(
    url: str,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
) -> Optional[dict[str, Any]]:
    req_headers = headers or _osonish_headers()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                headers=req_headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.error("fetch_json_http_error url=%s status=%s", url, resp.status)
                    return None
                data = await resp.json()
                if isinstance(data, dict):
                    return data
                logger.error("fetch_json_invalid_type url=%s type=%s", url, type(data).__name__)
                return None
    except Exception as e:
        logger.error("fetch_json_exception url=%s error=%s", url, e)
        return None


def _fmt_osonish_salary(min_salary: Any, max_salary: Any, lang: str = DEFAULT_LANG) -> str:
    """Ro'yxat uchun maosh matni — so'ralgan tilda."""
    return format_salary(min_salary, max_salary, lang)


def _fmt_date_ddmmyyyy(value: Any) -> str:
    """Sana yoki bo'sh satr (chaqiruvchi o'zi placeholder qo'yadi)."""
    if not isinstance(value, str) or not value:
        return ""
    dt_value = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(dt_value)
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return value[:10]


async def fetch_osonish_list(
    page: int,
    salary: int,
    soato_region: str,
    soato_district: str = "",
    mmk_group_field_id: int | None = None,
    sort_key: str = "",
    sort_type: str = "",
    search: str = "",
    lang: str = DEFAULT_LANG,
) -> tuple[list[Vacancy], int]:
    params: dict[str, Any] = {
        "page": page,
        "per_page": 10,
    }
    if salary:
        params["min_salary"] = salary
    if soato_region:
        params["soato_region"] = soato_region
    if soato_district:
        params["soato_district"] = soato_district
    if isinstance(mmk_group_field_id, int):
        params["mmk_group_field_id"] = mmk_group_field_id
    if sort_key:
        params["sort_key"] = sort_key
    if sort_type:
        params["sort_type"] = sort_type
    if search:
        params["search"] = search

    payload = await fetch_json(f"{OSONISH_BASE}/vacancies", params=params, headers=_osonish_headers())
    if not payload:
        return [], 1

    data_block = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data_block, dict):
        return [], 1

    items = data_block.get("data")
    if not isinstance(items, list):
        return [], int(data_block.get("last_page") or 1)

    vacancies: list[Vacancy] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        raw_id = item.get("id")
        if not isinstance(raw_id, int):
            continue

        company_obj = item.get("company") if isinstance(item.get("company"), dict) else {}
        district_obj = item.get("soato_district") if isinstance(item.get("soato_district"), dict) else {}
        region_obj = item.get("soato_region") if isinstance(item.get("soato_region"), dict) else {}

        salary_text = _fmt_osonish_salary(item.get("min_salary"), item.get("max_salary"), lang)
        district = district_obj.get("name_uz") or ""
        region = region_obj.get("name_uz") or ""
        location = ", ".join(filter(None, [district, region])) or (item.get("address") or "")

        vacancies.append(
            Vacancy(
                uid=f"osonish_{raw_id}",
                source="osonish",
                title=item.get("title") or "",
                company=company_obj.get("name") or "",
                salary_text=salary_text,
                location=location,
                district=district,
                posted_at=_fmt_date_ddmmyyyy(item.get("created_at")),
                raw_id=raw_id,
                max_salary=int(item.get("max_salary") or 0),
            )
        )

    return vacancies, int(data_block.get("last_page") or 1)


async def fetch_osonish_detail(vacancy_id: int) -> Optional[dict[str, Any]]:
    payload = await fetch_json(f"{OSONISH_BASE}/vacancies/{vacancy_id}", headers=_osonish_headers())
    if not payload:
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, dict) else None
