"""Admin Users module: list, detail and moderation actions.

Design notes
------------
*Pagination is keyset (cursor), never OFFSET.* The cursor carries the last
row's ``(sort_value, user_id)`` pair, so a page stays stable while rows are
inserted above it. Every sort key is paired with ``user_id`` as a tie-breaker,
and NULL sort values are paged explicitly (SQLite orders NULL last under
``DESC``, and ``col < ?`` is never true for NULL, so the NULL tail needs its
own predicate).

*The WHERE clauses are written so the indexes are usable*: plain
``u.date``/``u.user_pro``/``u.blocked``/``u.banned`` comparisons rather than
``COALESCE(...)`` wrappers (m001 + m009 index exactly those columns). The only
scan is the ``q`` search, and it is a LIKE scan only when ``q`` is not numeric
— a numeric ``q`` is treated as a primary-key lookup.

*``total`` is optional by contract.* It is computed only for the first page of
a non-LIKE query and only up to ``COUNT_CAP`` rows; past that the response
returns ``null`` instead of making every page pay for a full table count.

*The detail endpoint runs a fixed number of queries* (never one per related
row): one table-existence probe, one aggregate query built from scalar
subqueries, and one small query per recent-rows block.

Every mutation writes its ``admin_audit_log`` row *before* the commit, so the
mutation and its audit trail land together or not at all. Balance movements go
through ``webapp.core.ledger`` — this module never touches ``users.user_balance``.
"""

# NOTE: no ``from __future__ import annotations`` here — slowapi wraps the
# endpoints with functools.wraps, so FastAPI would resolve stringified request
# models against slowapi's module globals and fail.
import base64
import binascii
import json
import logging
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, Field

from webapp.core import errors, ledger
from webapp.core.audit import log_admin_action
from webapp.core.auth import require_role
from webapp.core.config import get_settings
from webapp.core.confirm import require_confirmation
from webapp.core.database import get_db
from webapp.core.limiter import limiter
from webapp.core.request_ip import client_ip as _client_ip

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

# Module-level dependency instances: ``require_role`` builds a new function on
# every call, so tests (and the route-protection test) need stable objects.
require_viewer = require_role("viewer")
require_moderator = require_role("moderator")
require_admin_role = require_role("admin")
require_balance_confirmation = require_confirmation("users.balance", ["user_id", "amount"])

#: Beyond this many matching rows the list endpoint reports ``total = null``.
COUNT_CAP = 100_000

MAX_NOTE = 500
MAX_MESSAGE = 4000
MAX_PRO_DAYS = 3650

SORT_COLUMNS: dict[str, str] = {
    "date": "u.date",
    "balance": "u.user_balance",
    "last_seen": "u.last_seen_at",
}

LANGS = ("uz", "ru", "en")

LIST_COLUMNS = """
    u.user_id, u.first_name, u.username, u.lang, u.region, u.district, u.date,
    COALESCE(u.user_pro, 0) AS user_pro, u.pro_until,
    COALESCE(u.user_balance, 0) AS balance,
    COALESCE(u.banned, 0) AS banned, COALESCE(u.blocked, 0) AS blocked,
    u.banned_reason, u.last_seen_at, u.ref_by
"""

TELEGRAM_SEND_FAILED = errors.TELEGRAM_SEND_FAILED


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _encode_cursor(payload: list[Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


#: What a cursor element may be. A cursor is client-supplied JSON that goes
#: straight into a keyset comparison, so a dict/list slipping through would be
#: compared against a column by SQLite's type ordering rather than rejected.
_CURSOR_SCALARS = (int, float, str, type(None))


def _decode_cursor(cursor: str, length: int) -> list[Any]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise errors.validation_error("cursor") from exc
    if not isinstance(payload, list) or len(payload) != length:
        raise errors.validation_error("cursor")
    # ``bool`` is an ``int`` subclass; it is excluded so a JSON ``true`` cannot
    # pose as the integer 1.
    if any(isinstance(item, bool) or not isinstance(item, _CURSOR_SCALARS) for item in payload):
        raise errors.validation_error("cursor")
    return payload


def _like_term(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _keyset_clause(column: str, value: Any, last_id: int) -> tuple[str, list[Any]]:
    """Rows strictly after ``(value, last_id)`` in ``column DESC, user_id DESC``.

    Written as ``col <= ? AND (col < ? OR user_id < ?)`` and not as the more
    obvious ``col < ? OR (col = ? AND user_id < ?)``: only the first form lets
    SQLite seek into the index (``SEARCH ... (date<?)``) instead of scanning it
    from the top, which is the entire point of keyset pagination. NULL sort
    values never satisfy it, so the NULL tail is paged by its own query.
    """
    return f"({column} <= ? AND ({column} < ? OR u.user_id < ?))", [value, value, last_id]


async def _existing_tables(db, names: tuple[str, ...]) -> set[str]:
    placeholders = ", ".join("?" for _ in names)
    cursor = await db.execute(
        f"SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ({placeholders})",
        names,
    )
    return {row[0] for row in await cursor.fetchall()}


def _clean_note(note: str | None) -> str | None:
    if note is None:
        return None
    note = str(note).strip()
    if not note:
        return None
    if len(note) > MAX_NOTE:
        raise errors.validation_error("note")
    return note


def _raise_ledger_error(exc: ledger.LedgerError) -> None:
    if isinstance(exc, ledger.InsufficientBalance):
        raise errors.api_error(
            400, errors.INSUFFICIENT_BALANCE, required=exc.required, balance=exc.balance
        ) from exc
    if isinstance(exc, ledger.UserNotFound):
        raise errors.not_found("user") from exc
    raise errors.api_error(500, errors.UPSTREAM_ERROR) from exc


# ---------------------------------------------------------------------------
# response models
# ---------------------------------------------------------------------------
class UserListItem(BaseModel):
    user_id: int
    first_name: str | None = None
    username: str | None = None
    lang: str | None = None
    region: str | None = None
    district: str | None = None
    date: int | None = None
    is_pro: bool = False
    pro_until: int | None = None
    balance: int = 0
    banned: bool = False
    banned_reason: str | None = None
    blocked: bool = False
    last_seen_at: int | None = None
    ref_by: int | None = None


class UsersListResponse(BaseModel):
    items: list[UserListItem]
    next_cursor: str | None = None
    total: int | None = None


class UserDetailResponse(BaseModel):
    user: UserListItem
    wallet: dict[str, Any]
    counts: dict[str, int]
    recent_transactions: list[dict[str, Any]]
    recent_events: list[dict[str, Any]]
    notification_settings: dict[str, Any] | None = None
    referrer: dict[str, Any] | None = None


class SavesResponse(BaseModel):
    items: list[dict[str, Any]]
    next_cursor: str | None = None
    total: int | None = None


class ProRequest(BaseModel):
    enabled: bool
    days: int | None = Field(default=None, ge=1, le=MAX_PRO_DAYS)
    note: str | None = Field(default=None, max_length=MAX_NOTE)


class ProResponse(BaseModel):
    ok: bool
    user_id: int
    is_pro: bool
    pro_until: int | None = None
    tx_id: int | None = None


class BalanceRequest(BaseModel):
    # ``user_id`` is part of the confirmation token params, so it travels in the
    # body as well as the path; the two must agree.
    user_id: int = Field(gt=0)
    amount: int = Field(ge=-ledger.MAX_AMOUNT, le=ledger.MAX_AMOUNT)
    note: str | None = Field(default=None, max_length=MAX_NOTE)


class BalanceResponse(BaseModel):
    ok: bool
    user_id: int
    amount: int
    new_balance: int
    tx_id: int


class BanRequest(BaseModel):
    banned: bool
    reason: str | None = Field(default=None, max_length=MAX_NOTE)


class BanResponse(BaseModel):
    ok: bool
    user_id: int
    banned: bool
    reason: str | None = None


class MessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_MESSAGE)


class MessageResponse(BaseModel):
    ok: bool
    user_id: int
    message_id: int | None = None


def _list_item(row) -> dict[str, Any]:
    data = dict(row)
    return {
        "user_id": int(data["user_id"]),
        "first_name": data.get("first_name"),
        "username": data.get("username"),
        "lang": data.get("lang"),
        "region": data.get("region"),
        "district": data.get("district"),
        "date": data.get("date"),
        "is_pro": bool(int(data.get("user_pro") or 0)),
        "pro_until": data.get("pro_until"),
        "balance": int(data.get("balance") or 0),
        "banned": bool(int(data.get("banned") or 0)),
        "banned_reason": data.get("banned_reason"),
        "blocked": bool(int(data.get("blocked") or 0)),
        "last_seen_at": data.get("last_seen_at"),
        "ref_by": data.get("ref_by"),
    }


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@router.get("", response_model=UsersListResponse)
@limiter.limit("60/minute")
async def list_users(
    request: Request,
    q: str | None = Query(default=None, max_length=64),
    pro: bool | None = Query(default=None),
    banned: bool | None = Query(default=None),
    blocked: bool | None = Query(default=None),
    lang: str | None = Query(default=None, max_length=8),
    region: str | None = Query(default=None, max_length=32),
    date_from: int | None = Query(default=None, alias="from", ge=0),
    date_to: int | None = Query(default=None, alias="to", ge=0),
    sort: str = Query(default="date"),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    admin=Depends(require_viewer),
    db=Depends(get_db),
) -> UsersListResponse:
    if sort not in SORT_COLUMNS:
        raise errors.validation_error("sort")
    sort_column = SORT_COLUMNS[sort]

    where: list[str] = []
    params: list[Any] = []
    like_search = False

    term = (q or "").strip()
    if term:
        if term.lstrip("-").isdigit():
            where.append("u.user_id = ?")
            params.append(int(term))
        else:
            like_search = True
            needle = _like_term(term.lstrip("@"))
            where.append("(u.username LIKE ? ESCAPE '\\' OR u.first_name LIKE ? ESCAPE '\\')")
            params.extend([needle, needle])

    if pro is not None:
        # Plain equality keeps idx_users_user_pro usable; the column is nullable
        # on old rows, hence the explicit IS NULL branch for the negative case.
        where.append("u.user_pro = 1" if pro else "(u.user_pro IS NULL OR u.user_pro = 0)")
    if banned is not None:
        where.append("u.banned = 1" if banned else "(u.banned IS NULL OR u.banned = 0)")
    if blocked is not None:
        where.append("u.blocked = 1" if blocked else "(u.blocked IS NULL OR u.blocked = 0)")
    if lang:
        if lang not in LANGS:
            raise errors.validation_error("lang")
        where.append("u.lang = ?")
        params.append(lang)
    if region:
        where.append("u.region = ?")
        params.append(str(region))
    if date_from is not None:
        where.append("u.date >= ?")
        params.append(int(date_from))
    if date_to is not None:
        where.append("u.date <= ?")
        params.append(int(date_to))

    filter_sql = (" WHERE " + " AND ".join(where)) if where else ""

    last_value: Any = None
    last_id: Any = None
    null_phase = False
    if cursor:
        last_value, last_id = _decode_cursor(cursor, 2)
        null_phase = last_value is None
        if not isinstance(last_id, int) and not (null_phase and last_id is None):
            raise errors.validation_error("cursor")

    # ``sort_value`` is the RAW column (not the COALESCE'd alias) so the cursor
    # compares against exactly what the keyset predicate compares against.
    async def _fetch(extra_where: list[str], extra_params: list[Any], want: int, order: str):
        clauses = where + extra_where
        sql_where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        db_cursor = await db.execute(
            f"SELECT {LIST_COLUMNS}, {sort_column} AS sort_value FROM users u{sql_where} "
            f"ORDER BY {order} LIMIT ?",
            (*params, *extra_params, want),
        )
        return list(await db_cursor.fetchall())

    rows: list[Any] = []
    if not null_phase:
        extra_where: list[str] = []
        extra_params: list[Any] = []
        if cursor:
            clause, clause_params = _keyset_clause(sort_column, last_value, last_id)
            extra_where.append(clause)
            extra_params.extend(clause_params)
        rows = await _fetch(
            extra_where, extra_params, limit + 1, f"{sort_column} DESC, u.user_id DESC"
        )

    # The keyset predicate cannot match NULL sort values, so once the non-NULL
    # rows run out the NULL tail is paged by its own query (an unfiltered first
    # page already contains it, ordered last by SQLite's NULL-under-DESC rule).
    if len(rows) <= limit and (null_phase or cursor):
        tail_where = [f"{sort_column} IS NULL"]
        tail_params: list[Any] = []
        if null_phase and last_id is not None:
            tail_where.append("u.user_id < ?")
            tail_params.append(last_id)
        rows.extend(
            await _fetch(tail_where, tail_params, limit + 1 - len(rows), "u.user_id DESC")
        )

    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_list_item(row) for row in rows]

    next_cursor = None
    if has_more and items:
        next_cursor = _encode_cursor([dict(rows[-1])["sort_value"], items[-1]["user_id"]])

    total: int | None = None
    if cursor is None and not like_search:
        # Capped so a huge table never turns every first page into a full scan.
        count_cursor = await db.execute(
            f"SELECT COUNT(*) FROM (SELECT 1 FROM users u{filter_sql} LIMIT ?)",
            (*params, COUNT_CAP + 1),
        )
        counted = int((await count_cursor.fetchone())[0])
        total = None if counted > COUNT_CAP else counted

    return UsersListResponse(
        items=[UserListItem(**item) for item in items], next_cursor=next_cursor, total=total
    )


# ---------------------------------------------------------------------------
# detail
# ---------------------------------------------------------------------------
@router.get("/{user_id}", response_model=UserDetailResponse)
@limiter.limit("60/minute")
async def get_user(
    request: Request,
    user_id: int = Path(..., gt=0),
    admin=Depends(require_viewer),
    db=Depends(get_db),
) -> UserDetailResponse:
    db_cursor = await db.execute(
        f"SELECT {LIST_COLUMNS} FROM users u WHERE u.user_id = ?", (user_id,)
    )
    row = await db_cursor.fetchone()
    if row is None:
        raise errors.not_found("user")
    user = _list_item(row)

    tables = await _existing_tables(
        db,
        (
            "saves",
            "referral_payouts",
            "resume_exports",
            "wallet_transactions",
            "resume_events",
            "notification_settings",
        ),
    )

    # One aggregate query built from scalar subqueries — never one per relation.
    selects: list[str] = []
    agg_params: list[Any] = []
    if "saves" in tables:
        selects.append("(SELECT COUNT(DISTINCT save_id) FROM saves WHERE user_id = ?) AS saves")
        agg_params.append(user_id)
    selects.append("(SELECT COUNT(*) FROM users WHERE ref_by = ?) AS referrals")
    agg_params.append(user_id)
    if "referral_payouts" in tables:
        selects.append(
            "(SELECT COALESCE(SUM(amount), 0) FROM referral_payouts WHERE inviter_id = ?)"
            " AS payouts_sum"
        )
        agg_params.append(user_id)
    if "resume_exports" in tables:
        selects.append(
            "(SELECT COUNT(*) FROM resume_exports WHERE user_id = ?) AS resume_exports"
        )
        agg_params.append(user_id)
    db_cursor = await db.execute(f"SELECT {', '.join(selects)}", tuple(agg_params))
    agg = dict(await db_cursor.fetchone())
    counts = {
        "saves": int(agg.get("saves") or 0),
        "referrals": int(agg.get("referrals") or 0),
        "payouts_sum": int(agg.get("payouts_sum") or 0),
        "resume_exports": int(agg.get("resume_exports") or 0),
    }

    recent_transactions: list[dict[str, Any]] = []
    if "wallet_transactions" in tables:
        db_cursor = await db.execute(
            """
            SELECT id, kind, amount, balance_after, price_snapshot, actor_id, note, created_at
            FROM wallet_transactions WHERE user_id = ? ORDER BY id DESC LIMIT 10
            """,
            (user_id,),
        )
        recent_transactions = [dict(r) for r in await db_cursor.fetchall()]

    recent_events: list[dict[str, Any]] = []
    if "resume_events" in tables:
        db_cursor = await db.execute(
            """
            SELECT id, event_name, step, created_at FROM resume_events
            WHERE user_id = ? ORDER BY id DESC LIMIT 10
            """,
            (user_id,),
        )
        recent_events = [dict(r) for r in await db_cursor.fetchall()]

    notification_settings: dict[str, Any] | None = None
    if "notification_settings" in tables:
        db_cursor = await db.execute(
            "SELECT enabled, created_at, updated_at FROM notification_settings WHERE user_id = ?",
            (user_id,),
        )
        notif_row = await db_cursor.fetchone()
        if notif_row is not None:
            notification_settings = dict(notif_row)
            notification_settings["enabled"] = bool(int(notification_settings["enabled"] or 0))

    referrer: dict[str, Any] | None = None
    if user["ref_by"]:
        db_cursor = await db.execute(
            "SELECT user_id, first_name, username FROM users WHERE user_id = ?",
            (int(user["ref_by"]),),
        )
        ref_row = await db_cursor.fetchone()
        if ref_row is not None:
            referrer = dict(ref_row)

    return UserDetailResponse(
        user=UserListItem(**user),
        wallet={
            "balance": user["balance"],
            "is_pro": user["is_pro"],
            "pro_until": user["pro_until"],
        },
        counts=counts,
        recent_transactions=recent_transactions,
        recent_events=recent_events,
        notification_settings=notification_settings,
        referrer=referrer,
    )


# ---------------------------------------------------------------------------
# saves
# ---------------------------------------------------------------------------
@router.get("/{user_id}/saves", response_model=SavesResponse)
@limiter.limit("60/minute")
async def list_user_saves(
    request: Request,
    user_id: int = Path(..., gt=0),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
    admin=Depends(require_viewer),
    db=Depends(get_db),
) -> SavesResponse:
    where = ["user_id = ?"]
    params: list[Any] = [user_id]
    if cursor:
        (last_id,) = _decode_cursor(cursor, 1)
        if not isinstance(last_id, int):
            raise errors.validation_error("cursor")
        where.append("save_id < ?")
        params.append(last_id)

    db_cursor = await db.execute(
        f"SELECT DISTINCT save_id FROM saves WHERE {' AND '.join(where)} "
        "ORDER BY save_id DESC LIMIT ?",
        (*params, limit + 1),
    )
    rows = [row[0] for row in await db_cursor.fetchall()]
    has_more = len(rows) > limit
    rows = rows[:limit]

    items = [
        {
            "save_id": save_id,
            "uid": str(save_id) if str(save_id).startswith("osonish_") else f"osonish_{save_id}",
        }
        for save_id in rows
    ]

    next_cursor = None
    if has_more and rows:
        try:
            next_cursor = _encode_cursor([int(rows[-1])])
        except (TypeError, ValueError):
            next_cursor = None

    total = None
    if cursor is None:
        db_cursor = await db.execute(
            "SELECT COUNT(DISTINCT save_id) FROM saves WHERE user_id = ?", (user_id,)
        )
        total = int((await db_cursor.fetchone())[0])

    return SavesResponse(items=items, next_cursor=next_cursor, total=total)


# ---------------------------------------------------------------------------
# mutations
# ---------------------------------------------------------------------------
@router.post("/{user_id}/pro", response_model=ProResponse)
@limiter.limit("10/minute")
async def set_user_pro(
    request: Request,
    body: ProRequest,
    user_id: int = Path(..., gt=0),
    admin=Depends(require_admin_role),
    db=Depends(get_db),
) -> ProResponse:
    note = _clean_note(body.note)
    if not body.enabled and body.days is not None:
        raise errors.validation_error("days")

    pro_until: int | None = None
    if body.enabled and body.days:
        pro_until = int(time.time()) + int(body.days) * 86400

    # The UPDATE is the first statement of the transaction (see ledger docs) and
    # its rowcount doubles as the existence check.
    if body.enabled:
        db_cursor = await db.execute(
            "UPDATE users SET user_pro = 1, pro_until = ? WHERE user_id = ?",
            (pro_until, user_id),
        )
    else:
        db_cursor = await db.execute(
            "UPDATE users SET user_pro = 0, pro_until = NULL WHERE user_id = ?", (user_id,)
        )
    if not db_cursor.rowcount:
        raise errors.not_found("user")

    ledger_note = note or ("pro grant" if body.enabled else "pro revoke")
    try:
        result = await ledger.apply_balance_change(
            db,
            user_id=user_id,
            amount=0,
            kind="adjustment",
            actor_id=int(admin["user_id"]),
            note=ledger_note[:MAX_NOTE],
        )
    except ledger.LedgerError as exc:
        _raise_ledger_error(exc)
        raise  # pragma: no cover - _raise_ledger_error always raises

    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="users.pro",
        target_type="user",
        target_id=str(user_id),
        payload={
            "enabled": body.enabled,
            "days": body.days,
            "pro_until": pro_until,
            "note": note,
            "tx_id": result["tx_id"],
        },
        ip=_client_ip(request),
    )
    await db.commit()

    return ProResponse(
        ok=True,
        user_id=user_id,
        is_pro=body.enabled,
        pro_until=pro_until,
        tx_id=int(result["tx_id"]),
    )


@router.post(
    "/{user_id}/balance",
    response_model=BalanceResponse,
    dependencies=[Depends(require_balance_confirmation)],
)
@limiter.limit("10/minute")
async def change_user_balance(
    request: Request,
    body: BalanceRequest,
    user_id: int = Path(..., gt=0),
    admin=Depends(require_admin_role),
    db=Depends(get_db),
) -> BalanceResponse:
    if int(body.user_id) != user_id:
        raise errors.validation_error("user_id")
    if body.amount == 0:
        raise errors.validation_error("amount")
    note = _clean_note(body.note)

    try:
        result = await ledger.apply_balance_change(
            db,
            user_id=user_id,
            amount=int(body.amount),
            kind="admin_credit",
            actor_id=int(admin["user_id"]),
            note=note,
            require_sufficient=body.amount < 0,
        )
    except ledger.LedgerError as exc:
        _raise_ledger_error(exc)
        raise  # pragma: no cover - _raise_ledger_error always raises
    except ValueError as exc:
        raise errors.validation_error("amount") from exc

    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="users.balance",
        target_type="user",
        target_id=str(user_id),
        payload={
            "amount": int(body.amount),
            "balance_after": int(result["balance_after"]),
            "tx_id": int(result["tx_id"]),
            "note": note,
        },
        ip=_client_ip(request),
    )
    await db.commit()

    return BalanceResponse(
        ok=True,
        user_id=user_id,
        amount=int(body.amount),
        new_balance=int(result["balance_after"]),
        tx_id=int(result["tx_id"]),
    )


@router.post("/{user_id}/ban", response_model=BanResponse)
@limiter.limit("10/minute")
async def set_user_ban(
    request: Request,
    body: BanRequest,
    user_id: int = Path(..., gt=0),
    admin=Depends(require_moderator),
    db=Depends(get_db),
) -> BanResponse:
    reason = _clean_note(body.reason)
    db_cursor = await db.execute(
        "UPDATE users SET banned = ?, banned_reason = ? WHERE user_id = ?",
        (1 if body.banned else 0, reason if body.banned else None, user_id),
    )
    if not db_cursor.rowcount:
        raise errors.not_found("user")

    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="users.ban",
        target_type="user",
        target_id=str(user_id),
        payload={"banned": body.banned, "reason": reason},
        ip=_client_ip(request),
    )
    await db.commit()

    return BanResponse(
        ok=True, user_id=user_id, banned=body.banned, reason=reason if body.banned else None
    )


async def send_telegram_message(token: str, chat_id: int, text: str) -> dict[str, Any]:
    """POST sendMessage. Returns the raw Telegram payload; never logs the token."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": int(chat_id), "text": text, "disable_web_page_preview": True},
        )
    try:
        return response.json()
    except ValueError:
        return {"ok": False, "error_code": response.status_code, "description": "invalid response"}


@router.post("/{user_id}/message", response_model=MessageResponse)
@limiter.limit("10/minute")
async def message_user(
    request: Request,
    body: MessageRequest,
    user_id: int = Path(..., gt=0),
    admin=Depends(require_moderator),
    db=Depends(get_db),
) -> MessageResponse:
    text = body.text.strip()
    if not text:
        raise errors.validation_error("text")

    db_cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if await db_cursor.fetchone() is None:
        raise errors.not_found("user")

    token = (get_settings().TOKEN or "").strip()
    if not token:
        raise errors.api_error(500, errors.SERVER_MISCONFIGURED)

    error_code: int | None = None
    description: str | None = None
    message_id: int | None = None
    try:
        # Sent without parse_mode: the admin's text is delivered verbatim and
        # can never be interpreted as markup.
        payload = await send_telegram_message(token, user_id, text)
    except httpx.HTTPError as exc:
        _log.warning("admin message to %s failed: %s", user_id, type(exc).__name__)
        payload = {"ok": False, "description": "network error"}

    ok = bool(payload.get("ok"))
    if ok:
        message_id = (payload.get("result") or {}).get("message_id")
    else:
        error_code = payload.get("error_code")
        description = str(payload.get("description") or "")[:200]
        if error_code == 403:
            # The user blocked the bot: record it, the broadcast worker uses it too.
            await db.execute("UPDATE users SET blocked = 1 WHERE user_id = ?", (user_id,))

    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="users.message",
        target_type="user",
        target_id=str(user_id),
        payload={
            "ok": ok,
            "length": len(text),
            "message_id": message_id,
            "error_code": error_code,
            "description": description,
        },
        ip=_client_ip(request),
    )
    await db.commit()

    if not ok:
        raise errors.api_error(502, TELEGRAM_SEND_FAILED, reason=description or None)

    return MessageResponse(ok=True, user_id=user_id, message_id=message_id)
