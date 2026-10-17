"""hh.uz adapter through the official API (https://api.hh.ru, ``host=hh.uz``).

Enabled only when ``HH_APP_TOKEN`` is set (vacancy search answers 403 without
an application token). Requests go out at most ``HH_RATE_PER_SECOND`` per
second; 429 / 5xx / transport errors back off exponentially (``Retry-After``
wins when present); 400 and 401/403 fail fast.

Incremental: the cursor is the end of the last fully processed publication
window (unix seconds). A run searches ``[cursor - overlap, now]`` ordered by
publication time; hh serves at most 2000 results per query, so a window with
``found > 2000`` is split in halves until it fits, and sub-windows are walked
oldest first so the cursor only ever moves forward over completed windows.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Awaitable, Callable, Mapping, Optional
from urllib.parse import urlsplit

import aiohttp

from src.core.timeutil import TZ
from src.ingest.base import Batch, NormalizedVacancy, RateLimiter, SourceError, new_stats, parse_ts
from src.ingest.regions import hh_area_to_region
from src.ingest.text import clean_line, html_to_text

logger = logging.getLogger(__name__)

HH_BASE = "https://api.hh.ru"
HH_HOST = "hh.uz"
HH_AREA_UZBEKISTAN = "97"
DEFAULT_USER_AGENT = "BandlikUZ/1.0 (+https://abitur24.uz)"
PER_PAGE = 100
MAX_RESULTS = 2000
MIN_WINDOW_SECONDS = 600
OVERLAP_SECONDS = 1800
FIRST_RUN_LOOKBACK = 30 * 86_400
TIMEOUT_SECONDS = 20
MAX_BACKOFF_SECONDS = 60.0
_ALLOWED_URL_HOSTS = ("hh.uz", "hh.ru")


@dataclass
class HttpResponse:
    status: int
    body: Any
    headers: Mapping[str, str]


Transport = Callable[[str, dict[str, Any], dict[str, str]], Awaitable[HttpResponse]]


async def aiohttp_transport(url: str, params: dict[str, Any], headers: dict[str, str]) -> HttpResponse:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        ) as resp:
            body: Any = None
            try:
                body = await resp.json(content_type=None)
            except (ValueError, aiohttp.ContentTypeError):
                body = None
            return HttpResponse(resp.status, body, dict(resp.headers))


def token_from_env() -> str:
    return (os.getenv("HH_APP_TOKEN") or "").strip()


def user_agent_from_env() -> str:
    return (os.getenv("HH_USER_AGENT") or "").strip() or DEFAULT_USER_AGENT


def _retry_after(headers: Mapping[str, str]) -> Optional[float]:
    for key, value in headers.items():
        if key.lower() == "retry-after":
            try:
                return max(0.0, min(float(value), MAX_BACKOFF_SECONDS))
            except (TypeError, ValueError):
                return None
    return None


class HHClient:
    def __init__(
        self,
        token: str,
        user_agent: str = DEFAULT_USER_AGENT,
        *,
        transport: Transport | None = None,
        rate: RateLimiter | None = None,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        max_retries: int = 5,
        base_delay: float = 1.0,
        stats: dict[str, int] | None = None,
    ) -> None:
        self.token = token
        self.user_agent = user_agent
        self.transport = transport or aiohttp_transport
        self.rate = rate or RateLimiter(float(os.getenv("HH_RATE_PER_SECOND") or 1.5))
        self.sleep = sleep
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.stats = stats if stats is not None else new_stats()

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "HH-User-Agent": self.user_agent,
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    async def get(self, path: str, params: dict[str, Any]) -> Optional[dict[str, Any]]:
        """JSON object for 200, ``None`` for 404; ``SourceError`` for everything else."""
        query = {"host": HH_HOST, **params}
        attempt = 0
        while True:
            await self.rate.wait()
            self.stats["requests"] += 1
            retry_reason: str
            delay_hint: Optional[float] = None
            status: Optional[int] = None
            try:
                resp = await self.transport(f"{HH_BASE}{path}", query, self._headers())
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                retry_reason = f"transport:{type(exc).__name__}"
            else:
                status = resp.status
                if status == 200:
                    if isinstance(resp.body, dict):
                        return resp.body
                    self.stats["errors"] += 1
                    raise SourceError("invalid_payload", status)
                if status == 404:
                    return None
                if status in (401, 403):
                    self.stats["errors"] += 1
                    raise SourceError("forbidden", status)
                if status == 400:
                    self.stats["errors"] += 1
                    raise SourceError("bad_request", status)
                if status == 429 or status >= 500:
                    retry_reason = "rate_limited" if status == 429 else "server_error"
                    delay_hint = _retry_after(resp.headers)
                else:
                    self.stats["errors"] += 1
                    raise SourceError("http_status", status)
            if attempt >= self.max_retries:
                self.stats["errors"] += 1
                raise SourceError(f"{retry_reason}_retries_exhausted", status)
            delay = delay_hint if delay_hint is not None else min(self.base_delay * (2**attempt), MAX_BACKOFF_SECONDS)
            self.stats["retries"] += 1
            logger.warning("hh %s %s, retry %d in %.1fs", path, retry_reason, attempt + 1, delay)
            await self.sleep(delay)
            attempt += 1

    async def search(self, date_from: int, date_to: int, page: int) -> dict[str, Any]:
        body = await self.get(
            "/vacancies",
            {
                "area": HH_AREA_UZBEKISTAN,
                "per_page": PER_PAGE,
                "page": page,
                "order_by": "publication_time",
                "date_from": _fmt_date(date_from),
                "date_to": _fmt_date(date_to),
            },
        )
        if body is None or not isinstance(body.get("items"), list):
            raise SourceError("invalid_payload", 200 if body is not None else 404)
        return body

    async def vacancy(self, vacancy_id: str) -> Optional[dict[str, Any]]:
        return await self.get(f"/vacancies/{vacancy_id}", {})


def _fmt_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%dT%H:%M:%S%z")


def _int_or_none(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _dict(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _id_of(value: Any) -> str:
    return clean_line(_dict(value).get("id") or "", 40)


def safe_url(value: Any, vacancy_id: str) -> str:
    """``alternate_url`` when it is an https hh link, else the canonical hh.uz vacancy URL."""
    fallback = f"https://{HH_HOST}/vacancy/{vacancy_id}"
    if not isinstance(value, str):
        return fallback
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return fallback
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not any(host == h or host.endswith("." + h) for h in _ALLOWED_URL_HOSTS):
        return fallback
    return value.strip()


def _contacts(value: Any) -> dict[str, Any]:
    data = _dict(value)
    phones = []
    for phone in data.get("phones") or []:
        if not isinstance(phone, Mapping):
            continue
        text = phone.get("formatted") or "".join(
            str(phone.get(k) or "") for k in ("country", "city", "number")
        )
        text = clean_line(text, 40)
        if text:
            phones.append(text)
    out = {
        "name": clean_line(data.get("name") or "", 120),
        "email": clean_line(data.get("email") or "", 120),
        "phones": phones[:5],
    }
    return {k: v for k, v in out.items() if v}


def normalize(item: Any, *, detail: bool = False) -> Optional[NormalizedVacancy]:
    """hh list item or full vacancy -> ``NormalizedVacancy`` (``None`` when unusable)."""
    if not isinstance(item, Mapping):
        return None
    vacancy_id = str(item.get("id") or "").strip()
    if not vacancy_id.isdigit() or len(vacancy_id) > 18:
        return None
    published = parse_ts(item.get("published_at")) or parse_ts(item.get("created_at"))
    title = clean_line(item.get("name") or "")
    if published is None or not title:
        return None
    salary = _dict(item.get("salary")) or _dict(item.get("salary_range"))
    currency = clean_line(salary.get("currency") or "", 5).upper() or None
    if currency == "RUR":
        currency = "RUB"
    area = _dict(item.get("area"))
    if detail:
        description = html_to_text(item.get("description"))
    else:
        snippet = _dict(item.get("snippet"))
        description = "\n".join(
            part for part in (html_to_text(snippet.get("responsibility")), html_to_text(snippet.get("requirement")))
            if part
        )
    skills = [
        clean_line(s.get("name") or "", 80) for s in (item.get("key_skills") or []) if isinstance(s, Mapping)
    ]
    roles = [r for r in (item.get("professional_roles") or []) if isinstance(r, Mapping)]
    gross = salary.get("gross")
    return NormalizedVacancy(
        source="hh",
        source_id=vacancy_id,
        title=title,
        published_at=published,
        employer=clean_line(_dict(item.get("employer")).get("name") or ""),
        salary_min=_int_or_none(salary.get("from")),
        salary_max=_int_or_none(salary.get("to")),
        currency=currency if (salary.get("from") or salary.get("to")) else None,
        salary_gross=gross if isinstance(gross, bool) else None,
        region_soato=hh_area_to_region(area),
        district_soato=None,
        region_name=clean_line(area.get("name") or "", 120),
        category=clean_line(roles[0].get("name") or "", 120) if roles else "",
        experience=_id_of(item.get("experience")),
        employment=_id_of(item.get("employment")),
        schedule=_id_of(item.get("schedule")),
        description_text=description,
        skills=[s for s in skills if s][:30],
        contacts=_contacts(item.get("contacts")) if detail else {},
        url=safe_url(item.get("alternate_url"), vacancy_id),
        is_open=not bool(item.get("archived")),
        raw=dict(item),
    )


class _BudgetExhausted(Exception):
    pass


class HHAdapter:
    name = "hh"
    interval_seconds = 600
    recheck_per_run = 40
    stale_after_seconds = 21 * 86_400

    def __init__(
        self,
        token: str | None = None,
        user_agent: str | None = None,
        *,
        client: HHClient | None = None,
        max_requests_per_run: int = 80,
    ) -> None:
        self.token = token if token is not None else token_from_env()
        self.stats = new_stats()
        self.client = client or HHClient(self.token, user_agent or user_agent_from_env(), stats=self.stats)
        self.client.stats = self.stats
        self.max_requests_per_run = max_requests_per_run
        self._run_start_requests = 0

    def enabled(self) -> bool:
        return bool(self.token)

    def _check_budget(self) -> None:
        if self.stats["requests"] - self._run_start_requests >= self.max_requests_per_run:
            raise _BudgetExhausted

    async def iter_new(self, cursor: Optional[str], now: int) -> AsyncIterator[Batch]:
        try:
            start = int(cursor) - OVERLAP_SECONDS if cursor else now - FIRST_RUN_LOOKBACK
        except ValueError:
            start = now - FIRST_RUN_LOOKBACK
        start = max(start, now - FIRST_RUN_LOOKBACK)
        self._run_start_requests = self.stats["requests"]
        try:
            async for batch in self._window(start, now):
                yield batch
        except _BudgetExhausted:
            logger.info("hh: request budget for this run used up; continuing next run")

    async def _window(self, lo: int, hi: int) -> AsyncIterator[Batch]:
        self._check_budget()
        body = await self.client.search(lo, hi, 0)
        try:
            found = int(body.get("found") or 0)
        except (TypeError, ValueError):
            found = 0
        if found > MAX_RESULTS and hi - lo > MIN_WINDOW_SECONDS:
            mid = (lo + hi) // 2
            async for batch in self._window(lo, mid):
                yield batch
            async for batch in self._window(mid, hi):
                yield batch
            return
        if found > MAX_RESULTS:
            logger.warning("hh: %d results in a %ds window, only %d reachable", found, hi - lo, MAX_RESULTS)
        try:
            pages = int(body.get("pages") or 1)
        except (TypeError, ValueError):
            pages = 1
        pages = max(1, min(pages, MAX_RESULTS // PER_PAGE))
        page = 0
        while True:
            items = [v for v in (normalize(i) for i in body["items"]) if v is not None]
            self.stats["items"] += len(items)
            last = page + 1 >= pages or not body["items"]
            yield Batch(items, str(hi) if last else None)
            if last:
                return
            page += 1
            body = await self.client.search(lo, hi, page)

    async def fetch_detail(self, source_id: str) -> Optional[NormalizedVacancy]:
        if not source_id.isdigit():
            return None
        body = await self.client.vacancy(source_id)
        if body is None:
            return None
        return normalize(body, detail=True)
