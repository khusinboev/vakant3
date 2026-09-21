"""Admin system diagnostics: DB/process health, scheduler state, error and
audit log listings.

Not registered here — the coordinator includes this router in webapp/main.py
(see CONTRACT_P12.md).
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import subprocess
import time

from fastapi import APIRouter, Depends, Query, Request

from webapp.core.auth import require_role
from webapp.core.config import BASE_DIR, DB_PATH
from webapp.core.database import get_db
from webapp.core.limiter import limiter

router = APIRouter(prefix="/admin", tags=["admin-system"])
_log = logging.getLogger(__name__)

# Process start time: an approximation of uptime good enough for a dashboard
# (this module is imported once, at process startup, by webapp/main.py).
_PROCESS_STARTED_AT = time.time()

_GIT_SHA_CACHE: str | None = None
_GIT_SHA_RESOLVED = False


async def _table_exists(db, name: str) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1", (name,)
    )
    return await cursor.fetchone() is not None


async def _count(db, table: str, where: str = "") -> int:
    """Exact ``COUNT(*)``. Only for tables that stay small (sessions, running
    broadcasts) — SQLite has no row-count metadata, so a count is a full scan
    of the table or of an index over it."""
    if not await _table_exists(db, table):
        return 0
    try:
        cursor = await db.execute(f"SELECT COUNT(*) FROM {table} {where}")
        row = await cursor.fetchone()
        return int((row[0] if row else 0) or 0)
    except Exception:
        _log.debug("admin_system count failed for %s", table, exc_info=True)
        return 0


#: ``/system`` is polled by the dashboard, and ``users``/``resume_events`` are
#: the two tables that grow without bound. Their counts are estimated from
#: ``MAX(rowid)`` (an index lookup, not a scan) and memoised for a minute, so
#: an open panel cannot turn a health page into a repeated full-table scan.
BIG_COUNT_TTL_SECONDS = 60

_big_count_cache: dict[tuple[str, str], tuple[float, int]] = {}

_DB_FILE_ATTR = "_system_db_file"


async def _db_identity(db) -> str:
    """The database file behind this connection, memoised on it.

    Part of the cache key so an estimate cannot leak between databases (every
    pooled connection reports the same file in production; a test's temporary
    database reports its own)."""
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


async def _estimated_count(db, table: str) -> int:
    """Approximate row count: ``MAX(rowid)``, cached for a minute.

    ``MAX(rowid)`` over-counts by however many rows were deleted (retention
    prunes ``resume_events``), which a health readout tolerates; a full
    ``COUNT(*)`` on a table with millions of rows, on every poll, does not.
    """
    key = (await _db_identity(db), table)
    cached = _big_count_cache.get(key)
    now = time.monotonic()
    if cached is not None and now - cached[0] < BIG_COUNT_TTL_SECONDS:
        return cached[1]
    if not await _table_exists(db, table):
        return 0
    try:
        cursor = await db.execute(f"SELECT MAX(rowid) FROM {table}")
        row = await cursor.fetchone()
        value = int((row[0] if row else 0) or 0)
    except Exception:
        _log.debug("admin_system estimate failed for %s", table, exc_info=True)
        return 0
    _big_count_cache[key] = (now, value)
    return value


def _resolve_git_sha() -> str | None:
    global _GIT_SHA_CACHE, _GIT_SHA_RESOLVED
    if _GIT_SHA_RESOLVED:
        return _GIT_SHA_CACHE
    _GIT_SHA_RESOLVED = True
    env_sha = (os.getenv("GIT_SHA") or "").strip()
    if env_sha:
        _GIT_SHA_CACHE = env_sha
        return _GIT_SHA_CACHE
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            _GIT_SHA_CACHE = result.stdout.strip() or None
    except Exception:
        _log.debug("git rev-parse unavailable", exc_info=True)
        _GIT_SHA_CACHE = None
    return _GIT_SHA_CACHE


async def _redis_reachable() -> bool:
    """Prefer the shared client `src.functions.cache` already exposes."""
    try:
        from src.functions.cache import get_redis

        client = await asyncio.wait_for(get_redis(), timeout=0.5)
        return client is not None
    except Exception:
        pass
    # Fallback: a bounded ping of our own, in case cache.py's helper ever stops
    # exposing get_redis().
    url = (os.getenv("REDIS_URL") or "").strip()
    if not url:
        return False
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(url, socket_connect_timeout=0.2, socket_timeout=0.2)
        try:
            await asyncio.wait_for(client.ping(), timeout=0.2)
            return True
        finally:
            await client.aclose()
    except Exception:
        return False


async def _scheduler_state(db) -> dict:
    if not await _table_exists(db, "webapp_admin_settings"):
        return {
            "auto_post": {"last_run": None, "scheduled_day": None, "next_slots": []},
            "notifications": {"last_run": None},
            "weekly_stats": {"last_week": None},
        }
    cursor = await db.execute("PRAGMA table_info(webapp_admin_settings)")
    columns = {row[1] for row in await cursor.fetchall()}
    wanted = [
        c
        for c in ("auto_post_scheduled_times_json", "auto_post_scheduled_day", "last_weekly_stats_week")
        if c in columns
    ]
    row = {}
    if wanted:
        cursor = await db.execute(
            f"SELECT {', '.join(wanted)} FROM webapp_admin_settings WHERE singleton = 1"
        )
        fetched = await cursor.fetchone()
        row = dict(fetched) if fetched else {}

    next_slots: list = []
    raw_slots = row.get("auto_post_scheduled_times_json")
    if raw_slots:
        try:
            next_slots = json.loads(raw_slots)
        except (TypeError, ValueError):
            next_slots = []

    return {
        # Neither auto-post nor notifications persist a "last successful run"
        # timestamp today (see CLAUDE.md) — only the scheduled-day marker and
        # the slot list are available, so `last_run` stays None rather than
        # being guessed.
        "auto_post": {
            "last_run": None,
            "scheduled_day": row.get("auto_post_scheduled_day") or None,
            "next_slots": next_slots,
        },
        "notifications": {"last_run": None},
        "weekly_stats": {"last_week": row.get("last_weekly_stats_week") or None},
    }


@router.get("/system")
@limiter.limit("60/minute")
async def get_system(
    request: Request,
    admin: dict = Depends(require_role("viewer")),
    db=Depends(get_db),
) -> dict:
    db_path = str(DB_PATH)
    try:
        db_size = os.path.getsize(db_path)
    except OSError:
        db_size = 0
    try:
        wal_size = os.path.getsize(db_path + "-wal")
    except OSError:
        wal_size = 0

    page_count = 0
    try:
        cursor = await db.execute("PRAGMA page_count")
        row = await cursor.fetchone()
        page_count = int((row[0] if row else 0) or 0)
    except Exception:
        _log.debug("PRAGMA page_count failed", exc_info=True)

    counts = {
        # Estimated (see _estimated_count): these two tables are unbounded.
        "users": await _estimated_count(db, "users"),
        "resume_events": await _estimated_count(db, "resume_events"),
        # Exact: retention keeps sessions small, and running broadcasts are
        # counted through idx_broadcasts_status.
        "sessions": await _count(db, "webapp_sessions"),
        "broadcasts_running": await _count(db, "broadcasts", "WHERE status = 'running'"),
    }

    return {
        "db": {"size_bytes": db_size, "wal_bytes": wal_size, "page_count": page_count},
        "counts": counts,
        "schedulers": await _scheduler_state(db),
        "redis": await _redis_reachable(),
        "version": _resolve_git_sha(),
        "uptime": int(time.time() - _PROCESS_STARTED_AT),
    }


def _encode_cursor(value: int) -> str:
    return base64.urlsafe_b64encode(str(int(value)).encode("ascii")).decode("ascii")


def _decode_cursor(cursor: str | None) -> int | None:
    if not cursor:
        return None
    try:
        return int(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii"))
    except Exception:
        return None


@router.get("/errors")
@limiter.limit("60/minute")
async def list_errors(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    source: str | None = None,
    admin: dict = Depends(require_role("viewer")),
    db=Depends(get_db),
) -> dict:
    if not await _table_exists(db, "error_log"):
        return {"items": [], "next_cursor": None, "total": None}

    last_id = _decode_cursor(cursor)
    conditions: list[str] = []
    params: list = []
    if last_id is not None:
        conditions.append("id < ?")
        params.append(last_id)
    if source:
        conditions.append("source = ?")
        params.append(source)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit + 1)

    cursor_rows = await db.execute(
        f"SELECT id, created_at, source, level, message, context_json FROM error_log "
        f"{where} ORDER BY id DESC LIMIT ?",
        tuple(params),
    )
    rows = [dict(r) for r in await cursor_rows.fetchall()]

    next_cursor = None
    if len(rows) > limit:
        next_cursor = _encode_cursor(rows[limit - 1]["id"])
        rows = rows[:limit]

    items = []
    for row in rows:
        context = None
        if row.get("context_json"):
            try:
                context = json.loads(row["context_json"])
            except (TypeError, ValueError):
                context = None
        items.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "source": row["source"],
                "level": row["level"],
                "message": row["message"],
                "context": context,
            }
        )

    return {"items": items, "next_cursor": next_cursor, "total": None}


@router.get("/audit")
@limiter.limit("60/minute")
async def list_audit(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    actor: int | None = None,
    action: str | None = None,
    admin: dict = Depends(require_role("viewer")),
    db=Depends(get_db),
) -> dict:
    if not await _table_exists(db, "admin_audit_log"):
        return {"items": [], "next_cursor": None, "total": None}

    last_id = _decode_cursor(cursor)
    conditions: list[str] = []
    params: list = []
    if last_id is not None:
        conditions.append("id < ?")
        params.append(last_id)
    if actor is not None:
        conditions.append("actor_id = ?")
        params.append(int(actor))
    if action:
        conditions.append("action = ?")
        params.append(action)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit + 1)

    cursor_rows = await db.execute(
        "SELECT id, actor_id, action, target_type, target_id, payload_json, ip, created_at "
        f"FROM admin_audit_log {where} ORDER BY id DESC LIMIT ?",
        tuple(params),
    )
    rows = [dict(r) for r in await cursor_rows.fetchall()]

    next_cursor = None
    if len(rows) > limit:
        next_cursor = _encode_cursor(rows[limit - 1]["id"])
        rows = rows[:limit]

    items = []
    for row in rows:
        payload = None
        if row.get("payload_json"):
            try:
                payload = json.loads(row["payload_json"])
            except (TypeError, ValueError):
                payload = None
        items.append(
            {
                "id": row["id"],
                "actor_id": row["actor_id"],
                "action": row["action"],
                "target_type": row["target_type"],
                "target_id": row["target_id"],
                "payload": payload,
                "ip": row["ip"],
                "created_at": row["created_at"],
            }
        )

    return {"items": items, "next_cursor": next_cursor, "total": None}
