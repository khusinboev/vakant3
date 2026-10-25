"""vacancy.gov.uz adapter: the single open portal of civil-service vacancies.

Access method: the portal is an Angular SPA whose own public pages call an
anonymous JSON API on the same host (no key, no login, no cookies):

* ``POST /api/Vacancy/HRMVacancy/GetHRMVacancyList`` with ``{"page": n, "pageSize": 40}``
  -> ``{"count", "next", "previous", "results": [...]}``. Pages are 0-based, the
  server caps ``pageSize`` at 40, and results are ordered by ``date_start`` (the
  start of the current 10-day announcement window) newest first.
* ``POST /api/Vacancy/HRMVacancy/GetHRMVacancyDetail?id=<id>&isView=false``
  -> the full item (duties, requirements, conditions, institution contacts);
  404 for an unknown id. ``isView=false`` keeps our re-checks out of the portal's
  public view counter. An expired vacancy still answers 200 with a past
  ``date_stop``, so openness is derived from ``is_published`` and ``date_stop``.

The site publishes no ``robots.txt`` (the path falls back to the SPA shell) and
no terms of use that restrict reading; the list is the same data every
visitor sees. Requests stay at 1 per second with an identifying User-Agent.

Incremental: the cursor is ``"<newest date_start>:<last full sweep>"``. A run
walks pages newest first until a whole page is older than the cursor minus one
day. Within one ``date_start`` day the server order is unspecified, so once per
day (``FULL_SWEEP_SECONDS``) the run walks the whole list instead; that also
re-confirms every open vacancy for the runner's stale-close rule.

Failure handling: ``SourceError`` for anything unexpected (403, HTML instead of
JSON, a changed payload shape); after ``BREAKER_THRESHOLD`` consecutive failed
requests ``enabled()`` turns false for ``BREAKER_PAUSE_SECONDS``, so a blocked
or redesigned portal costs a few requests, not a request storm.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Mapping, Optional

import aiohttp

from src.ingest.base import Batch, NormalizedVacancy, RateLimiter, SourceError, new_stats, parse_ts
from src.ingest.categories import vacancy_gov_category
from src.ingest.regions import REGION_SOATO
from src.ingest.text import clean_line, html_to_text

logger = logging.getLogger(__name__)

BASE_URL = "https://vacancy.gov.uz"
LIST_PATH = "/api/Vacancy/HRMVacancy/GetHRMVacancyList"
DETAIL_PATH = "/api/Vacancy/HRMVacancy/GetHRMVacancyDetail"
VACANCY_URL = BASE_URL + "/hrm-vacancy-detail/{id}"
DEFAULT_USER_AGENT = "BandlikUZ/1.0 (+https://abitur24.uz)"
PAGE_SIZE = 40
TIMEOUT_SECONDS = 25
OVERLAP_SECONDS = 86_400
FULL_SWEEP_SECONDS = 86_400
MAX_BACKOFF_SECONDS = 60.0
BREAKER_THRESHOLD = 3
BREAKER_PAUSE_SECONDS = 6 * 3600


@dataclass
class HttpResponse:
    status: int
    body: Any
    headers: Mapping[str, str]


Transport = Callable[[str, str, dict[str, Any], Optional[dict[str, Any]], dict[str, str]], Awaitable[HttpResponse]]


async def aiohttp_transport(
    method: str, url: str, params: dict[str, Any], json_body: Optional[dict[str, Any]], headers: dict[str, str]
) -> HttpResponse:
    async with aiohttp.ClientSession() as session:
        async with session.request(
            method, url, params=params or None, json=json_body, headers=headers,
            timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS),
        ) as resp:
            body: Any = None
            try:
                body = await resp.json(content_type=None)
            except (ValueError, aiohttp.ContentTypeError):
                body = None  # an HTML page or an empty body: the caller treats it as a broken payload
            return HttpResponse(resp.status, body, dict(resp.headers))


def enabled_from_env() -> bool:
    return (os.getenv("VACANCY_GOV_ENABLED") or "1").strip().lower() not in ("0", "false", "no", "off")


def user_agent_from_env() -> str:
    return (os.getenv("VACANCY_GOV_USER_AGENT") or "").strip() or DEFAULT_USER_AGENT


def _retry_after(headers: Mapping[str, str]) -> Optional[float]:
    for key, value in headers.items():
        if key.lower() == "retry-after":
            try:
                return max(0.0, min(float(value), MAX_BACKOFF_SECONDS))
            except (TypeError, ValueError):
                return None
    return None


# ------------------------------------------------------------------ regions

_APOSTROPHES = re.compile("[‘’ʻʼ`´]")

#: Province stems, Latin then Cyrillic spelling (the portal mixes both).
_REGION_STEMS: tuple[tuple[str, str], ...] = (
    ("qoraqalpog", "1735"), ("қорақалпоғ", "1735"), ("каракалпак", "1735"),
    ("andijon", "1703"), ("андижон", "1703"),
    ("buxoro", "1706"), ("бухоро", "1706"),
    ("jizzax", "1708"), ("жиззах", "1708"),
    ("qashqadaryo", "1710"), ("қашқадарё", "1710"),
    ("navoiy", "1712"), ("навоий", "1712"),
    ("namangan", "1714"), ("наманган", "1714"),
    ("samarqand", "1718"), ("самарқанд", "1718"),
    ("surxondaryo", "1722"), ("сурхондарё", "1722"),
    ("sirdaryo", "1724"), ("сирдарё", "1724"),
    ("farg'ona", "1730"), ("фарғона", "1730"),
    ("xorazm", "1733"), ("хоразм", "1733"),
)
_TASHKENT_STEMS = ("toshkent", "тошкент", "ташкент")
_PROVINCE_MARKERS = ("viloyat", "вилоят", "область")


def _norm_name(value: str) -> str:
    return re.sub(r"\s+", " ", _APOSTROPHES.sub("'", value.lower())).strip()


def parse_region(
    value: Any, region_names: Mapping[str, str] | None = None
) -> tuple[Optional[str], str]:
    """``"Namangan viloyati , Yangiqo‘rg‘on tumani"`` -> ``(region_soato, display name)``.

    The part before the first comma is the province; the display name keeps the
    district text. ``region_soato`` is ``None`` when the province is unknown.
    """
    if not isinstance(value, str) or not value.strip():
        return None, ""
    parts = [p.strip() for p in value.split(",") if p.strip()]
    display = clean_line(", ".join(parts), 160)
    if not parts:
        return None, ""
    province = _norm_name(parts[0])
    if any(province.startswith(stem) for stem in _TASHKENT_STEMS):
        is_province = any(marker in province for marker in _PROVINCE_MARKERS)
        return ("1727" if is_province else "1726"), display
    for stem, soato in _REGION_STEMS:
        if stem in province:
            return soato, display
    if region_names:
        found = region_names.get(province) or region_names.get(parts[0].lower())
        if found in REGION_SOATO:
            return found, display
    return None, display


# ------------------------------------------------------------- normalizing


def _dict(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _int_or_none(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _description(item: Mapping[str, Any]) -> str:
    sections = (
        ("Tuzilma", item.get("structure_name")),
        ("Vazifalar", item.get("position_duties")),
        ("Talablar", item.get("position_requirements")),
        ("Shartlar", item.get("position_conditions")),
    )
    lines = []
    for label, raw in sections:
        text = html_to_text(raw)
        if text:
            lines.append(f"{label}: {text}")
    return "\n".join(lines)


def _contacts(item: Mapping[str, Any]) -> dict[str, Any]:
    """Institution contacts only (a public phone/e-mail/address of the employer); never a person's."""
    org = _dict(item.get("organizationFull"))
    phone = clean_line(org.get("phone") or "", 40)
    out = {
        "phones": [phone] if phone else [],
        "email": clean_line(org.get("email") or "", 120),
        "address": clean_line(org.get("mail_address") or "", 200),
    }
    return {k: v for k, v in out.items() if v}


def normalize(
    item: Any, now: int, region_names: Mapping[str, str] | None = None, *, detail: bool = False
) -> Optional[NormalizedVacancy]:
    """List item or detail -> ``NormalizedVacancy`` (``None`` when unusable).

    ``published_at`` is ``date_start``, the start of the current announcement
    window (falls back to ``created``). The vacancy is open while it is
    published and ``date_stop`` is still ahead of ``now``.
    """
    if not isinstance(item, Mapping):
        return None
    raw_id = item.get("id")
    if not isinstance(raw_id, int) or isinstance(raw_id, bool) or raw_id <= 0:
        return None
    title = clean_line(item.get("position_name") or "")
    published = parse_ts(item.get("date_start")) or parse_ts(item.get("created"))
    if not title or published is None:
        return None
    stop = parse_ts(item.get("date_stop"))
    is_open = item.get("is_published") is not False and (stop is None or stop > now)
    region, region_name = parse_region(item.get("region"), region_names)
    salary = _int_or_none(item.get("position_salary"))
    experience = _int_or_none(item.get("experience"))
    position_type = item.get("position_type")
    return NormalizedVacancy(
        source="vacancy_gov",
        source_id=str(raw_id),
        title=title,
        published_at=published,
        employer=clean_line(item.get("organization") or ""),
        salary_min=salary,
        salary_max=None,
        currency="UZS" if salary else None,
        salary_gross=None,
        region_soato=region,
        district_soato=None,
        region_name=region_name,
        category=clean_line(position_type, 120) if isinstance(position_type, str) else "",
        category_id=vacancy_gov_category(item, title),
        experience=str(experience) if experience else "",
        employment="",
        schedule=clean_line(item.get("position_conditions") or "", 120),
        description_text=_description(item),
        contacts=_contacts(item) if detail else {},
        url=VACANCY_URL.format(id=raw_id),
        is_open=is_open,
        raw=dict(item),
    )


# ------------------------------------------------------------------ cursor


def parse_cursor(cursor: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """``"<newest date_start>:<last full sweep>"`` -> ``(newest, last_full)``; garbage -> ``(None, None)``."""
    if not cursor:
        return None, None
    left, _, right = cursor.partition(":")
    if left.isdigit() and right.isdigit():
        return int(left), int(right)
    return None, None


class VacancyGovAdapter:
    name = "vacancy_gov"
    interval_seconds = 1800
    recheck_per_run = 30
    stale_after_seconds = 21 * 86_400

    def __init__(
        self,
        *,
        transport: Transport | None = None,
        user_agent: str | None = None,
        rate: RateLimiter | None = None,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        clock: Callable[[], float] = time.time,
        max_pages: int = 150,
        max_retries: int = 3,
        base_delay: float = 1.0,
        enabled: bool | None = None,
        region_names: Mapping[str, str] | None = None,
    ) -> None:
        self.transport = transport or aiohttp_transport
        self.user_agent = user_agent or user_agent_from_env()
        self.rate = rate or RateLimiter(1.0)
        self.sleep = sleep
        self.clock = clock
        self.max_pages = max_pages
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.region_names: Mapping[str, str] = region_names or {}
        self._switch = enabled_from_env() if enabled is None else enabled
        self._failures = 0
        self._paused_until = 0.0
        self.stats = new_stats()

    # ---- availability

    def enabled(self) -> bool:
        return self._switch and self.clock() >= self._paused_until

    def _record_failure(self, reason: str) -> None:
        self._failures += 1
        if self._failures >= BREAKER_THRESHOLD:
            self._paused_until = self.clock() + BREAKER_PAUSE_SECONDS
            self._failures = 0
            logger.warning("vacancy_gov: %s again; source paused for %d h", reason, BREAKER_PAUSE_SECONDS // 3600)

    # ---- http

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent, "Accept": "application/json", "Content-Type": "application/json"}

    async def _request(self, path: str, params: dict[str, Any], body: Optional[dict[str, Any]]) -> Optional[dict]:
        """JSON object for 200, ``None`` for 404; ``SourceError`` for everything else."""
        attempt = 0
        while True:
            await self.rate.wait()
            self.stats["requests"] += 1
            delay_hint: Optional[float] = None
            status: Optional[int] = None
            try:
                resp = await self.transport("POST", BASE_URL + path, params, body, self._headers())
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                reason = f"transport:{type(exc).__name__}"
            else:
                status = resp.status
                if status == 200:
                    if isinstance(resp.body, dict):
                        self._failures = 0
                        return resp.body
                    self._fail("invalid_payload", status)
                if status == 404:
                    self._failures = 0
                    return None
                if status in (401, 403):
                    self._fail("forbidden", status)
                if status == 429 or status >= 500:
                    reason = "rate_limited" if status == 429 else "server_error"
                    delay_hint = _retry_after(resp.headers)
                else:
                    self._fail("http_status", status)
            if attempt >= self.max_retries:
                self._fail(f"{reason}_retries_exhausted", status)
            delay = delay_hint if delay_hint is not None else min(self.base_delay * (2**attempt), MAX_BACKOFF_SECONDS)
            self.stats["retries"] += 1
            logger.warning("vacancy_gov %s %s, retry %d in %.1fs", path, reason, attempt + 1, delay)
            await self.sleep(delay)
            attempt += 1

    def _fail(self, reason: str, status: Optional[int]) -> None:
        self.stats["errors"] += 1
        self._record_failure(reason)
        raise SourceError(reason, status)

    async def _page(self, page: int) -> tuple[list[Any], int]:
        body = await self._request(LIST_PATH, {}, {"page": page, "pageSize": PAGE_SIZE})
        results = (body or {}).get("results")
        count = (body or {}).get("count")
        if not isinstance(results, list) or isinstance(count, bool) or not isinstance(count, int):
            self._fail("invalid_payload", 200)
        return results, count

    # ---- adapter protocol

    async def iter_new(self, cursor: Optional[str], now: int) -> AsyncIterator[Batch]:
        newest, last_full = parse_cursor(cursor)
        full = newest is None or last_full is None or now - last_full >= FULL_SWEEP_SECONDS
        since = None if full else newest - OVERLAP_SECONDS
        newest = newest or 0
        seen: set[int] = set()
        page = 0
        while page < self.max_pages:
            results, count = await self._page(page)
            batch = []
            for raw in results:
                vacancy = normalize(raw, now, self.region_names)
                if vacancy is None or int(vacancy.source_id) in seen:
                    continue
                seen.add(int(vacancy.source_id))
                batch.append(vacancy)
            self.stats["items"] += len(batch)
            if batch:
                newest = max(newest, max(v.published_at for v in batch))
            exhausted = not results or (page + 1) * PAGE_SIZE >= count
            reached_old = (
                since is not None and bool(batch) and max(v.published_at for v in batch) < since
            )
            done = exhausted or reached_old
            next_cursor = f"{newest}:{now if full else last_full}" if done and newest else None
            yield Batch(batch, next_cursor)
            if done:
                return
            page += 1
        logger.warning("vacancy_gov: stopped at the %d page cap; cursor not advanced", self.max_pages)

    async def fetch_detail(self, source_id: str) -> Optional[NormalizedVacancy]:
        if not source_id.isdigit():
            return None
        body = await self._request(DETAIL_PATH, {"id": source_id, "isView": "false"}, None)
        if body is None:
            return None
        vacancy = normalize(body, int(self.clock()), self.region_names, detail=True)
        if vacancy is None or vacancy.source_id != source_id:
            # A 200 we cannot read must not be mistaken for "the vacancy is gone".
            self._fail("invalid_payload", 200)
        return vacancy
