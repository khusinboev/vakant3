"""Contracts shared by every ingestion source.

An adapter turns one site's API into ``NormalizedVacancy`` objects. It does
network I/O only and never touches the database; the runner stores what it
yields in short transactions (``src/ingest/repo.py``).
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable, Optional, Protocol

from src.core.timeutil import TZ

#: Canonical-copy priority inside a duplicate group: higher wins.
SOURCE_PRIORITY: dict[str, int] = {"hh": 20, "osonish": 10}


class SourceError(Exception):
    """A source could not answer (outage, rate limit exhausted, auth refused, broken body).

    Never means "the vacancy does not exist": adapters return ``None`` for that.
    """

    def __init__(self, reason: str, status: int | None = None) -> None:
        super().__init__(f"{reason} (status={status})" if status is not None else reason)
        self.reason = reason
        self.status = status


@dataclass
class NormalizedVacancy:
    source: str
    source_id: str
    title: str
    published_at: int
    employer: str = ""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    currency: Optional[str] = None
    salary_gross: Optional[bool] = None
    region_soato: Optional[str] = None
    district_soato: Optional[str] = None
    region_name: str = ""
    category: str = ""
    experience: str = ""
    employment: str = ""
    schedule: str = ""
    description_text: str = ""
    skills: list[str] = field(default_factory=list)
    contacts: dict[str, Any] = field(default_factory=dict)
    url: str = ""
    #: False when the source marks it archived / closed.
    is_open: bool = True
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def uid(self) -> str:
        return f"{self.source}_{self.source_id}"


@dataclass
class Batch:
    """One page of list results plus the cursor that is safe to store once it is saved.

    ``cursor`` is ``None`` while the run is still inside a unit of work that is
    not complete yet (e.g. an hh date window with more pages to come).
    """

    items: list[NormalizedVacancy]
    cursor: Optional[str] = None


class Adapter(Protocol):
    name: str
    #: Seconds between two list polls of this source.
    interval_seconds: int
    #: How many open vacancies to re-check through the detail endpoint per run.
    recheck_per_run: int
    #: An open vacancy neither seen in a list nor confirmed by a detail check for
    #: this long is closed as stale.
    stale_after_seconds: int
    stats: dict[str, int]

    def enabled(self) -> bool: ...

    def iter_new(self, cursor: Optional[str], now: int) -> AsyncIterator[Batch]: ...

    async def fetch_detail(self, source_id: str) -> Optional[NormalizedVacancy]:
        """Full vacancy, ``None`` when the source says it no longer exists; ``SourceError`` on outage."""
        ...


class RateLimiter:
    """Minimum spacing between requests (a token bucket of size 1).

    ``clock`` and ``sleep`` are injectable so tests never wait for real.
    """

    def __init__(
        self,
        per_second: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    ) -> None:
        self.interval = 1.0 / per_second if per_second > 0 else 0.0
        self._clock = clock
        self._sleep = sleep
        self._next_at = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = self._clock()
            if now < self._next_at:
                await self._sleep(self._next_at - now)
                now = self._next_at
            self._next_at = now + self.interval


def new_stats() -> dict[str, int]:
    return {"requests": 0, "errors": 0, "retries": 0, "items": 0}


def parse_ts(value: Any) -> Optional[int]:
    """ISO-8601 (``Z``, ``+05:00`` or ``+0500``; naive = Asia/Tashkent) or ``YYYY-MM-DD HH:MM:SS`` -> unix."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.strptime(text[:24], "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return int(dt.timestamp())
