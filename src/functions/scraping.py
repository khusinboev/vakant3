import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import aiohttp

from src.functions.vacancy_format import format_salary
from src.i18n import DEFAULT_LANG

logger = logging.getLogger(__name__)

OSONISH_BASE = "https://osonish.uz/api/v1"
OSONISH_TIMEOUT_SECONDS = 15

#: Largest vacancy id we accept from a client: JSON numbers stay exact up to
#: 2**53, and it keeps ``saves.save_id`` well inside SQLite's INTEGER range.
MAX_OSONISH_ID = 2**53
_UID_PREFIX = "osonish_"


def parse_osonish_uid(uid: str) -> int | None:
    """``"osonish_<id>"`` -> ``id`` for 1 <= id <= 2**53, else ``None``.

    Strict: plain ASCII digits only (no sign, spaces, underscores or leading
    zeros), so one vacancy has exactly one uid.
    """
    if not isinstance(uid, str) or not uid.startswith(_UID_PREFIX):
        return None
    digits = uid[len(_UID_PREFIX):]
    if not (0 < len(digits) <= 16) or not digits.isascii() or not digits.isdigit() or digits[0] == "0":
        return None
    value = int(digits)
    return value if value <= MAX_OSONISH_ID else None


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


class UpstreamError(Exception):
    """osonish.uz could not answer: transport error, timeout, non-200 or a malformed body.

    Distinct from a genuine empty result (an empty list, or a 404 for a detail):
    callers must never cache anything derived from this.
    """

    def __init__(self, reason: str, status: int | None = None) -> None:
        super().__init__(f"{reason} (status={status})" if status is not None else reason)
        self.reason = reason
        self.status = status


async def request_json(
    url: str,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
) -> tuple[int, Any]:
    """GET ``url`` and return ``(status, body)``.

    Raises ``UpstreamError`` on a transport failure or timeout, and on a 200
    whose body is not JSON. A non-200 status is returned (body ``None``) so the
    caller decides what it means (a detail 404 is "not found", not an outage).
    """
    req_headers = headers or _osonish_headers()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                headers=req_headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=OSONISH_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status != 200:
                    return resp.status, None
                try:
                    return 200, await resp.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError) as exc:
                    raise UpstreamError("invalid_json", 200) from exc
    except UpstreamError:
        raise
    except Exception as exc:  # aiohttp.ClientError, asyncio.TimeoutError, OSError
        raise UpstreamError(f"transport: {type(exc).__name__}: {exc}") from exc


async def fetch_json(
    url: str,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
) -> Optional[dict[str, Any]]:
    """Lenient variant for best-effort callers (bot region seeding): ``None`` on any failure."""
    try:
        status, data = await request_json(url, params=params, headers=headers)
    except UpstreamError as exc:
        logger.error("fetch_json_exception url=%s error=%s", url, exc)
        return None
    if status != 200:
        logger.error("fetch_json_http_error url=%s status=%s", url, status)
        return None
    if isinstance(data, dict):
        return data
    logger.error("fetch_json_invalid_type url=%s type=%s", url, type(data).__name__)
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

    status, payload = await request_json(f"{OSONISH_BASE}/vacancies", params=params, headers=_osonish_headers())
    if status != 200:
        raise UpstreamError("http_status", status)

    data_block = payload.get("data") if isinstance(payload, dict) else None
    items = data_block.get("data") if isinstance(data_block, dict) else None
    if not isinstance(items, list):
        # A real "no results" is ``{"data": {"data": [], ...}}``; anything else
        # is a broken answer and must not be served (or cached) as empty.
        raise UpstreamError("invalid_payload", status)

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

    return vacancies, _last_page(data_block)


def _last_page(data_block: dict[str, Any]) -> int:
    try:
        return max(1, int(data_block.get("last_page") or 1))
    except (TypeError, ValueError):
        return 1


async def get_osonish_detail(vacancy_id: int) -> Optional[dict[str, Any]]:
    """The vacancy, ``None`` when osonish says it does not exist, ``UpstreamError`` on an outage."""
    status, payload = await request_json(f"{OSONISH_BASE}/vacancies/{vacancy_id}", headers=_osonish_headers())
    if status == 404:
        return None
    if status != 200 or not isinstance(payload, dict):
        raise UpstreamError("http_status" if status != 200 else "invalid_payload", status)
    data = payload.get("data")
    # A 200 without a vacancy object is osonish's other way of saying "gone".
    return data if isinstance(data, dict) else None


async def fetch_osonish_detail(vacancy_id: int) -> Optional[dict[str, Any]]:
    """Lenient variant for the bot (deeplink, auto-post): ``None`` on not-found *and* on an outage."""
    try:
        return await get_osonish_detail(vacancy_id)
    except UpstreamError as exc:
        logger.error("osonish_detail_failed id=%s error=%s", vacancy_id, exc)
        return None
