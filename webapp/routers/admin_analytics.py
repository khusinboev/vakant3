"""Admin dashboard analytics: the `daily_stats` rollup plus today's live counters.

Not registered here — the coordinator includes this router in webapp/main.py
once Phase 0/1 routers have landed (see CONTRACT_P12.md).
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Request

from src.core.timeutil import day_key, now_tz
from src.functions.daily_rollup import compute_day
from webapp.core.auth import require_role
from webapp.core.database import get_db
from webapp.core.limiter import limiter

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])

MAX_DAYS = 365


def _day_key_offset(days_ago: int) -> str:
    return day_key(now_tz() - timedelta(days=days_ago))


@router.get("/overview")
@limiter.limit("60/minute")
async def get_overview(
    request: Request,
    days: int = Query(30, ge=1, le=MAX_DAYS),
    admin: dict = Depends(require_role("viewer")),
    db=Depends(get_db),
) -> dict:
    """Series from `daily_stats` for the last `days` completed days, plus today (live, unpersisted)."""
    today = day_key()
    start_day = _day_key_offset(days)

    cursor = await db.execute(
        "SELECT day, new_users, active_users, pro_users, pro_activations, revenue, "
        "referral_payouts, saves, resume_saves, resume_sends_ok, resume_sends_err, "
        "auto_posts, notifications, broadcasts_sent, computed_at "
        "FROM daily_stats WHERE day >= ? AND day < ? ORDER BY day",
        (start_day, today),
    )
    series = [dict(row) for row in await cursor.fetchall()]

    # Today isn't finished yet, so it is never persisted — computed fresh on
    # every call from the same cheap, guarded queries the nightly job uses.
    today_live = await compute_day(db, today)
    today_live["day"] = today

    return {"days": days, "series": series, "today": today_live}
