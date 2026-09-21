"""Finance reporting for the admin panel.

Read-only: reads on ``wallet_transactions`` (owned by the LEDGER agent, table
created by migration ``m004_wallet_transactions``, see CONTRACT_P0.md) plus
``users`` and ``referral_payouts`` (owned by the bot, see
``src/middleware/middlewares.py``). This module never writes to any table.

Day boundaries use Asia/Tashkent (UTC+5, no DST), computed in SQL with
``date(created_at, 'unixepoch', '+5 hours')`` so a transaction at, say,
23:30 Tashkent time (18:30 UTC) and one at 00:05 Tashkent the next day
(19:05 UTC the *previous* day) land in the correct calendar day — the same
convention ``src/core/timeutil.py`` uses in Python.
"""

from __future__ import annotations

import base64
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from webapp.core import errors
from webapp.core.auth import require_role
from webapp.core.database import get_db
from webapp.core.limiter import limiter
from src.core.timeutil import TZ, now_tz

router = APIRouter(prefix="/admin/finance", tags=["admin-finance"])

# Mirrors CONTRACT_P0.md / webapp/core/ledger.py KINDS. Kept local so this
# router has no import-time dependency on the LEDGER agent's module.
FINANCE_KINDS: tuple[str, ...] = (
    "pro_activation",
    "referral_reward",
    "admin_credit",
    "admin_reset",
    "adjustment",
)

# SQLite expression bucketing a unix-seconds column into an Asia/Tashkent
# calendar day string ('YYYY-MM-DD').
_DAY_EXPR = "date(created_at, 'unixepoch', '+5 hours')"

#: ``total`` is optional by contract (CONTRACT_P12.md "Pagination"), so the
#: count is capped: past this many matching rows the response says ``null``
#: rather than making every page pay for a full scan of ``wallet_transactions``.
COUNT_CAP = 100_000

#: ``/referrals`` groups the whole ``users`` table and joins ``referral_payouts``
#: — there is no cheap incremental form of it. The panel polls the page, so the
#: aggregate is memoised per process for a minute. The window is short enough
#: that a payout shows up while an admin is still looking at the tab.
REFERRALS_CACHE_TTL_SECONDS = 60

_referrals_cache: dict[tuple[Any, ...], tuple[float, Any]] = {}

#: Attribute the resolved database file is memoised on, so the PRAGMA below
#: runs once per connection rather than once per request.
_DB_FILE_ATTR = "_finance_db_file"


async def _db_identity(db) -> str:
    """The database file this connection is attached to.

    Part of the cache key so the memo cannot leak between databases. In
    production every pooled connection reports the same file, so they share one
    cache entry; under test each temporary database gets its own.
    """
    cached = getattr(db, _DB_FILE_ATTR, None)
    if cached is not None:
        return cached
    try:
        cursor = await db.execute("PRAGMA database_list")
        rows = await cursor.fetchall()
        identity = str(next((row[2] for row in rows if row[1] == "main"), "")) or "unknown"
    except Exception:
        identity = "unknown"
    try:
        setattr(db, _DB_FILE_ATTR, identity)
    except AttributeError:  # pragma: no cover - a connection stub
        pass
    return identity


def _referrals_cached(key: tuple[Any, ...]) -> Any | None:
    entry = _referrals_cache.get(key)
    if entry is None or time.monotonic() - entry[0] >= REFERRALS_CACHE_TTL_SECONDS:
        return None
    return entry[1]


def _referrals_store(key: tuple[Any, ...], value: Any) -> Any:
    # Bounded so a client cycling cursors cannot grow the cache without limit.
    if len(_referrals_cache) > 256:
        _referrals_cache.clear()
    _referrals_cache[key] = (time.monotonic(), value)
    return value


# --------------------------------------------------------------------------
# Cursor helpers (opaque base64 of colon-joined sort-key parts)
# --------------------------------------------------------------------------

def _encode_cursor(*parts: Any) -> str:
    raw = ":".join(str(p) for p in parts)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str) -> list[str]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    except Exception as exc:
        raise errors.validation_error("cursor") from exc
    parts = raw.split(":")
    if not parts or not all(parts):
        raise errors.validation_error("cursor")
    return parts


def _window_start_ts(days: int) -> int:
    """Unix ts of the start (00:00 Asia/Tashkent) of the first day in the window."""
    today_local = now_tz().astimezone(TZ).date()
    start_day = today_local - timedelta(days=days - 1)
    start_dt = datetime(start_day.year, start_day.month, start_day.day, tzinfo=TZ)
    return int(start_dt.timestamp())


def _day_range(days: int) -> list[str]:
    """All 'YYYY-MM-DD' keys in the window, oldest first, for zero-filling series."""
    today_local = now_tz().astimezone(TZ).date()
    start_day = today_local - timedelta(days=days - 1)
    return [(start_day + timedelta(days=i)).isoformat() for i in range(days)]


# --------------------------------------------------------------------------
# Response models
# --------------------------------------------------------------------------

class FinanceTotals(BaseModel):
    revenue: int
    activations: int
    admin_credits: int
    referral_payouts: int
    balance_outstanding: int


class FinanceSeriesPoint(BaseModel):
    day: str
    revenue: int
    activations: int
    payouts: int


class FinanceSummaryResponse(BaseModel):
    totals: FinanceTotals
    series: list[FinanceSeriesPoint]


class FinanceTransactionItem(BaseModel):
    id: int
    user_id: int
    kind: str
    amount: int
    balance_after: int
    price_snapshot: int | None = None
    actor_id: int | None = None
    note: str | None = None
    created_at: int


class FinanceTransactionsResponse(BaseModel):
    items: list[FinanceTransactionItem]
    next_cursor: str | None = None
    total: int | None = None


class FinanceReferralItem(BaseModel):
    inviter_id: int
    inviter_name: str
    invited_count: int
    paid_sum: int


class FinanceReferralsResponse(BaseModel):
    items: list[FinanceReferralItem]
    next_cursor: str | None = None
    total: int | None = None


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@router.get("/summary", response_model=FinanceSummaryResponse)
@limiter.limit("60/minute")
async def get_finance_summary(
    request: Request,
    days: int = Query(default=30, ge=1, le=365),
    admin=Depends(require_role("viewer")),
    db=Depends(get_db),
) -> FinanceSummaryResponse:
    start_ts = _window_start_ts(days)

    totals_cursor = await db.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN kind = 'pro_activation' THEN -amount ELSE 0 END), 0) AS revenue,
            COALESCE(SUM(CASE WHEN kind = 'pro_activation' THEN 1 ELSE 0 END), 0) AS activations,
            COALESCE(SUM(CASE WHEN kind = 'admin_credit' THEN amount ELSE 0 END), 0) AS admin_credits,
            COALESCE(SUM(CASE WHEN kind = 'referral_reward' THEN amount ELSE 0 END), 0) AS referral_payouts
        FROM wallet_transactions
        WHERE created_at >= ?
        """,
        (start_ts,),
    )
    totals_row = await totals_cursor.fetchone()

    balance_cursor = await db.execute("SELECT COALESCE(SUM(user_balance), 0) AS s FROM users")
    balance_row = await balance_cursor.fetchone()

    totals = FinanceTotals(
        revenue=int(totals_row["revenue"] if totals_row else 0),
        activations=int(totals_row["activations"] if totals_row else 0),
        admin_credits=int(totals_row["admin_credits"] if totals_row else 0),
        referral_payouts=int(totals_row["referral_payouts"] if totals_row else 0),
        balance_outstanding=int(balance_row["s"] if balance_row else 0),
    )

    series_cursor = await db.execute(
        f"""
        SELECT
            {_DAY_EXPR} AS day,
            COALESCE(SUM(CASE WHEN kind = 'pro_activation' THEN -amount ELSE 0 END), 0) AS revenue,
            COALESCE(SUM(CASE WHEN kind = 'pro_activation' THEN 1 ELSE 0 END), 0) AS activations,
            COALESCE(SUM(CASE WHEN kind = 'referral_reward' THEN amount ELSE 0 END), 0) AS payouts
        FROM wallet_transactions
        WHERE created_at >= ?
        GROUP BY day
        """,
        (start_ts,),
    )
    by_day: dict[str, dict[str, int]] = {
        str(row["day"]): {
            "revenue": int(row["revenue"] or 0),
            "activations": int(row["activations"] or 0),
            "payouts": int(row["payouts"] or 0),
        }
        for row in await series_cursor.fetchall()
    }

    series = [
        FinanceSeriesPoint(
            day=day,
            revenue=by_day.get(day, {}).get("revenue", 0),
            activations=by_day.get(day, {}).get("activations", 0),
            payouts=by_day.get(day, {}).get("payouts", 0),
        )
        for day in _day_range(days)
    ]

    return FinanceSummaryResponse(totals=totals, series=series)


@router.get("/transactions", response_model=FinanceTransactionsResponse)
@limiter.limit("60/minute")
async def list_finance_transactions(
    request: Request,
    kind: str | None = Query(default=None),
    user_id: int | None = Query(default=None),
    from_ts: int | None = Query(default=None, alias="from"),
    to_ts: int | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    admin=Depends(require_role("viewer")),
    db=Depends(get_db),
) -> FinanceTransactionsResponse:
    if kind is not None and kind not in FINANCE_KINDS:
        raise errors.validation_error("kind")

    where: list[str] = []
    params: list[Any] = []
    if kind is not None:
        where.append("kind = ?")
        params.append(kind)
    if user_id is not None:
        where.append("user_id = ?")
        params.append(int(user_id))
    if from_ts is not None:
        where.append("created_at >= ?")
        params.append(int(from_ts))
    if to_ts is not None:
        where.append("created_at <= ?")
        params.append(int(to_ts))

    # Capped count: a LIMIT sub-select stops SQLite as soon as it has seen
    # COUNT_CAP + 1 matching rows, and the response reports ``null`` past that.
    inner = "SELECT 1 FROM wallet_transactions"
    if where:
        inner += " WHERE " + " AND ".join(where)
    count_cursor = await db.execute(
        f"SELECT COUNT(*) AS c FROM ({inner} LIMIT ?)", (*params, COUNT_CAP + 1)
    )
    count_row = await count_cursor.fetchone()
    counted = int(count_row["c"] if count_row else 0)
    total: int | None = None if counted > COUNT_CAP else counted

    page_where = list(where)
    page_params = list(params)
    if cursor:
        parts = _decode_cursor(cursor)
        try:
            before_id = int(parts[0])
        except ValueError as exc:
            raise errors.validation_error("cursor") from exc
        page_where.append("id < ?")
        page_params.append(before_id)

    sql = (
        "SELECT id, user_id, kind, amount, balance_after, price_snapshot, actor_id, note, created_at "
        "FROM wallet_transactions"
    )
    if page_where:
        sql += " WHERE " + " AND ".join(page_where)
    sql += " ORDER BY id DESC LIMIT ?"
    page_params.append(limit)

    rows_cursor = await db.execute(sql, tuple(page_params))
    rows = await rows_cursor.fetchall()

    items = [
        FinanceTransactionItem(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            kind=str(row["kind"]),
            amount=int(row["amount"]),
            balance_after=int(row["balance_after"]),
            price_snapshot=row["price_snapshot"],
            actor_id=row["actor_id"],
            note=row["note"],
            created_at=int(row["created_at"]),
        )
        for row in rows
    ]
    next_cursor = _encode_cursor(items[-1].id) if len(items) == limit else None
    return FinanceTransactionsResponse(items=items, next_cursor=next_cursor, total=total)


@router.get("/referrals", response_model=FinanceReferralsResponse)
@limiter.limit("60/minute")
async def list_finance_referrals(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    admin=Depends(require_role("viewer")),
    db=Depends(get_db),
) -> FinanceReferralsResponse:
    cache_key = (await _db_identity(db), limit, cursor or "")
    cached = _referrals_cached(cache_key)
    if cached is not None:
        return cached

    page_where = ""
    page_params: list[Any] = []
    if cursor:
        parts = _decode_cursor(cursor)
        try:
            last_count = int(parts[0])
            last_inviter = int(parts[1])
        except (IndexError, ValueError) as exc:
            raise errors.validation_error("cursor") from exc
        page_where = (
            "WHERE agg.invited_count < ? "
            "OR (agg.invited_count = ? AND agg.inviter_id < ?)"
        )
        page_params = [last_count, last_count, last_inviter]

    sql = f"""
        WITH agg AS (
            SELECT
                u.ref_by AS inviter_id,
                COUNT(*) AS invited_count,
                COALESCE(SUM(rp.amount), 0) AS paid_sum
            FROM users u
            LEFT JOIN referral_payouts rp ON rp.user_id = u.user_id
            WHERE u.ref_by IS NOT NULL
            GROUP BY u.ref_by
        )
        SELECT
            agg.inviter_id AS inviter_id,
            agg.invited_count AS invited_count,
            agg.paid_sum AS paid_sum,
            inv.first_name AS inviter_first_name,
            inv.username AS inviter_username
        FROM agg
        LEFT JOIN users inv ON inv.user_id = agg.inviter_id
        {page_where}
        ORDER BY agg.invited_count DESC, agg.inviter_id DESC
        LIMIT ?
    """
    rows_cursor = await db.execute(sql, tuple(page_params) + (limit,))
    rows = await rows_cursor.fetchall()

    items: list[FinanceReferralItem] = []
    for row in rows:
        inviter_id = int(row["inviter_id"])
        username = row["inviter_username"]
        first_name = row["inviter_first_name"]
        inviter_name = str(username or first_name or inviter_id)
        items.append(
            FinanceReferralItem(
                inviter_id=inviter_id,
                inviter_name=inviter_name,
                invited_count=int(row["invited_count"]),
                paid_sum=int(row["paid_sum"] or 0),
            )
        )

    total_cursor = await db.execute(
        "SELECT COUNT(DISTINCT ref_by) AS c FROM users WHERE ref_by IS NOT NULL"
    )
    total_row = await total_cursor.fetchone()
    total = int(total_row["c"] if total_row else 0)

    next_cursor = (
        _encode_cursor(items[-1].invited_count, items[-1].inviter_id)
        if len(items) == limit
        else None
    )
    return _referrals_store(
        cache_key,
        FinanceReferralsResponse(items=items, next_cursor=next_cursor, total=total),
    )
