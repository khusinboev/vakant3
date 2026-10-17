"""The ingestion loop: poll every enabled source on its own interval and keep the store fresh.

Per due adapter and run:
1. list new vacancies (``iter_new``) and upsert each page in its own short
   transaction; the cursor is saved as soon as a unit of work completes;
2. re-check up to ``recheck_per_run`` open vacancies through the detail
   endpoint (never-checked first) — this fills descriptions and closes the
   ones the source answers 404 / archived for;
3. close rows not confirmed for ``stale_after_seconds``.
Then closed rows older than ``PURGE_AFTER_SECONDS`` are deleted.

No transaction is ever open while a request is in flight. One adapter
failing is logged and recorded in ``ingest_cursor.last_error``; the others
still run, and the loop itself never dies.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Callable, Optional, Sequence

from src.ingest import repo
from src.ingest.base import Adapter, SourceError

logger = logging.getLogger(__name__)

TICK_SECONDS = 60
PURGE_AFTER_SECONDS = 60 * 86_400


class IngestRunner:
    def __init__(
        self,
        adapters: Sequence[Adapter],
        *,
        clock: Callable[[], float] = time.time,
        purge_after_seconds: int = PURGE_AFTER_SECONDS,
    ) -> None:
        self.adapters = list(adapters)
        self.clock = clock
        self.purge_after_seconds = purge_after_seconds

    def _now(self) -> int:
        return int(self.clock())

    async def run_once(self, conn, *, force: bool = False) -> dict[str, dict[str, Any]]:
        """Run every enabled adapter that is due (or all with ``force``); returns per-source stats."""
        results: dict[str, dict[str, Any]] = {}
        for adapter in self.adapters:
            if not adapter.enabled():
                continue
            now = self._now()
            state = await repo.get_cursor(conn, adapter.name)
            last_run = (state or {}).get("last_run_at")
            if not force and last_run and now - int(last_run) < adapter.interval_seconds:
                continue
            for key in adapter.stats:
                adapter.stats[key] = 0
            try:
                results[adapter.name] = await self._run_adapter(conn, adapter, state, now)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("ingest %s: run failed", adapter.name)
                stats = {**adapter.stats, "failed": 1}
                results[adapter.name] = {**stats, "error": f"{type(exc).__name__}: {exc}"}
                try:
                    if conn.in_transaction:
                        await conn.rollback()
                    await repo.save_run(
                        conn, adapter.name, now=now, cursor=None, ok=False,
                        error=f"{type(exc).__name__}: {exc}", stats=stats,
                    )
                except Exception:
                    logger.exception("ingest %s: could not record the failure", adapter.name)
        try:
            purged = await repo.purge_closed(conn, self._now() - self.purge_after_seconds)
            if purged:
                logger.info("ingest: purged %d closed vacancies", purged)
        except Exception:
            logger.exception("ingest: purge failed")
        return results

    async def _run_adapter(self, conn, adapter: Adapter, state: Optional[dict[str, Any]], now: int) -> dict[str, Any]:
        if hasattr(adapter, "region_names"):
            adapter.region_names = await repo.region_name_map(conn)  # type: ignore[attr-defined]
        cursor = (state or {}).get("cursor")
        new_cursor: Optional[str] = None
        seen = new = 0
        async for batch in adapter.iter_new(cursor, now):
            if batch.items:
                new += await repo.upsert_batch(conn, batch.items, self._now())
                seen += len(batch.items)
            if batch.cursor is not None:
                new_cursor = batch.cursor
                await repo.save_cursor(conn, adapter.name, new_cursor)

        checked = closed = 0
        recheck_error = None
        for source_id in await repo.pick_for_recheck(conn, adapter.name, adapter.recheck_per_run):
            uid = f"{adapter.name}_{source_id}"
            try:
                vacancy = await adapter.fetch_detail(source_id)
            except SourceError as exc:
                recheck_error = f"recheck: {exc}"
                logger.warning("ingest %s: detail re-check stopped: %s", adapter.name, exc)
                break
            ts = self._now()
            if vacancy is None:
                closed += await repo.close(conn, [uid], "gone", ts)
                continue
            if vacancy.uid != uid:
                await repo.mark_checked(conn, uid, ts)
                continue
            await repo.apply_detail(conn, vacancy, ts)
            checked += 1
            if not vacancy.is_open:
                closed += 1

        stale = await repo.close_stale(conn, adapter.name, now - adapter.stale_after_seconds, self._now())
        stats = {**adapter.stats, "seen": seen, "new": new, "checked": checked, "closed": closed, "stale": stale}
        await repo.save_run(
            conn, adapter.name, now=now, cursor=new_cursor, ok=recheck_error is None, error=recheck_error, stats=stats
        )
        logger.info("ingest %s: %s", adapter.name, stats)
        return stats


def ingest_enabled() -> bool:
    return (os.getenv("INGEST_ENABLED") or "1").strip().lower() not in ("0", "false", "no", "off")


def build_adapters() -> list[Adapter]:
    from src.ingest.sources.hh import HHAdapter
    from src.ingest.sources.osonish import OsonishAdapter

    return [OsonishAdapter(), HHAdapter()]


async def ingest_loop(tick_seconds: int = TICK_SECONDS) -> None:
    """Bot background task: a tick per minute, each adapter runs when its interval is due."""
    from src.db.connection import connect

    if not ingest_enabled():
        logger.info("ingest: disabled by INGEST_ENABLED")
        return
    runner = IngestRunner(build_adapters())
    for adapter in runner.adapters:
        logger.info("ingest: source %s %s", adapter.name, "enabled" if adapter.enabled() else "disabled")
    while True:
        try:
            async with connect() as conn:
                await runner.run_once(conn)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("ingest: tick failed")
        await asyncio.sleep(tick_seconds)
