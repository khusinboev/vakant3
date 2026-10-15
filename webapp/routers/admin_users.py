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

*Rank protection.* No action on a user (Pro, balance, reset, ban/unban, message,
session revocation) may target an admin whose role ranks at or above the
actor's: a moderator cannot ban an admin, an admin cannot touch another admin,
and nobody — not even another owner — can act on an owner. The target's role is
read with the same rule as ``auth.resolve_admin_role`` (an enabled ``admins``
row, else the ``ADMIN_IDS`` bootstrap owner while no enabled owner exists) but
without its lazy INSERT. Refusal: 403 ``CANNOT_TARGET_ADMIN{role}``.

*Sessions.* A ``webapp_sessions`` row is the identity behind a Bearer token, so
banning deletes the user's rows in the ban's own transaction (and the unused
bot hand-off tokens that could mint new ones); ``/sessions/revoke`` does the
same without banning.

*Idempotent balance changes.* ``X-Idempotency-Key`` claims a row in
``admin_idempotency`` (m018) as the first write of the transaction; see
:func:`_claim_idempotency`.

*CSV export* (``/export.csv``) streams the list's filters and sort in keyset
chunks of ``EXPORT_CHUNK`` rows on its own connection, capped at
``EXPORT_MAX_ROWS``; see :func:`export_users_csv`.
"""

# NOTE: no ``from __future__ import annotations`` here — slowapi wraps the
# endpoints with functools.wraps, so FastAPI would resolve stringified request
# models against slowapi's module globals and fail.
import base64
import binascii
import csv
import hashlib
import hmac
import io
import json
import logging
import re
import secrets
import time
from datetime import datetime
from typing import Any, AsyncIterator, Awaitable, Callable

import httpx
from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.core.timeutil import TZ
from webapp.core import errors, ledger
from webapp.core.audit import log_admin_action
from webapp.core.auth import (
    ROLES,
    USER_BANNED,
    has_enabled_owner,
    is_banned,
    require_role,
    resolve_admin_role,
    role_rank,
)
from webapp.core.config import get_settings
from webapp.core.confirm import canonical_params, require_confirmation
from webapp.core.database import get_db, open_connection
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
require_reset_confirmation = require_confirmation("users.reset", ["user_id"])
require_sessions_confirmation = require_confirmation("users.sessions_revoke", ["user_id"])

#: Beyond this many matching rows the list endpoint reports ``total = null``.
COUNT_CAP = 100_000

#: Hard cap on one CSV export. A bigger result is cut here (the response says
#: so in ``X-Export-Truncated``); narrow the filters to export the rest.
EXPORT_MAX_ROWS = 100_000
#: Rows per keyset query while streaming; also the unit the response is flushed in.
EXPORT_CHUNK = 500

#: How long an ``X-Idempotency-Key`` is remembered for one actor and action.
IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60
_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,128}$")
IDEMPOTENCY_HEADER = "x-idempotency-key"
REPLAYED_HEADER = "Idempotent-Replayed"

#: Action name of the single-use CSV download link: the ``admin_idempotency``
#: claim, the error params and the MAC's domain all use it.
EXPORT_DOWNLOAD_ACTION = "users.export_download"
#: How long a download link stays valid. Longer than the 60 s confirm TTL:
#: Telegram's native ``downloadFile`` popup waits for the admin to tap it.
EXPORT_LINK_TTL_SECONDS = 300

#: Error codes this module adds (the frontend translates them in adminUsers.ts).
CANNOT_TARGET_ADMIN = "CANNOT_TARGET_ADMIN"
IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"

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
# rank protection
# ---------------------------------------------------------------------------
async def target_admin_role(db, user_id: int) -> str | None:
    """The admin role the TARGET of an action holds, or None.

    Same rule as ``webapp.core.auth.resolve_admin_role`` — an enabled
    ``admins`` row wins, a disabled one means "not an admin", and an
    ``ADMIN_IDS`` id counts as the bootstrap owner while no enabled owner
    exists — but strictly read-only: resolving someone else's role must never
    provision them (``resolve_admin_role`` inserts and commits).
    """
    user_id = int(user_id)
    if "admins" not in await _existing_tables(db, ("admins",)):
        return "owner" if user_id in get_settings().admin_ids_set else None
    cursor = await db.execute("SELECT role, disabled FROM admins WHERE user_id = ?", (user_id,))
    row = await cursor.fetchone()
    if row is not None:
        if int(row["disabled"] or 0):
            return None
        role = str(row["role"] or "")
        return role if role in ROLES else "viewer"
    if user_id in get_settings().admin_ids_set and not await has_enabled_owner(db):
        return "owner"
    return None


def outranks_or_equals(target_role: str | None, actor_role: str) -> bool:
    """True when ``target_role`` is an admin role ranked at or above the actor's."""
    return target_role is not None and role_rank(target_role) >= role_rank(actor_role)


async def _guard_target(db, admin: dict[str, Any], user_id: int) -> None:
    """403 ``CANNOT_TARGET_ADMIN{role}`` when the target outranks (or equals) the actor."""
    role = await target_admin_role(db, user_id)
    if outranks_or_equals(role, str(admin.get("role") or "")):
        raise errors.api_error(403, CANNOT_TARGET_ADMIN, role=role)


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------
async def _revoke_sessions(db, user_id: int) -> dict[str, int]:
    """Delete the user's Mini App sessions (and unused bot hand-off tokens).

    Runs inside the caller's transaction and does not commit. A session row is
    the identity behind a Bearer token (``webapp.core.session``), so once it is
    gone every token minted for it answers 401 ``SESSION_EXPIRED``.
    """
    revoked = {"sessions": 0, "handoff_tokens": 0}
    tables = await _existing_tables(db, ("webapp_sessions", "bot_handoff_tokens"))
    if "webapp_sessions" in tables:
        cursor = await db.execute("DELETE FROM webapp_sessions WHERE user_id = ?", (user_id,))
        revoked["sessions"] = max(0, int(cursor.rowcount or 0))
    if "bot_handoff_tokens" in tables:
        cursor = await db.execute(
            "DELETE FROM bot_handoff_tokens WHERE user_id = ? AND used = 0", (user_id,)
        )
        revoked["handoff_tokens"] = max(0, int(cursor.rowcount or 0))
    return revoked


# ---------------------------------------------------------------------------
# idempotency (admin_idempotency, m018)
# ---------------------------------------------------------------------------
def _idempotency_key(request: Request) -> str | None:
    """The ``X-Idempotency-Key`` header, or None when the client sent none.

    Optional so older clients keep working; a present but malformed key is a
    400 rather than silently ignored (ignoring it would drop the protection the
    client asked for).
    """
    raw = request.headers.get(IDEMPOTENCY_HEADER)
    if raw is None:
        return None
    key = raw.strip()
    if not _IDEMPOTENCY_KEY_RE.fullmatch(key):
        raise errors.validation_error("idempotency_key")
    return key


def _body_hash(fields: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_params(fields).encode()).hexdigest()


async def _claim_idempotency(
    db,
    *,
    actor_id: int,
    action: str,
    key: str,
    target_id: str | None,
    body_hash: str,
) -> dict[str, Any] | None:
    """Claim ``(actor, action, key)`` or return the response it already produced.

    This is the FIRST write of the mutation's transaction. The expired-row
    DELETE takes SQLite's write lock, so a concurrent request with the same key
    blocks right here (busy_timeout) until the first one commits or rolls back,
    and then its INSERT sees the committed row. Taking the lock with a write
    (not a read) is also what keeps ``ledger``'s rule intact: no read snapshot
    is pinned before the balance UPDATE.

    Returns None when the key was claimed (the caller performs the mutation and
    stores its response with :func:`_store_idempotent_response` before the
    commit), or the stored response dict for a replay. A key reused with a
    different body is 409 ``IDEMPOTENCY_CONFLICT``. On a replay and on a
    conflict the transaction is rolled back, so nothing is written.
    """
    now = int(time.time())
    await db.execute(
        "DELETE FROM admin_idempotency WHERE created_at < ?", (now - IDEMPOTENCY_TTL_SECONDS,)
    )
    cursor = await db.execute(
        "INSERT INTO admin_idempotency "
        "(actor_id, action, idem_key, target_id, body_hash, response_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, NULL, ?) "
        "ON CONFLICT (actor_id, action, idem_key) DO NOTHING",
        (int(actor_id), action, key, target_id, body_hash, now),
    )
    if cursor.rowcount:
        return None

    cursor = await db.execute(
        "SELECT body_hash, response_json FROM admin_idempotency "
        "WHERE actor_id = ? AND action = ? AND idem_key = ?",
        (int(actor_id), action, key),
    )
    row = await cursor.fetchone()
    await db.rollback()
    # A committed claim always carries its response (both are written in one
    # transaction), so a missing response can only be a mismatched body.
    if row is None or row["body_hash"] != body_hash or row["response_json"] is None:
        raise errors.api_error(409, IDEMPOTENCY_CONFLICT)
    return json.loads(row["response_json"])


async def _store_idempotent_response(
    db, *, actor_id: int, action: str, key: str, response: dict[str, Any]
) -> None:
    await db.execute(
        "UPDATE admin_idempotency SET response_json = ? "
        "WHERE actor_id = ? AND action = ? AND idem_key = ?",
        (json.dumps(response, separators=(",", ":")), int(actor_id), action, key),
    )


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------
#: A text cell starting with one of these is evaluated as a formula by
#: Excel / LibreOffice / Google Sheets (CSV injection).
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

UTF8_BOM = chr(0xFEFF)

#: Exactly the fields the admin list already shows (``UserListItem``), no more.
CSV_COLUMNS = (
    "user_id",
    "first_name",
    "username",
    "lang",
    "region",
    "district",
    "joined_at",
    "is_pro",
    "pro_until",
    "balance",
    "banned",
    "banned_reason",
    "blocked",
    "last_seen_at",
    "ref_by",
)


def csv_cell(value: Any) -> Any:
    """A value made safe for a spreadsheet cell.

    Text starting with ``= + - @ TAB CR`` gets a leading apostrophe so it is
    shown, never evaluated. Real numbers are left alone (a negative balance is
    data, and quoting it would turn it into text). NUL bytes are dropped. The
    ``csv`` writer does the RFC 4180 quoting of commas, quotes and newlines.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return value
    text = str(value).replace("\x00", "")
    if text.startswith(_FORMULA_PREFIXES):
        text = "'" + text
    return text


def _ts_cell(value: Any) -> str:
    """Unix seconds -> ``YYYY-MM-DD HH:MM:SS`` in Asia/Tashkent; empty when unset."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return ""
    if seconds <= 0:
        return ""
    return datetime.fromtimestamp(seconds, TZ).strftime("%Y-%m-%d %H:%M:%S")


def _csv_row(row) -> list[Any]:
    item = _list_item(row)
    return [
        csv_cell(item["user_id"]),
        csv_cell(item["first_name"]),
        csv_cell(item["username"]),
        csv_cell(item["lang"]),
        csv_cell(item["region"]),
        csv_cell(item["district"]),
        _ts_cell(item["date"]),
        csv_cell(item["is_pro"]),
        _ts_cell(item["pro_until"]),
        csv_cell(item["balance"]),
        csv_cell(item["banned"]),
        csv_cell(item["banned_reason"]),
        csv_cell(item["blocked"]),
        _ts_cell(item["last_seen_at"]),
        csv_cell(item["ref_by"]),
    ]


# ---------------------------------------------------------------------------
# list filters (shared by the list and the CSV export)
# ---------------------------------------------------------------------------
def _user_filters(
    *,
    q: str | None,
    pro: bool | None,
    banned: bool | None,
    blocked: bool | None,
    lang: str | None,
    region: str | None,
    date_from: int | None,
    date_to: int | None,
) -> tuple[list[str], list[Any], bool]:
    """``(where_clauses, params, like_search)`` for the list filters."""
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
    return where, params, like_search


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
    #: The admin role the user holds (None for a regular user) ...
    target_role: str | None = None
    #: ... and whether the viewing admin outranks it, i.e. may act on this user.
    actionable: bool = True


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
    #: Mini App sessions deleted by this ban (0 on unban).
    sessions_revoked: int = 0


class ResetRequest(BaseModel):
    # In the body for the same reason as ``BalanceRequest.user_id``.
    user_id: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=MAX_NOTE)


class ResetResponse(BaseModel):
    ok: bool
    user_id: int
    amount: int
    new_balance: int
    tx_id: int


class RevokeSessionsRequest(BaseModel):
    # Bound into the confirmation token, so it travels in the body as well.
    user_id: int = Field(gt=0)


class RevokeSessionsResponse(BaseModel):
    ok: bool
    user_id: int
    revoked: int


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

    where, params, like_search = _user_filters(
        q=q,
        pro=pro,
        banned=banned,
        blocked=blocked,
        lang=lang,
        region=region,
        date_from=date_from,
        date_to=date_to,
    )

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
# CSV export
#
# Registered BEFORE ``/{user_id}``: that route's path pattern would otherwise
# swallow ``export.csv`` and answer 422.
# ---------------------------------------------------------------------------
ExportConnector = Callable[[], Awaitable[Any]]


def get_export_connector() -> ExportConnector:
    """How the export stream opens its own connection (a dependency for tests).

    The request's pooled connection cannot serve the body: FastAPI closes
    ``yield`` dependencies before a StreamingResponse starts iterating. The
    stream therefore opens one standalone connection and closes it when the
    body ends (or the client goes away). Exports are limited to 2/minute per
    actor, so this never competes with the pool in a meaningful way.
    """
    return open_connection


def export_filters(
    q: str | None = Query(default=None, max_length=64),
    pro: bool | None = Query(default=None),
    banned: bool | None = Query(default=None),
    blocked: bool | None = Query(default=None),
    lang: str | None = Query(default=None, max_length=8),
    region: str | None = Query(default=None, max_length=32),
    date_from: int | None = Query(default=None, alias="from", ge=0),
    date_to: int | None = Query(default=None, alias="to", ge=0),
    sort: str = Query(default="date"),
) -> dict[str, Any]:
    """Dependency: the list endpoint's filter and sort parameters, parsed."""
    return {
        "q": q,
        "pro": pro,
        "banned": banned,
        "blocked": blocked,
        "lang": lang,
        "region": region,
        "date_from": date_from,
        "date_to": date_to,
        "sort": sort,
    }


def canonical_export_filters(filters: dict[str, Any]) -> dict[str, Any]:
    """The filters as one canonical dict: what the audit row records and what a
    download link's token is signed over. Unset filters are left out (not
    ``null``), matching what a JSON client sends for ``undefined``; the keys are
    the query-string names (``from``/``to``)."""
    params: dict[str, Any] = {"sort": filters["sort"]}
    term = (filters["q"] or "").strip()
    if term:
        params["q"] = term
    for name, value in (
        ("pro", filters["pro"]),
        ("banned", filters["banned"]),
        ("blocked", filters["blocked"]),
        ("lang", filters["lang"] or None),
        ("region", filters["region"] or None),
        ("from", filters["date_from"]),
        ("to", filters["date_to"]),
    ):
        if value is not None:
            params[name] = value
    return params


def _export_link_mac(actor_id: int, params: dict[str, Any], exp: int, nonce: str) -> str:
    """HMAC-SHA256 (``WEBAPP_SECRET``) over actor, filters, expiry and nonce.

    The message starts with ``EXPORT_DOWNLOAD_ACTION`` while a confirm token's
    starts with the actor id, so neither kind of token verifies as the other.
    """
    message = (
        f"{EXPORT_DOWNLOAD_ACTION}|{int(actor_id)}|{canonical_params(params)}|{int(exp)}|{nonce}"
    ).encode()
    return hmac.new(get_settings().WEBAPP_SECRET.encode(), message, hashlib.sha256).hexdigest()


def issue_export_link_token(actor_id: int, params: dict[str, Any]) -> str:
    """``<exp>.<nonce>.<mac>``: valid ``EXPORT_LINK_TTL_SECONDS``, unique per mint.

    The random nonce is what the single-use claim stores, so two links minted
    for the same actor and filters in the same second are still two links.
    """
    exp = int(time.time()) + EXPORT_LINK_TTL_SECONDS
    nonce = secrets.token_hex(16)
    return f"{exp}.{nonce}.{_export_link_mac(actor_id, params, exp, nonce)}"


_NONCE_RE = re.compile(r"^[0-9a-f]{32}$")


def verify_export_link_token(token: str, actor_id: int, params: dict[str, Any]) -> str | None:
    """The token's nonce when it is valid for this actor and these filters, else None."""
    parts = str(token or "").strip().split(".")
    if len(parts) != 3:
        return None
    exp_str, nonce, signature = parts
    try:
        exp = int(exp_str)
    except ValueError:
        return None
    now = int(time.time())
    if exp <= now or exp > now + EXPORT_LINK_TTL_SECONDS + 5:
        return None
    if not _NONCE_RE.fullmatch(nonce):
        return None
    if not hmac.compare_digest(_export_link_mac(actor_id, params, exp, nonce), signature):
        return None
    return nonce


class ExportLinkResponse(BaseModel):
    token: str
    expires_in: int


async def require_export_link(
    filters: dict[str, Any] = Depends(export_filters),
    actor: int = Query(..., gt=0),
    dl: str = Query(..., min_length=1, max_length=256),
    db=Depends(get_db),
) -> dict[str, Any]:
    """Dependency: the admin (``admin``+) a CSV download link was minted for.

    ``Telegram.WebApp.downloadFile`` fetches a plain HTTPS URL without our
    headers, so it cannot carry the Bearer session the normal export uses.
    The link carries ``actor=<id>&dl=<token>`` instead: ``dl`` comes from
    ``POST /admin/users/export/link`` (:func:`issue_export_link_token`); its
    MAC binds that actor and exactly these filters, and it dies after
    ``EXPORT_LINK_TTL_SECONDS``. The actor's role and ban are re-read here (so
    a revoked or banned admin's link is dead), and the endpoint claims the
    token's nonce once (:func:`_consume_download_link`), so a leaked link
    cannot be replayed.
    """
    params = canonical_export_filters(filters)
    nonce = verify_export_link_token(dl, int(actor), params)
    if nonce is None:
        raise errors.api_error(403, errors.CONFIRMATION_REQUIRED, action=EXPORT_DOWNLOAD_ACTION)
    role = await resolve_admin_role(db, int(actor))
    if role is None:
        raise errors.api_error(403, errors.ADMIN_REQUIRED)
    if role_rank(role) < role_rank("admin"):
        raise errors.api_error(403, errors.ADMIN_REQUIRED, required_role="admin")
    # The same ban check ``require_admin`` makes: this route skips that dependency.
    if await is_banned(db, int(actor)):
        raise errors.api_error(403, USER_BANNED)
    return {"user_id": int(actor), "role": role, "link_nonce": nonce}


# Same marker ``require_role`` sets: this dependency enforces role ``admin``
# (tests/test_admin_routes_protected.py walks route trees for it).
require_export_link.__require_role__ = "admin"  # type: ignore[attr-defined]


async def _consume_download_link(
    db, actor_id: int, nonce: str, params: dict[str, Any]
) -> None:
    """Claim the link's nonce once (``admin_idempotency``); a second use is refused.

    Committed together with the export's audit row, before the body streams.
    The row outlives the link (retention purges ``admin_idempotency`` after
    ``IDEMPOTENCY_TTL_SECONDS``), so a replay is refused for the link's whole life.
    """
    cursor = await db.execute(
        "INSERT INTO admin_idempotency "
        "(actor_id, action, idem_key, target_id, body_hash, response_json, created_at) "
        "VALUES (?, ?, ?, NULL, ?, NULL, ?) "
        "ON CONFLICT (actor_id, action, idem_key) DO NOTHING",
        (
            int(actor_id),
            EXPORT_DOWNLOAD_ACTION,
            nonce,
            _body_hash(params),
            int(time.time()),
        ),
    )
    if not cursor.rowcount:
        await db.rollback()
        raise errors.api_error(403, errors.CONFIRMATION_REQUIRED, action=EXPORT_DOWNLOAD_ACTION)


async def _iter_export_rows(
    conn, where: list[str], params: list[Any], sort_column: str, max_rows: int
) -> AsyncIterator[list[Any]]:
    """Chunks of at most ``EXPORT_CHUNK`` rows, in the list endpoint's order.

    Same keyset walk as the list: non-NULL sort values by ``(value, user_id)``
    DESC, then the NULL tail by ``user_id`` DESC. Never more than one chunk is
    held in memory.
    """
    remaining = max_rows
    last: tuple[Any, int] | None = None
    while remaining > 0:
        clauses = [*where, f"{sort_column} IS NOT NULL"]
        args = list(params)
        if last is not None:
            clause, extra = _keyset_clause(sort_column, last[0], last[1])
            clauses.append(clause)
            args.extend(extra)
        want = min(EXPORT_CHUNK, remaining)
        cursor = await conn.execute(
            f"SELECT {LIST_COLUMNS}, {sort_column} AS sort_value FROM users u "
            f"WHERE {' AND '.join(clauses)} ORDER BY {sort_column} DESC, u.user_id DESC LIMIT ?",
            (*args, want),
        )
        rows = list(await cursor.fetchall())
        if not rows:
            break
        yield rows
        remaining -= len(rows)
        last = (rows[-1]["sort_value"], int(rows[-1]["user_id"]))
        if len(rows) < want:
            break

    last_id: int | None = None
    while remaining > 0:
        clauses = [*where, f"{sort_column} IS NULL"]
        args = list(params)
        if last_id is not None:
            clauses.append("u.user_id < ?")
            args.append(last_id)
        want = min(EXPORT_CHUNK, remaining)
        cursor = await conn.execute(
            f"SELECT {LIST_COLUMNS} FROM users u WHERE {' AND '.join(clauses)} "
            "ORDER BY u.user_id DESC LIMIT ?",
            (*args, want),
        )
        rows = list(await cursor.fetchall())
        if not rows:
            break
        yield rows
        remaining -= len(rows)
        last_id = int(rows[-1]["user_id"])
        if len(rows) < want:
            break


def _drain(buffer: io.StringIO) -> bytes:
    data = buffer.getvalue().encode("utf-8")
    buffer.seek(0)
    buffer.truncate(0)
    return data


async def _csv_stream(
    connect: ExportConnector,
    where: list[str],
    params: list[Any],
    sort_column: str,
    max_rows: int,
) -> AsyncIterator[bytes]:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    # BOM: Excel only reads a CSV as UTF-8 (Cyrillic, o'/g') when it starts with one.
    buffer.write(UTF8_BOM)
    writer.writerow(CSV_COLUMNS)
    yield _drain(buffer)

    conn = await connect()
    try:
        async for rows in _iter_export_rows(conn, where, params, sort_column, max_rows):
            for row in rows:
                writer.writerow(_csv_row(row))
            yield _drain(buffer)
    finally:
        await conn.close()


async def _export_response(
    request: Request,
    db,
    connect: ExportConnector,
    admin: dict[str, Any],
    filters: dict[str, Any],
) -> StreamingResponse:
    """Shared body of both export routes: count, audit, commit, then stream."""
    sort = filters["sort"]
    if sort not in SORT_COLUMNS:
        raise errors.validation_error("sort")
    sort_column = SORT_COLUMNS[sort]
    where, params, _like = _user_filters(
        q=filters["q"],
        pro=filters["pro"],
        banned=filters["banned"],
        blocked=filters["blocked"],
        lang=filters["lang"],
        region=filters["region"],
        date_from=filters["date_from"],
        date_to=filters["date_to"],
    )
    canonical = canonical_export_filters(filters)
    link_nonce = admin.get("link_nonce")
    if link_nonce is not None:
        await _consume_download_link(db, int(admin["user_id"]), link_nonce, canonical)

    filter_sql = (" WHERE " + " AND ".join(where)) if where else ""
    count_cursor = await db.execute(
        f"SELECT COUNT(*) FROM (SELECT 1 FROM users u{filter_sql} LIMIT ?)",
        (*params, EXPORT_MAX_ROWS + 1),
    )
    matched = int((await count_cursor.fetchone())[0])
    row_count = min(matched, EXPORT_MAX_ROWS)
    truncated = matched > EXPORT_MAX_ROWS

    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="users.export",
        target_type="users",
        target_id=None,
        payload={
            "filters": canonical,
            "row_count": row_count,
            "truncated": truncated,
            "via": "link" if link_nonce is not None else "session",
        },
        ip=_client_ip(request),
    )
    await db.commit()

    filename = f"users-{datetime.now(TZ):%Y%m%d-%H%M}.csv"
    return StreamingResponse(
        _csv_stream(connect, where, params, sort_column, row_count),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Export-Rows": str(row_count),
            "X-Export-Truncated": "1" if truncated else "0",
        },
    )


@router.get("/export.csv")
@limiter.limit("2/minute")
async def export_users_csv(
    request: Request,
    filters: dict[str, Any] = Depends(export_filters),
    admin=Depends(require_admin_role),
    db=Depends(get_db),
    connect: ExportConnector = Depends(get_export_connector),
) -> StreamingResponse:
    """The user list as CSV: the list's filters and sort, every page.

    Role ``admin``+ (Bearer session), 2/minute, at most ``EXPORT_MAX_ROWS``
    (100k) rows — the response says how many it carries (``X-Export-Rows``)
    and whether the cap cut it (``X-Export-Truncated: 1``). Columns are exactly
    the list's fields (``CSV_COLUMNS``), text cells are formula-injection safe,
    the file starts with a UTF-8 BOM. One ``users.export`` audit row records
    the filters and the row count; it is committed before the first byte.
    """
    return await _export_response(request, db, connect, admin, filters)


@router.post("/export/link", response_model=ExportLinkResponse)
@limiter.limit("10/minute")
async def mint_export_link(
    request: Request,
    filters: dict[str, Any] = Depends(export_filters),
    admin=Depends(require_admin_role),
) -> ExportLinkResponse:
    """Mint a single-use ``/export/download.csv`` token for these filters.

    Takes the same query parameters as ``/export.csv`` and signs their
    canonical form, so the link must repeat them exactly. Role ``admin``+
    (Bearer session). Minting writes nothing: the download is what gets
    claimed and audited.
    """
    if filters["sort"] not in SORT_COLUMNS:
        raise errors.validation_error("sort")
    token = issue_export_link_token(int(admin["user_id"]), canonical_export_filters(filters))
    return ExportLinkResponse(token=token, expires_in=EXPORT_LINK_TTL_SECONDS)


@router.get("/export/download.csv")
@limiter.limit("2/minute")
async def export_users_csv_link(
    request: Request,
    filters: dict[str, Any] = Depends(export_filters),
    admin=Depends(require_export_link),
    db=Depends(get_db),
    connect: ExportConnector = Depends(get_export_connector),
) -> StreamingResponse:
    """The same export behind a single-use download link (``require_export_link``)."""
    return await _export_response(request, db, connect, admin, filters)


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

    target_role = await target_admin_role(db, user_id)

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
        target_role=target_role,
        actionable=not outranks_or_equals(target_role, str(admin.get("role") or "")),
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

    # Reads only, outside any transaction: nothing is pinned before the UPDATE.
    await _guard_target(db, admin, user_id)

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
    response: Response,
    body: BalanceRequest,
    user_id: int = Path(..., gt=0),
    admin=Depends(require_admin_role),
    db=Depends(get_db),
) -> BalanceResponse:
    """Credit or debit the balance (confirm token ``users.balance``).

    ``X-Idempotency-Key`` (optional for old clients, always sent by the Mini
    App): the same actor + key within 24 h returns the original response with
    ``Idempotent-Replayed: true`` and writes nothing; the same key with a
    different body is 409 ``IDEMPOTENCY_CONFLICT``.
    """
    if int(body.user_id) != user_id:
        raise errors.validation_error("user_id")
    if body.amount == 0:
        raise errors.validation_error("amount")
    note = _clean_note(body.note)
    idem_key = _idempotency_key(request)
    actor_id = int(admin["user_id"])

    await _guard_target(db, admin, user_id)

    if idem_key is not None:
        replay = await _claim_idempotency(
            db,
            actor_id=actor_id,
            action="users.balance",
            key=idem_key,
            target_id=str(user_id),
            body_hash=_body_hash({"user_id": user_id, "amount": int(body.amount), "note": note}),
        )
        if replay is not None:
            response.headers[REPLAYED_HEADER] = "true"
            return BalanceResponse(**replay)

    try:
        result = await ledger.apply_balance_change(
            db,
            user_id=user_id,
            amount=int(body.amount),
            kind="admin_credit",
            actor_id=actor_id,
            note=note,
            require_sufficient=body.amount < 0,
        )
    except ledger.LedgerError as exc:
        _raise_ledger_error(exc)
        raise  # pragma: no cover - _raise_ledger_error always raises
    except ValueError as exc:
        raise errors.validation_error("amount") from exc

    outcome = BalanceResponse(
        ok=True,
        user_id=user_id,
        amount=int(body.amount),
        new_balance=int(result["balance_after"]),
        tx_id=int(result["tx_id"]),
    )

    await log_admin_action(
        db,
        actor_id=actor_id,
        action="users.balance",
        target_type="user",
        target_id=str(user_id),
        payload={
            "amount": int(body.amount),
            "balance_after": int(result["balance_after"]),
            "tx_id": int(result["tx_id"]),
            "note": note,
            "idempotency_key": idem_key,
        },
        ip=_client_ip(request),
    )
    if idem_key is not None:
        await _store_idempotent_response(
            db, actor_id=actor_id, action="users.balance", key=idem_key, response=outcome.model_dump()
        )
    await db.commit()
    return outcome


@router.post(
    "/{user_id}/reset",
    response_model=ResetResponse,
    dependencies=[Depends(require_reset_confirmation)],
)
@limiter.limit("10/minute")
async def reset_user(
    request: Request,
    body: ResetRequest,
    user_id: int = Path(..., gt=0),
    admin=Depends(require_admin_role),
    db=Depends(get_db),
) -> ResetResponse:
    """Zero the balance and drop Pro (confirm token ``users.reset``), rank-checked."""
    if int(body.user_id) != user_id:
        raise errors.validation_error("user_id")
    note = _clean_note(body.note)
    actor_id = int(admin["user_id"])

    await _guard_target(db, admin, user_id)

    try:
        result = await ledger.reset_user(db, user_id=user_id, actor_id=actor_id, note=note)
    except ledger.LedgerError as exc:
        _raise_ledger_error(exc)
        raise  # pragma: no cover - _raise_ledger_error always raises

    await log_admin_action(
        db,
        actor_id=actor_id,
        action="users.reset",
        target_type="user",
        target_id=str(user_id),
        payload={"amount": int(result["amount"]), "tx_id": int(result["tx_id"]), "note": note},
        ip=_client_ip(request),
    )
    await db.commit()
    return ResetResponse(
        ok=True,
        user_id=user_id,
        amount=int(result["amount"]),
        new_balance=0,
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
    """Ban or unban. A ban also deletes the user's sessions, in the same transaction."""
    reason = _clean_note(body.reason)
    await _guard_target(db, admin, user_id)

    db_cursor = await db.execute(
        "UPDATE users SET banned = ?, banned_reason = ? WHERE user_id = ?",
        (1 if body.banned else 0, reason if body.banned else None, user_id),
    )
    if not db_cursor.rowcount:
        raise errors.not_found("user")

    revoked = {"sessions": 0, "handoff_tokens": 0}
    if body.banned:
        revoked = await _revoke_sessions(db, user_id)

    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="users.ban",
        target_type="user",
        target_id=str(user_id),
        payload={
            "banned": body.banned,
            "reason": reason,
            "sessions_revoked": revoked["sessions"],
            "handoff_revoked": revoked["handoff_tokens"],
        },
        ip=_client_ip(request),
    )
    await db.commit()

    return BanResponse(
        ok=True,
        user_id=user_id,
        banned=body.banned,
        reason=reason if body.banned else None,
        sessions_revoked=revoked["sessions"],
    )


@router.post(
    "/{user_id}/sessions/revoke",
    response_model=RevokeSessionsResponse,
    dependencies=[Depends(require_sessions_confirmation)],
)
@limiter.limit("10/minute")
async def revoke_user_sessions(
    request: Request,
    body: RevokeSessionsRequest,
    user_id: int = Path(..., gt=0),
    admin=Depends(require_admin_role),
    db=Depends(get_db),
) -> RevokeSessionsResponse:
    """Sign the user out of the Mini App everywhere, without banning them.

    Confirm token ``users.sessions_revoke`` bound to ``user_id``. The user can
    open the Mini App again (a new ``/auth/launch`` mints a new session); what
    this ends is every session that exists now.
    """
    if int(body.user_id) != user_id:
        raise errors.validation_error("user_id")
    await _guard_target(db, admin, user_id)

    db_cursor = await db.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    if await db_cursor.fetchone() is None:
        raise errors.not_found("user")

    revoked = await _revoke_sessions(db, user_id)
    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="users.sessions_revoke",
        target_type="user",
        target_id=str(user_id),
        payload={
            "sessions_revoked": revoked["sessions"],
            "handoff_revoked": revoked["handoff_tokens"],
        },
        ip=_client_ip(request),
    )
    await db.commit()
    return RevokeSessionsResponse(ok=True, user_id=user_id, revoked=revoked["sessions"])


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
    await _guard_target(db, admin, user_id)

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
