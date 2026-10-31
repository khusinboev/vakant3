"""Nightly analytics rollup: fills ``daily_stats`` (see m011_daily_stats).

``compute_day(conn, day)`` aggregates one Tashkent calendar day from whatever
source tables currently exist — every table (and, for ``saves``, a specific
column) is guarded with a ``sqlite_master``/``PRAGMA table_info`` check first,
and the query itself is also wrapped defensively, so this module never raises
just because another agent's migration (auto_post_log, wallet_transactions,
broadcast_targets, ...) hasn't landed yet on a given DB.

``daily_rollup_loop`` runs forever: on start it backfills up to
``BACKFILL_MAX_DAYS`` missing days, then sleeps until 00:10 Asia/Tashkent every
night and computes yesterday. It opens its own connection per tick, matching
the other bot schedulers (auto_post_scheduler, weekly_stats_scheduler).
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta

from src.core.timeutil import TZ, day_key, now_tz
from src.db.connection import connect

logger = logging.getLogger(__name__)

ROLLUP_HOUR = 0
ROLLUP_MINUTE = 10
BACKFILL_MAX_DAYS = 90
# If a tick fails outright (e.g. DB temporarily locked), retry sooner than a
# full day rather than silently skipping a night.
RETRY_BACKOFF_SECONDS = 300

#: Columns of `daily_stats` this module fills, in insert order (excludes `day`).
STAT_FIELDS: tuple[str, ...] = (
    "new_users",
    "active_users",
    "pro_users",
    "pro_activations",
    "revenue",
    "referral_payouts",
    "saves",
    "resume_saves",
    "resume_sends_ok",
    "resume_sends_err",
    "auto_posts",
    "notifications",
    "broadcasts_sent",
    "computed_at",
)


def day_bounds(day: str) -> tuple[int, int]:
    """[start, end) unix-second bounds of a 'YYYY-MM-DD' Tashkent calendar day."""
    start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=TZ)
    end = start + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())


async def _table_exists(conn, name: str) -> bool:
    cursor = await conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1", (name,)
    )
    return await cursor.fetchone() is not None


async def _column_exists(conn, table: str, column: str) -> bool:
    cursor = await conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in await cursor.fetchall())


async def _scalar(conn, sql: str, params: tuple = ()) -> int:
    try:
        cursor = await conn.execute(sql, params)
        row = await cursor.fetchone()
        return int((row[0] if row else 0) or 0)
    except Exception:
        logger.debug("daily_rollup query failed, defaulting to 0: %s", sql, exc_info=True)
        return 0


async def compute_day(conn, day: str) -> dict[str, int]:
    """Aggregate every known signal for one Tashkent calendar day.

    Returns a dict with exactly ``STAT_FIELDS`` as keys. Safe to call against
    a DB missing any of the source tables (returns 0 for that metric).
    """
    start_ts, end_ts = day_bounds(day)
    stats: dict[str, int] = {field: 0 for field in STAT_FIELDS}

    if await _table_exists(conn, "users"):
        stats["new_users"] = await _scalar(
            conn, "SELECT COUNT(*) FROM users WHERE date >= ? AND date < ?", (start_ts, end_ts)
        )
        # Snapshot at computation time, not a historical point-in-time value —
        # there is no per-day pro/free trail to reconstruct it from.
        stats["pro_users"] = await _scalar(conn, "SELECT COUNT(*) FROM users WHERE user_pro = 1")

    # active_users: union of every per-user activity signal that carries a
    # timestamp. `saves` only joins in once/if it gains a `created_at` column.
    active_selects: list[str] = []
    if await _table_exists(conn, "resume_events"):
        active_selects.append(
            "SELECT user_id FROM resume_events WHERE created_at >= ? AND created_at < ?"
        )
    if await _table_exists(conn, "webapp_sessions"):
        active_selects.append(
            "SELECT user_id FROM webapp_sessions WHERE created_at >= ? AND created_at < ?"
        )
    saves_has_timestamp = await _table_exists(conn, "saves") and await _column_exists(
        conn, "saves", "created_at"
    )
    if saves_has_timestamp:
        active_selects.append("SELECT user_id FROM saves WHERE created_at >= ? AND created_at < ?")
    if active_selects:
        sql = "SELECT COUNT(DISTINCT user_id) FROM (" + " UNION ".join(active_selects) + ")"
        stats["active_users"] = await _scalar(conn, sql, (start_ts, end_ts) * len(active_selects))

    if saves_has_timestamp:
        stats["saves"] = await _scalar(
            conn, "SELECT COUNT(*) FROM saves WHERE created_at >= ? AND created_at < ?", (start_ts, end_ts)
        )
    # else: today's `saves` table has no timestamp column, so a per-day count
    # is not derivable — it stays 0 rather than reporting a misleading total.

    if await _table_exists(conn, "wallet_transactions"):
        stats["pro_activations"] = await _scalar(
            conn,
            "SELECT COUNT(*) FROM wallet_transactions WHERE kind = 'pro_activation' "
            "AND created_at >= ? AND created_at < ?",
            (start_ts, end_ts),
        )
        stats["revenue"] = await _scalar(
            conn,
            "SELECT COALESCE(SUM(COALESCE(price_snapshot, ABS(amount))), 0) FROM wallet_transactions "
            "WHERE kind = 'pro_activation' AND created_at >= ? AND created_at < ?",
            (start_ts, end_ts),
        )
        stats["referral_payouts"] = await _scalar(
            conn,
            "SELECT COALESCE(SUM(ABS(amount)), 0) FROM wallet_transactions "
            "WHERE kind = 'referral_reward' AND created_at >= ? AND created_at < ?",
            (start_ts, end_ts),
        )
    elif await _table_exists(conn, "referral_payouts"):
        # Ledger (wallet_transactions) not migrated yet — fall back to the
        # bot's own payout table so the column is never silently wrong.
        stats["referral_payouts"] = await _scalar(
            conn,
            "SELECT COALESCE(SUM(amount), 0) FROM referral_payouts WHERE ts >= ? AND ts < ?",
            (start_ts, end_ts),
        )

    if await _table_exists(conn, "resume_events"):
        stats["resume_saves"] = await _scalar(
            conn,
            "SELECT COUNT(*) FROM resume_events WHERE event_name IN ('save_success', 'autosave_success') "
            "AND created_at >= ? AND created_at < ?",
            (start_ts, end_ts),
        )
        stats["resume_sends_ok"] = await _scalar(
            conn,
            "SELECT COUNT(*) FROM resume_events WHERE event_name = 'send_success' "
            "AND created_at >= ? AND created_at < ?",
            (start_ts, end_ts),
        )
        stats["resume_sends_err"] = await _scalar(
            conn,
            "SELECT COUNT(*) FROM resume_events WHERE event_name = 'send_error' "
            "AND created_at >= ? AND created_at < ?",
            (start_ts, end_ts),
        )

    if await _table_exists(conn, "auto_post_log"):
        stats["auto_posts"] = await _scalar(
            conn,
            "SELECT COUNT(*) FROM auto_post_log WHERE status = 'sent' "
            "AND posted_at >= ? AND posted_at < ?",
            (start_ts, end_ts),
        )
    elif await _table_exists(conn, "posted_vacancies"):
        # auto_post_log (m010) not migrated yet — posted_vacancies always exists.
        stats["auto_posts"] = await _scalar(
            conn,
            "SELECT COUNT(*) FROM posted_vacancies WHERE posted_at >= ? AND posted_at < ?",
            (start_ts, end_ts),
        )

    if await _table_exists(conn, "sent_notifications"):
        stats["notifications"] = await _scalar(
            conn,
            "SELECT COUNT(*) FROM sent_notifications WHERE sent_at >= ? AND sent_at < ?",
            (start_ts, end_ts),
        )

    if await _table_exists(conn, "broadcast_targets"):
        stats["broadcasts_sent"] = await _scalar(
            conn,
            "SELECT COUNT(*) FROM broadcast_targets WHERE status = 'sent' "
            "AND sent_at >= ? AND sent_at < ?",
            (start_ts, end_ts),
        )

    stats["computed_at"] = int(time.time())
    return stats


async def upsert_daily_stats(conn, day: str, stats: dict[str, int]) -> None:
    """Idempotent write: safe to call repeatedly for the same day (backfill/retry)."""
    columns = ("day", *STAT_FIELDS)
    placeholders = ", ".join(f":{c}" for c in columns)
    update_clause = ", ".join(f"{c} = excluded.{c}" for c in STAT_FIELDS)
    params = {"day": day, **{field: stats.get(field, 0) for field in STAT_FIELDS}}
    await conn.execute(
        f"""
        INSERT INTO daily_stats ({', '.join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(day) DO UPDATE SET {update_clause}
        """,
        params,
    )
    await conn.commit()


async def _existing_days(conn) -> set[str]:
    if not await _table_exists(conn, "daily_stats"):
        return set()
    cursor = await conn.execute("SELECT day FROM daily_stats")
    return {row[0] for row in await cursor.fetchall()}


async def backfill_missing_days(conn, max_days: int = BACKFILL_MAX_DAYS, reference: datetime | None = None) -> list[str]:
    """Compute+upsert any of the last ``max_days`` completed days missing from daily_stats.

    Never touches "today" (still in progress). Returns the days filled, oldest first.
    """
    now = reference or now_tz()
    existing = await _existing_days(conn)
    filled: list[str] = []
    for offset in range(max_days, 0, -1):
        day = day_key(now - timedelta(days=offset))
        if day in existing:
            continue
        stats = await compute_day(conn, day)
        await upsert_daily_stats(conn, day, stats)
        filled.append(day)
    return filled


def _seconds_until_next_run(moment: datetime | None = None) -> float:
    now = moment or now_tz()
    target = now.replace(hour=ROLLUP_HOUR, minute=ROLLUP_MINUTE, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def daily_rollup_loop() -> None:
    """Backfill on start, then compute yesterday every night at 00:10 Asia/Tashkent."""
    try:
        async with connect() as conn:
            filled = await backfill_missing_days(conn)
            if filled:
                logger.info("daily_rollup: backfilled %d day(s): %s", len(filled), filled)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("daily_rollup: startup backfill failed")

    while True:
        try:
            await asyncio.sleep(_seconds_until_next_run())
            yesterday = day_key(now_tz() - timedelta(days=1))
            async with connect() as conn:
                stats = await compute_day(conn, yesterday)
                await upsert_daily_stats(conn, yesterday, stats)
            logger.info("daily_rollup: computed %s: %s", yesterday, stats)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("daily_rollup: tick failed, retrying in %ss", RETRY_BACKOFF_SECONDS)
            await asyncio.sleep(RETRY_BACKOFF_SECONDS)
