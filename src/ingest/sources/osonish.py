"""osonish.uz adapter (always enabled).

Lists come newest first; a run pages until a whole page is older than the
stored cursor minus an overlap, the last page, or ``max_pages``. The cursor is the
newest ``created_at`` seen (unix seconds). List items carry no description,
so the runner's detail re-check fills it.
"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Awaitable, Callable, Mapping, Optional

from src.functions import scraping
from src.functions.vacancy_format import extract_codes
from src.ingest.base import Batch, DetailUnusable, NormalizedVacancy, RateLimiter, SourceError, new_stats, parse_ts
from src.ingest.categories import osonish_category
from src.ingest.regions import osonish_region
from src.ingest.text import clean_line, html_to_text

logger = logging.getLogger(__name__)

PageFetcher = Callable[[int, int], Awaitable[tuple[list[dict[str, Any]], int]]]
DetailFetcher = Callable[[int], Awaitable[Optional[dict[str, Any]]]]

OVERLAP_SECONDS = 3600
FIRST_RUN_LOOKBACK = 30 * 86_400


def _int_or_none(value: Any) -> Optional[int]:
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _code(codes: Mapping[str, Any], name: str) -> str:
    value = codes.get(name)
    return "" if value is None else str(value)


def normalize(item: Mapping[str, Any], region_names: Mapping[str, str] | None = None, *, detail: bool = False):
    """osonish list item or detail -> ``NormalizedVacancy`` (``None`` when unusable)."""
    raw_id = item.get("id")
    if not isinstance(raw_id, int) or isinstance(raw_id, bool) or not 0 < raw_id <= scraping.MAX_OSONISH_ID:
        return None
    published = parse_ts(item.get("created_at")) or parse_ts(item.get("updated_at"))
    if published is None:
        return None
    company = item.get("company") if isinstance(item.get("company"), Mapping) else {}
    hr = item.get("hr") if isinstance(item.get("hr"), Mapping) else {}
    region, district, region_name = osonish_region(item, region_names)
    codes = extract_codes(dict(item))
    contacts: dict[str, Any] = {}
    if detail:
        phone = clean_line(hr.get("phone") or item.get("phone") or "", 40)
        email = clean_line(hr.get("email") or item.get("email") or "", 120)
        name = clean_line(hr.get("name") or hr.get("full_name") or "", 120)
        contacts = {k: v for k, v in (("name", name), ("phones", [phone] if phone else []), ("email", email)) if v}
    description = ""
    if detail:
        description = html_to_text(item.get("info") or item.get("description") or item.get("requirements"))
    title = clean_line(item.get("title") or "")
    return NormalizedVacancy(
        source="osonish",
        source_id=str(raw_id),
        title=title,
        published_at=published,
        employer=clean_line(company.get("name") or item.get("company_name") or ""),
        salary_min=_int_or_none(item.get("min_salary")),
        salary_max=_int_or_none(item.get("max_salary")),
        currency="UZS",
        salary_gross=None,
        region_soato=region,
        district_soato=district,
        region_name=region_name,
        category=clean_line(
            (item.get("mmk_position") or {}).get("name", "") if isinstance(item.get("mmk_position"), Mapping) else ""
        ),
        category_id=osonish_category(item, title),
        experience=_code(codes, "experience"),
        employment=_code(codes, "busyness_type"),
        schedule=_code(codes, "work_type"),
        description_text=description,
        contacts=contacts,
        url=f"https://osonish.uz/vacancies/{raw_id}",
        is_open=True,
        raw=dict(item),
    )


class OsonishAdapter:
    name = "osonish"
    interval_seconds = 600
    recheck_per_run = 60
    stale_after_seconds = 21 * 86_400

    def __init__(
        self,
        fetch_page: PageFetcher | None = None,
        fetch_detail_raw: DetailFetcher | None = None,
        *,
        per_page: int = 50,
        max_pages: int = 20,
        rate: RateLimiter | None = None,
        region_names: Mapping[str, str] | None = None,
    ) -> None:
        self._fetch_page = fetch_page or scraping.fetch_osonish_raw_page
        self._fetch_detail = fetch_detail_raw or scraping.get_osonish_detail
        self.per_page = per_page
        self.max_pages = max_pages
        self.rate = rate or RateLimiter(1.0)
        self.region_names: Mapping[str, str] = region_names or {}
        self.stats = new_stats()

    def enabled(self) -> bool:
        return True

    async def _call(self, fn, *args):
        await self.rate.wait()
        self.stats["requests"] += 1
        try:
            return await fn(*args)
        except scraping.UpstreamError as exc:
            self.stats["errors"] += 1
            raise SourceError(exc.reason, exc.status) from exc

    async def iter_new(self, cursor: Optional[str], now: int) -> AsyncIterator[Batch]:
        try:
            since = int(cursor) - OVERLAP_SECONDS if cursor else now - FIRST_RUN_LOOKBACK
        except ValueError:
            since = now - FIRST_RUN_LOOKBACK
        newest = int(cursor) if cursor and cursor.isdigit() else 0
        page = 1
        while page <= self.max_pages:
            items, last_page = await self._call(self._fetch_page, page, self.per_page)
            batch = [v for v in (normalize(i, self.region_names) for i in items) if v is not None]
            self.stats["items"] += len(batch)
            if batch:
                newest = max(newest, max(v.published_at for v in batch))
            # Stop once a whole page is older than the cursor; older items on a mixed
            # page are kept, a re-sighting refreshes ``last_seen_at``.
            reached_old = not batch or max(v.published_at for v in batch) < since
            done = reached_old or page >= last_page or page >= self.max_pages
            yield Batch(batch, str(newest) if done and newest else None)
            if done:
                return
            page += 1

    async def fetch_detail(self, source_id: str) -> Optional[NormalizedVacancy]:
        try:
            vacancy_id = int(source_id)
        except ValueError:
            return None
        data = await self._call(self._fetch_detail, vacancy_id)
        if data is None:
            return None
        vacancy = normalize(data, self.region_names, detail=True)
        if vacancy is None:
            raise DetailUnusable(f"osonish {vacancy_id}: unparseable detail")
        return vacancy
