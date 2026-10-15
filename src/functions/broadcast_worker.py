"""Broadcast queue: target materialization + the sending worker.

The bot used to loop over every user inside the admin handler: one connection
held open for the whole run, progress only in memory, nothing survived a
restart. Now a broadcast is three rows-worth of state in SQLite —
``broadcasts`` (the job), ``broadcast_targets`` (one row per recipient) — and
this module is the only thing that sends.

Design notes worth keeping:

* **One connection per batch, never per message.** A batch opens a connection,
  claims its targets in a short write transaction, closes that transaction,
  sends, then writes the results in a second short transaction. No write
  transaction is ever held across a Telegram call.
* **Two workers cannot double-send.** Targets are claimed by flipping
  ``pending`` -> ``sending`` with ``UPDATE ... RETURNING`` (a single atomic
  statement); on SQLite < 3.35 the same claim runs inside ``BEGIN IMMEDIATE``.
  A claimed row is owned by exactly one worker.
* **Resumable.** Everything the worker knows lives in the DB, so a restart
  picks the job up at the first ``pending`` target. Claims left behind by a
  crash are reset at loop start and then every ``STALE_RESET_INTERVAL_SECONDS``
  (``reset_stale_claims``), so a worker that died shortly before a restart
  does not leave its rows ``sending`` forever.
* **No starvation.** The picker skips a job whose remaining rows are all
  claimed by someone else, so such a job neither blocks later broadcasts nor
  makes the loop spin.
* **Cancellable, pausable.** ``status`` is re-read at every batch boundary
  (transitions live in ``broadcast_control.set_broadcast_state``).
* **Classified failures.** Every Telegram error becomes an ``error_kind``
  (``classify_error``). ``sent_unparsed`` (aiogram could not deserialize an
  ``ok`` answer, so the message *was* delivered) is not a failure: the row is
  ``sent`` with the kind kept as a warning, never retried and never counted
  towards the early abort. Permanent kinds fail the recipient at once;
  ``flood``/``network`` go back to ``pending`` with ``attempts + 1`` and a
  ``next_attempt_at`` backoff (10 s doubling, at most ``MAX_ATTEMPTS`` sends).
  The claim and the picker only see rows that are due, and a job never
  finishes while a retry is outstanding.
* **One flood pause for the whole process.** A 429 pauses every send
  (``SHARED_PAUSE``) for ``retry_after``; the unsent rest of the batch is
  released rather than held through the pause. The token bucket still paces
  normal sending at 25/s.
* **Early abort.** When Telegram keeps rejecting the message itself, the job
  stops as ``failed``/``content_rejected`` instead of trying every recipient
  (``EARLY_ABORT_MIN_FAILURES``, ``EARLY_ABORT_RATIO``).

Both the bot (``src/handlers/admin.py``) and the API
(``webapp/routers/admin_broadcasts.py``) create jobs through
``create_broadcast``/``queue_broadcast`` here, so the targeting rules exist
once.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

import aiohttp
from aiogram.exceptions import (
    ClientDecodeError,
    TelegramBadRequest,
    TelegramEntityTooLarge,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from pydantic import ValidationError

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 3.0
#: Targets claimed (and progress counters written) per batch.
BATCH_SIZE = 20
#: Telegram tolerates ~30 messages/s to different chats; stay under it.
SEND_RATE_PER_SECOND = 25.0
ACTIVE_STATUSES = ("queued", "running")

SEGMENT_RE = re.compile(
    r"^(all|pro|free|test_admins|lang:(?:uz|ru|en)|region:[A-Za-z0-9_\-]{1,32}|active_days:\d{1,4})$"
)

_HAS_RETURNING = sqlite3.sqlite_version_info >= (3, 35, 0)


# ---------------------------------------------------------------------------
# Targeting
# ---------------------------------------------------------------------------

def is_valid_segment(segment: str) -> bool:
    return bool(SEGMENT_RE.match(str(segment or "")))


async def _user_columns(conn) -> set[str]:
    cursor = await conn.execute("PRAGMA table_info(users)")
    return {row[1] for row in await cursor.fetchall()}


async def _segment_condition(
    conn, segment: str, admin_ids: Sequence[int] | None
) -> tuple[str, list[Any]]:
    """SQL fragment (over ``users u``) selecting the segment's recipients."""
    if not is_valid_segment(segment):
        raise ValueError(f"unknown segment: {segment}")
    if segment == "all":
        return "1 = 1", []
    if segment == "pro":
        return "COALESCE(u.user_pro, 0) = 1", []
    if segment == "free":
        return "COALESCE(u.user_pro, 0) = 0", []
    if segment == "test_admins":
        ids = sorted({int(x) for x in (admin_ids or [])})
        if not ids:
            return "1 = 0", []
        placeholders = ",".join("?" for _ in ids)
        return f"u.user_id IN ({placeholders})", list(ids)
    prefix, _, value = segment.partition(":")
    if prefix == "lang":
        return "u.lang = ?", [value]
    if prefix == "region":
        return "u.region = ?", [value]
    if prefix == "active_days":
        days = max(1, int(value))
        since = int(time.time()) - days * 86400
        columns = await _user_columns(conn)
        # ``last_seen_at`` arrives with a later migration and is NULL for every
        # user until something starts filling it, so the signup timestamp is
        # both the fallback and the second COALESCE branch.
        expression = (
            "COALESCE(u.last_seen_at, u.date, 0)"
            if "last_seen_at" in columns
            else "COALESCE(u.date, 0)"
        )
        return f"{expression} >= ?", [since]
    raise ValueError(f"unknown segment: {segment}")  # pragma: no cover - regex covers it


async def materialize_targets(
    conn, broadcast_id: int, target: dict[str, Any], admin_ids: Sequence[int] | None = None
) -> int:
    """Insert one ``broadcast_targets`` row per recipient. Caller commits.

    Exactly one ``INSERT ... SELECT`` per segment: 50k rows never travel
    through Python.
    """
    segment = str(target.get("segment") or "all")
    condition, params = await _segment_condition(conn, segment, admin_ids)
    if target.get("exclude_blocked", True):
        condition = f"({condition}) AND COALESCE(u.blocked, 0) = 0"
    # Banned users never receive a broadcast, whatever the segment says.
    if "banned" in await _user_columns(conn):
        condition = f"({condition}) AND COALESCE(u.banned, 0) = 0"
    await conn.execute(
        "INSERT OR IGNORE INTO broadcast_targets (broadcast_id, user_id, status) "
        f"SELECT ?, u.user_id, 'pending' FROM users u WHERE {condition}",
        [broadcast_id, *params],
    )
    cursor = await conn.execute(
        "SELECT COUNT(*) FROM broadcast_targets WHERE broadcast_id = ?", (broadcast_id,)
    )
    return int((await cursor.fetchone())[0])


# ---------------------------------------------------------------------------
# Job creation (shared by the bot handlers and the admin API)
# ---------------------------------------------------------------------------

async def create_broadcast(
    conn,
    *,
    actor_id: int,
    kind: str,
    text: str | None = None,
    buttons: Iterable[dict[str, str]] | None = None,
    media_path: str | None = None,
    forward_chat_id: int | None = None,
    forward_message_id: int | None = None,
    target: dict[str, Any] | None = None,
    status: str = "draft",
) -> int:
    """Insert a broadcast row and return its id. Caller commits."""
    cursor = await conn.execute(
        """
        INSERT INTO broadcasts (
            actor_id, status, kind, text, parse_mode, media_path,
            forward_chat_id, forward_message_id, buttons_json, target_json, created_at
        ) VALUES (?, ?, ?, ?, 'HTML', ?, ?, ?, ?, ?, ?)
        """,
        (
            int(actor_id),
            status,
            kind,
            text,
            media_path,
            forward_chat_id,
            forward_message_id,
            json.dumps(list(buttons or []), ensure_ascii=False),
            json.dumps(target or {"segment": "all", "exclude_blocked": True}, ensure_ascii=False),
            int(time.time()),
        ),
    )
    return int(cursor.lastrowid)


async def queue_broadcast(conn, broadcast_id: int, admin_ids: Sequence[int] | None = None) -> int:
    """Materialize targets and move the job to ``queued``. Caller commits."""
    cursor = await conn.execute(
        "SELECT target_json FROM broadcasts WHERE id = ?", (broadcast_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        raise LookupError(f"broadcast {broadcast_id} not found")
    try:
        target = json.loads(row[0] or "{}")
    except json.JSONDecodeError:
        target = {}
    total = await materialize_targets(conn, broadcast_id, target, admin_ids)
    await conn.execute(
        "UPDATE broadcasts SET status = 'queued', total = ?, error = NULL WHERE id = ?",
        (total, broadcast_id),
    )
    return total


async def broadcast_progress(conn, broadcast_id: int) -> dict[str, Any] | None:
    """Counters for the progress message / the admin panel."""
    cursor = await conn.execute(
        "SELECT id, status, total, sent, failed, blocked, error FROM broadcasts WHERE id = ?",
        (broadcast_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "status": row[1],
        "total": row[2],
        "sent": row[3],
        "failed": row[4],
        "blocked": row[5],
        "error": row[6],
        "done": int(row[3]) + int(row[4]) + int(row[5]),
    }


async def broadcast_breakdown(conn, broadcast_id: int) -> dict[str, Any]:
    """Failure kinds and retry state of one job, for the admin detail views.

    ``error_kinds`` counts terminal failures (``failed`` + ``blocked``) per
    kind; rows written before m017 have no kind and are reported as
    ``blocked``/``other`` from their status. ``retry.scheduled`` are rows
    waiting for their next attempt, ``retry.retried`` recipients that needed
    more than one send, ``retry.extra_attempts`` the sends beyond the first.
    """
    cursor = await conn.execute(
        "SELECT COALESCE(error_kind, CASE WHEN status = 'blocked' THEN 'blocked' ELSE 'other' END), "
        "COUNT(*) FROM broadcast_targets "
        "WHERE broadcast_id = ? AND status IN ('failed', 'blocked') GROUP BY 1",
        (broadcast_id,),
    )
    error_kinds = {str(row[0]): int(row[1]) for row in await cursor.fetchall()}
    cursor = await conn.execute(
        "SELECT SUM(status = 'pending' AND next_attempt_at IS NOT NULL), "
        "MIN(CASE WHEN status = 'pending' THEN next_attempt_at END), "
        "SUM(attempts > 1), SUM(MAX(attempts - 1, 0)) "
        "FROM broadcast_targets WHERE broadcast_id = ?",
        (broadcast_id,),
    )
    row = await cursor.fetchone()
    return {
        "error_kinds": error_kinds,
        "retry": {
            "scheduled": int(row[0] or 0),
            "next_attempt_at": int(row[1]) if row[1] is not None else None,
            "retried": int(row[2] or 0),
            "extra_attempts": int(row[3] or 0),
        },
    }


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TokenBucket:
    """Smooth ``rate`` sends per second with a small burst allowance."""

    def __init__(self, rate: float = SEND_RATE_PER_SECOND, capacity: float | None = None) -> None:
        self.rate = float(rate)
        self.capacity = float(capacity if capacity is not None else rate)
        self._tokens = self.capacity
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                self._tokens = min(self.capacity, self._tokens + (now - self._updated) * self.rate)
                self._updated = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                await asyncio.sleep((tokens - self._tokens) / self.rate)


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def _keyboard(buttons_json: str | None) -> InlineKeyboardMarkup | None:
    try:
        buttons = json.loads(buttons_json or "[]")
    except json.JSONDecodeError:
        return None
    rows = [
        [InlineKeyboardButton(text=str(item["text"]), url=str(item["url"]))]
        for item in buttons
        if isinstance(item, dict) and item.get("text") and item.get("url")
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def media_file_path(media_path: str) -> Path:
    """``broadcasts.media_path`` -> absolute path under the DB directory.

    The bot must not import the webapp package, so the uploads root is derived
    from the bot's own DB path. Anything escaping that root is refused.
    """
    from config import BASE_DIR  # local: importing config needs a real TOKEN

    root = (Path(BASE_DIR).resolve().parent / "uploads").resolve()
    candidate = Path(str(media_path or "").strip())
    resolved = candidate.resolve() if candidate.is_absolute() else (root.parent / candidate).resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError(f"media path outside the uploads root: {media_path}")
    return resolved


def _extract_file_id(message: Any) -> str | None:
    """The ``file_id`` Telegram gave back, so the next 49 999 sends reuse it."""
    for attribute in ("photo", "video", "document"):
        value = getattr(message, attribute, None)
        if not value:
            continue
        if isinstance(value, (list, tuple)):
            value = value[-1] if value else None
        file_id = getattr(value, "file_id", None)
        if file_id:
            return str(file_id)
    return None


async def send_to_user(bot, job: dict[str, Any], user_id: int) -> Any:
    """One Telegram call for one recipient. Raises aiogram exceptions."""
    kind = job["kind"]
    if kind == "forward":
        target = job.get("target") or {}
        if target.get("forward_mode") == "copy":
            # copyMessage keeps the entities (incl. custom emoji) and, unlike forwardMessage, takes a keyboard.
            return await bot.copy_message(
                user_id,
                job["forward_chat_id"],
                job["forward_message_id"],
                reply_markup=_keyboard(job.get("buttons_json")),
            )
        return await bot.forward_message(user_id, job["forward_chat_id"], job["forward_message_id"])

    markup = _keyboard(job.get("buttons_json"))
    text = job.get("text") or ""
    if kind == "text":
        return await bot.send_message(user_id, text, reply_markup=markup)

    media = job.get("media_file_id") or FSInputFile(media_file_path(job.get("media_path") or ""))
    caption = text or None
    if kind == "photo":
        return await bot.send_photo(user_id, media, caption=caption, reply_markup=markup)
    if kind == "video":
        return await bot.send_video(user_id, media, caption=caption, reply_markup=markup)
    if kind == "document":
        return await bot.send_document(user_id, media, caption=caption, reply_markup=markup)
    raise ValueError(f"unknown broadcast kind: {kind}")




# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

#: Every ``broadcast_targets.error_kind`` the worker writes.
ERROR_KINDS = (
    "blocked",         # 403: the user blocked the bot / bot can't initiate / kicked
    "deactivated",     # the Telegram account was deleted
    "chat_not_found",  # 400 chat/user not found, PEER_ID_INVALID
    "bad_request",     # 400 about the message itself (entities, file, length, 413)
    "flood",           # 429 RetryAfter
    "network",         # timeouts, aiohttp errors, undecodable answers, Telegram 5xx
    "other",           # anything else (unknown API codes, missing media file, ...)
    "sent_unparsed",   # delivered, but aiogram could not deserialize Telegram's ok answer
)
#: Retried with backoff; every other kind fails the recipient at once.
TRANSIENT_KINDS = frozenset({"flood", "network"})
#: The user cannot be reached any more: the target is ``blocked`` and so is ``users.blocked``.
UNREACHABLE_KINDS = frozenset({"blocked", "deactivated"})
#: Failures that say "this message is wrong", not "this user is wrong". They
#: feed the early abort. ``other`` is in because an unknown error that repeats
#: for every recipient (a deleted media file, a revoked token) is just as
#: hopeless as a rejected entity, and must not run through 50 000 rows either.
CONTENT_KINDS = frozenset({"bad_request", "other"})
#: Not failures: Telegram accepted the message but its answer did not fit
#: aiogram's model. The row is ``sent`` (counted in ``broadcasts.sent``) and
#: keeps the kind and text as a warning; it is never retried, because a retry
#: would deliver the same message again.
DELIVERED_KINDS = frozenset({"sent_unparsed"})

#: Send attempts per recipient, the first one included; the 6th transient
#: failure marks the row ``failed``.
MAX_ATTEMPTS = 6
BACKOFF_BASE_SECONDS = 10
BACKOFF_CAP_SECONDS = 600
#: A pathological ``retry_after`` must not freeze the worker for days.
MAX_RETRY_AFTER_SECONDS = 3600
ERROR_TEXT_LIMIT = 200

#: Early abort: once at least this many recipients failed with a content kind
#: *and* those are at least ``EARLY_ABORT_RATIO`` of everything that reached a
#: verdict on the content (sent + content failures), the job stops as
#: ``failed`` with ``error = 'content_rejected'``. Zero successes is the
#: ratio-1.0 case; 0.95 also stops a message that reached a handful of users
#: before Telegram started refusing it, and never fires on a healthy job where
#: a few hundred bad chats are a rounding error next to the deliveries.
EARLY_ABORT_MIN_FAILURES = 200
EARLY_ABORT_RATIO = 0.95
CONTENT_REJECTED = "content_rejected"

_CHAT_NOT_FOUND_MARKERS = ("chat not found", "user not found", "peer_id_invalid", "chat_id is empty")


def _error_text(exc: BaseException) -> str:
    text = getattr(exc, "message", None) or str(exc) or type(exc).__name__
    return str(text).strip()[:ERROR_TEXT_LIMIT]


def _delivered_but_unparsed(exc: BaseException) -> bool:
    """aiogram 3.14 ``check_response`` raises ``ClientDecodeError`` in two cases:

    * "Failed to decode object" — the body is not JSON (an HTML 502 from a
      proxy). Nothing says Telegram handled the call: retryable ``network``.
    * "Failed to deserialize object" — the body is JSON but does not fit the
      ``Response[...]`` model (``original`` is a pydantic ``ValidationError``).
      Telegram answered, and unless that answer says ``ok: false`` the message
      was delivered: retrying would send it again.
    """
    if not isinstance(exc, ClientDecodeError):
        return False
    if not isinstance(getattr(exc, "original", None), ValidationError):
        return False
    data = getattr(exc, "data", None)
    return not (isinstance(data, dict) and data.get("ok") is False)


def classify_error(exc: BaseException) -> tuple[str, str, float | None]:
    """``(kind, short text, retry_after)`` for one failed send. Pure."""
    text = _error_text(exc)
    if _delivered_but_unparsed(exc):
        return "sent_unparsed", text, None
    if isinstance(exc, TelegramRetryAfter):
        retry_after = max(0.0, min(float(exc.retry_after or 0), MAX_RETRY_AFTER_SECONDS))
        return "flood", text, retry_after
    low = text.lower()
    if "user is deactivated" in low:
        return "deactivated", text, None
    if isinstance(exc, TelegramForbiddenError):
        return "blocked", text, None
    # 413 subclasses TelegramNetworkError in aiogram, but a file that is too
    # large stays too large: it is about the message, never retried.
    if isinstance(exc, TelegramEntityTooLarge):
        return "bad_request", text, None
    if isinstance(
        exc,
        (
            TelegramServerError,
            TelegramNetworkError,
            ClientDecodeError,
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ConnectionError,
        ),
    ):
        return "network", text, None
    if isinstance(exc, (TelegramBadRequest, TelegramNotFound)) and any(
        marker in low for marker in _CHAT_NOT_FOUND_MARKERS
    ):
        return "chat_not_found", text, None
    if isinstance(exc, TelegramBadRequest):
        return "bad_request", text, None
    return "other", text, None


def backoff_seconds(attempts_made: int) -> int:
    """Delay before the next try after ``attempts_made`` earlier attempts:
    10, 20, 40, 80, 160 s (capped at 600)."""
    return min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * 2 ** max(0, int(attempts_made)))


def plan_outcome(result: dict[str, Any], attempts_before: int, now: int) -> dict[str, Any]:
    """What one send result does to its target row. Pure.

    ``attempts`` counts every send made for the row. A transient failure goes
    back to ``pending`` with ``next_attempt_at = now + backoff(attempts made
    before this one)`` — or the ``retry_after`` Telegram asked for, if longer —
    until ``MAX_ATTEMPTS`` sends were made; then it is ``failed``.
    """
    attempts = int(attempts_before) + 1
    if result["status"] == "sent":
        # ``sent_unparsed`` keeps its kind and text as a warning on a sent row.
        warning = result.get("kind") if result.get("kind") in DELIVERED_KINDS else None
        return {
            "status": "sent",
            "error": result.get("error") if warning else None,
            "error_kind": warning,
            "attempts": attempts, "next_attempt_at": None, "sent_at": now,
        }
    kind = result["kind"]
    if kind in TRANSIENT_KINDS and attempts < MAX_ATTEMPTS:
        delay = backoff_seconds(attempts_before)
        if kind == "flood" and result.get("retry_after"):
            delay = max(delay, int(math.ceil(float(result["retry_after"]))))
        return {
            "status": "pending", "error": result["error"], "error_kind": kind,
            "attempts": attempts, "next_attempt_at": now + delay, "sent_at": None,
        }
    return {
        "status": "blocked" if kind in UNREACHABLE_KINDS else "failed",
        "error": result["error"],
        "error_kind": kind,
        "attempts": attempts,
        "next_attempt_at": None,
        "sent_at": None,
    }


# ---------------------------------------------------------------------------
# Process-wide flood pause
# ---------------------------------------------------------------------------

class SendPause:
    """One ``pause_until`` shared by every send in the process.

    A 429 is about the bot, not about the recipient: Telegram wants *all*
    sends to stop for ``retry_after`` seconds. The worker records it here and
    every later send — in this batch, the next batch, any broadcast — waits.
    Pauses only ever extend. Clock and sleep are injectable for tests.
    """

    def __init__(self, clock=time.monotonic, sleep=asyncio.sleep) -> None:
        self._clock = clock
        self._sleep = sleep
        self._until = 0.0

    def pause_for(self, seconds: float) -> None:
        seconds = min(float(seconds or 0), MAX_RETRY_AFTER_SECONDS)
        if seconds <= 0:
            return
        self._until = max(self._until, self._clock() + seconds)

    def remaining(self) -> float:
        return max(0.0, self._until - self._clock())

    async def wait(self) -> None:
        while (left := self.remaining()) > 0:
            await self._sleep(left)


#: The instance the bot process uses. Tests pass their own.
SHARED_PAUSE = SendPause()


async def _deliver(bot, job: dict[str, Any], user_id: int) -> dict[str, Any]:
    """Exactly one send. Never raises; failures come back classified."""
    try:
        message = await send_to_user(bot, job, user_id)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - one bad chat must not stop the run
        kind, text, retry_after = classify_error(exc)
        if kind in DELIVERED_KINDS:
            logger.warning(
                "broadcast %s: user %s delivered, answer unparsed: %s", job["id"], user_id, text
            )
            return {
                "user_id": user_id,
                "status": "sent",
                "kind": kind,
                "error": text,
                "file_id": None,
            }
        if kind == "flood":
            logger.warning("broadcast %s: flood wait %ss", job["id"], retry_after)
        elif kind not in UNREACHABLE_KINDS:
            logger.warning("broadcast %s: user %s failed (%s): %s", job["id"], user_id, kind, text)
        return {
            "user_id": user_id,
            "status": "error",
            "kind": kind,
            "error": text,
            "retry_after": retry_after,
        }
    return {
        "user_id": user_id,
        "status": "sent",
        "kind": None,
        "error": None,
        "file_id": _extract_file_id(message),
    }


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def _now() -> int:
    """Wall-clock epoch seconds for every timestamp the worker writes (tests pin it)."""
    return int(time.time())


def _default_connect():
    from src.db.connection import connect  # local: config import needs a real TOKEN

    return connect


async def _load_job(conn, broadcast_id: int) -> dict[str, Any] | None:
    cursor = await conn.execute(
        """
        SELECT id, actor_id, status, kind, text, media_path, media_file_id,
               forward_chat_id, forward_message_id, buttons_json, target_json
        FROM broadcasts WHERE id = ?
        """,
        (broadcast_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    job = {
        "id": row[0],
        "actor_id": row[1],
        "status": row[2],
        "kind": row[3],
        "text": row[4],
        "media_path": row[5],
        "media_file_id": row[6],
        "forward_chat_id": row[7],
        "forward_message_id": row[8],
        "buttons_json": row[9],
    }
    try:
        job["target"] = json.loads(row[10] or "{}")
    except json.JSONDecodeError:
        job["target"] = {}
    return job


#: A ``pending`` row the worker may take now: never tried, or its retry is due.
_DUE = "(t.next_attempt_at IS NULL OR t.next_attempt_at <= ?)"


async def _next_broadcast_id(conn) -> int | None:
    """Oldest active job this worker can make progress on.

    That is a job with a ``pending`` target that is due (never tried, or its
    ``next_attempt_at`` has passed), or one with nothing left at all — neither
    ``pending`` nor ``sending`` — so ``run_broadcast`` can mark it done.

    Skipped, so they neither starve later broadcasts nor make the loop spin:
    a job whose remaining rows are all ``sending`` (another worker's, or a dead
    one's until ``reset_stale_claims`` hands them back), and a job whose only
    remaining rows are retries scheduled for later.
    """
    now = _now()
    cursor = await conn.execute(
        f"""
        SELECT b.id FROM broadcasts b
        WHERE b.status IN ('queued', 'running')
          AND (
            EXISTS (SELECT 1 FROM broadcast_targets t
                    WHERE t.broadcast_id = b.id AND t.status = 'pending' AND {_DUE})
            OR NOT EXISTS (SELECT 1 FROM broadcast_targets t
                           WHERE t.broadcast_id = b.id AND t.status IN ('pending', 'sending'))
          )
        ORDER BY b.id LIMIT 1
        """,
        (now,),
    )
    row = await cursor.fetchone()
    return int(row[0]) if row else None


async def _claim_batch(conn, broadcast_id: int, limit: int) -> list[int]:
    """Atomically take up to ``limit`` due pending targets; their user ids."""
    return list(await _claim_with_attempts(conn, broadcast_id, limit))


async def _claim_with_attempts(conn, broadcast_id: int, limit: int) -> dict[int, int]:
    """``_claim_batch`` that also returns ``{user_id: attempts made so far}``,
    in claim order — the worker needs the count to plan each outcome."""
    now = _now()
    select_pending = (
        "SELECT t.user_id FROM broadcast_targets t "
        f"WHERE t.broadcast_id = ? AND t.status = 'pending' AND {_DUE} "
        "ORDER BY t.user_id LIMIT ?"
    )
    if _HAS_RETURNING:
        cursor = await conn.execute(
            "UPDATE broadcast_targets SET status = 'sending', claimed_at = ? "
            f"WHERE broadcast_id = ? AND user_id IN ({select_pending}) "
            "RETURNING user_id, attempts",
            (now, broadcast_id, broadcast_id, now, limit),
        )
        rows = await cursor.fetchall()
        await conn.commit()
        return {int(row[0]): int(row[1] or 0) for row in sorted(rows, key=lambda r: int(r[0]))}

    await conn.execute("BEGIN IMMEDIATE")  # pragma: no cover - SQLite < 3.35
    try:
        cursor = await conn.execute(
            select_pending.replace("SELECT t.user_id", "SELECT t.user_id, t.attempts"),
            (broadcast_id, now, limit),
        )
        claimed = {int(row[0]): int(row[1] or 0) for row in await cursor.fetchall()}
        if claimed:
            placeholders = ",".join("?" for _ in claimed)
            await conn.execute(
                f"UPDATE broadcast_targets SET status = 'sending', claimed_at = ? "
                f"WHERE broadcast_id = ? AND user_id IN ({placeholders})",
                (now, broadcast_id, *claimed),
            )
        await conn.execute("COMMIT")
    except Exception:
        await conn.execute("ROLLBACK")
        raise
    return claimed


async def _write_results(
    conn,
    broadcast_id: int,
    results: list[dict[str, Any]],
    file_id: str | None,
    attempts: dict[int, int] | None = None,
    released: Sequence[int] = (),
) -> bool:
    """Persist a finished batch in one short transaction.

    Targets, ``users.blocked``, the progress counters and — when the batch
    pushed the job over the threshold — the early abort. ``released`` are
    claimed rows the batch did not send (a flood pause began): they go back to
    ``pending`` untouched, so the claim is not held across the pause.
    Returns True when the job was aborted as ``content_rejected``.
    """
    now = _now()
    attempts = attempts or {}
    planned = [(r, plan_outcome(r, attempts.get(r["user_id"], 0), now)) for r in results]
    sent = [r for r, o in planned if o["status"] == "sent"]
    blocked = [r for r, o in planned if o["status"] == "blocked"]
    failed = [r for r, o in planned if o["status"] == "failed"]
    content_failed = [r for r in failed if r["kind"] in CONTENT_KINDS]
    aborted = False

    await conn.execute("BEGIN IMMEDIATE")
    try:
        await conn.executemany(
            # claimed_at is cleared: the row is terminal or back in the queue,
            # so it must not look like an outstanding claim to reset_stale_claims.
            "UPDATE broadcast_targets SET status = ?, error = ?, error_kind = ?, attempts = ?, "
            "next_attempt_at = ?, sent_at = ?, claimed_at = NULL "
            "WHERE broadcast_id = ? AND user_id = ?",
            [
                (
                    o["status"], o["error"], o["error_kind"], o["attempts"],
                    o["next_attempt_at"], o["sent_at"], broadcast_id, r["user_id"],
                )
                for r, o in planned
            ],
        )
        if released:
            placeholders = ",".join("?" for _ in released)
            await conn.execute(
                "UPDATE broadcast_targets SET status = 'pending', claimed_at = NULL "
                f"WHERE broadcast_id = ? AND status = 'sending' AND user_id IN ({placeholders})",
                (broadcast_id, *released),
            )
        if blocked:
            placeholders = ",".join("?" for _ in blocked)
            await conn.execute(
                f"UPDATE users SET blocked = 1 WHERE user_id IN ({placeholders}) AND blocked != 1",
                [r["user_id"] for r in blocked],
            )
        if sent:
            placeholders = ",".join("?" for _ in sent)
            await conn.execute(
                f"UPDATE users SET blocked = 0 WHERE user_id IN ({placeholders}) AND blocked != 0",
                [r["user_id"] for r in sent],
            )
        await conn.execute(
            "UPDATE broadcasts SET sent = sent + ?, failed = failed + ?, blocked = blocked + ?, "
            "content_failed = content_failed + ? WHERE id = ?",
            (len(sent), len(failed), len(blocked), len(content_failed), broadcast_id),
        )
        if content_failed:
            cursor = await conn.execute(
                "UPDATE broadcasts SET status = 'failed', error = ?, finished_at = ? "
                "WHERE id = ? AND status IN ('queued', 'running', 'paused') "
                "AND content_failed >= ? AND content_failed >= ? * (sent + content_failed)",
                (CONTENT_REJECTED, now, broadcast_id, EARLY_ABORT_MIN_FAILURES, EARLY_ABORT_RATIO),
            )
            aborted = (cursor.rowcount or 0) > 0
        if file_id:
            await conn.execute(
                "UPDATE broadcasts SET media_file_id = ? WHERE id = ? AND media_file_id IS NULL",
                (file_id, broadcast_id),
            )
        await conn.execute("COMMIT")
    except Exception:
        await conn.execute("ROLLBACK")
        raise
    if aborted:
        logger.warning(
            "broadcast %s aborted: Telegram rejected the content (%s)", broadcast_id, CONTENT_REJECTED
        )
    return aborted


#: Waits before re-trying a result write that hit ``database is locked`` /
#: ``busy`` (each attempt already waited the connection's busy timeout). After
#: the last one the error propagates and the rows stay ``sending`` until
#: ``reset_stale_claims``.
WRITE_RETRY_DELAYS = (0.5, 1.0, 2.0)


def _is_lock_error(exc: BaseException) -> bool:
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    text = str(exc).lower()
    return "locked" in text or "busy" in text


async def _write_results_retrying(conn, broadcast_id: int, *args: Any) -> bool:
    """``_write_results`` that survives a transient lock.

    Losing a batch's results is worse than a short wait: the rows would stay
    ``sending``, be reset after ``STALE_CLAIM_SECONDS`` and sent again. The
    write is one transaction that is rolled back on failure, so a retry
    applies it exactly once.
    """
    delays = tuple(WRITE_RETRY_DELAYS)
    for attempt in range(len(delays) + 1):
        try:
            return await _write_results(conn, broadcast_id, *args)
        except sqlite3.OperationalError as exc:
            if attempt >= len(delays) or not _is_lock_error(exc):
                raise
            logger.warning(
                "broadcast %s: result write failed (%s), retry %s/%s",
                broadcast_id, exc, attempt + 1, len(delays),
            )
            await asyncio.sleep(delays[attempt])
    raise AssertionError("unreachable")  # pragma: no cover


async def _complete_despite_cancel(coro) -> Any:
    """Run ``coro`` to the end even if this task is cancelled meanwhile.

    ``asyncio.shield`` alone is not enough: the awaiting task would leave at
    once and close the connection under the still-running write. Here every
    cancellation is held until the write finished and then re-raised.
    """
    task = asyncio.ensure_future(coro)
    interrupted = False
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            if task.done():
                raise
            interrupted = True
    if interrupted:
        raise asyncio.CancelledError
    return result


async def _persist_batch(conn, broadcast_id: int, *args: Any) -> bool:
    return await _complete_despite_cancel(_write_results_retrying(conn, broadcast_id, *args))


async def _finish(conn, broadcast_id: int, status: str, error: str | None = None) -> None:
    await conn.execute(
        "UPDATE broadcasts SET status = ?, error = COALESCE(?, error), finished_at = ? WHERE id = ?",
        (status, error, _now(), broadcast_id),
    )
    await conn.commit()


async def _finish_done(conn, broadcast_id: int) -> None:
    """``done`` only from an active status: a pause or cancel that landed
    between the last batch and this check is not overwritten."""
    await conn.execute(
        "UPDATE broadcasts SET status = 'done', finished_at = ? "
        "WHERE id = ? AND status IN ('queued', 'running')",
        (_now(), broadcast_id),
    )
    await conn.commit()


async def _remaining(conn, broadcast_id: int) -> tuple[int, int]:
    """``(pending, sending)``; ``pending`` includes retries scheduled for later."""
    cursor = await conn.execute(
        "SELECT SUM(status = 'pending'), SUM(status = 'sending') "
        "FROM broadcast_targets WHERE broadcast_id = ?",
        (broadcast_id,),
    )
    row = await cursor.fetchone()
    return int(row[0] or 0), int(row[1] or 0)


async def run_broadcast(
    bot,
    broadcast_id: int,
    *,
    connect=None,
    bucket: TokenBucket | None = None,
    pause: SendPause | None = None,
    batch_size: int = BATCH_SIZE,
    max_batches: int | None = None,
) -> dict[str, Any] | None:
    """Drain one broadcast, one connection per batch.

    Returns when the job is finished, no longer active, or has nothing due
    right now (every remaining row is someone else's claim or a retry
    scheduled for later).
    """
    connect = connect or _default_connect()
    bucket = bucket or TokenBucket()
    pause = pause or SHARED_PAUSE
    batches = 0

    while max_batches is None or batches < max_batches:
        batches += 1
        # A flood pause is waited out here: no connection open, no row claimed.
        await pause.wait()
        async with connect() as conn:
            job = await _load_job(conn, broadcast_id)
            if job is None:
                return None
            if job["status"] == "cancelled":
                await _finish(conn, broadcast_id, "cancelled")
                return await broadcast_progress(conn, broadcast_id)
            if job["status"] not in ACTIVE_STATUSES:
                return await broadcast_progress(conn, broadcast_id)
            if job["status"] == "queued":
                await conn.execute(
                    "UPDATE broadcasts SET status = 'running', started_at = COALESCE(started_at, ?) "
                    "WHERE id = ? AND status = 'queued'",
                    (_now(), broadcast_id),
                )
                await conn.commit()

            claimed = await _claim_with_attempts(conn, broadcast_id, batch_size)
            if not claimed:
                pending, sending = await _remaining(conn, broadcast_id)
                if pending == 0 and sending == 0:
                    await _finish_done(conn, broadcast_id)
                # Otherwise another worker owns the rest, or the rest are
                # retries that are not due yet; come back on a later poll.
                return await broadcast_progress(conn, broadcast_id)

            # No write transaction is open from here until the batch is done.
            user_ids = list(claimed)
            results: list[dict[str, Any]] = []
            released: list[int] = []
            new_file_id: str | None = None
            try:
                for index, user_id in enumerate(user_ids):
                    if pause.remaining() > 0:
                        # Telegram asked every send to stop: give the rest of the
                        # batch back instead of holding the claim through the pause.
                        released = user_ids[index:]
                        break
                    await bucket.acquire()
                    result = await _deliver(bot, job, user_id)
                    if not job.get("media_file_id") and result.get("file_id"):
                        new_file_id = result["file_id"]
                        job["media_file_id"] = new_file_id
                    if result["kind"] == "flood":
                        pause.pause_for(result.get("retry_after") or 0)
                    results.append(result)
            except asyncio.CancelledError:
                # Shutdown (main.py cancels the worker on every deploy): record
                # what was already delivered, so a restart does not send it
                # again, and hand the rest back. The send that was in flight
                # has an unknown outcome and goes back too (at-least-once).
                recorded = {r["user_id"] for r in results}
                released = [uid for uid in user_ids if uid not in recorded]
                try:
                    await _persist_batch(conn, broadcast_id, results, new_file_id, claimed, released)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("broadcast %s: results lost on shutdown", broadcast_id)
                raise

            await _persist_batch(conn, broadcast_id, results, new_file_id, claimed, released)
    return None


#: A claim older than this is assumed to belong to a worker that died. A batch
#: of 20 sends at the 25 msg/s token-bucket rate takes about a second, and a
#: flood pause is never waited out while holding a claim (the rest of the batch
#: is released first), so ten minutes is far beyond any healthy batch.
STALE_CLAIM_SECONDS = 600
#: How often the running loop looks for stale claims. The UPDATE goes through
#: the partial index on ``claimed_at WHERE status = 'sending'``, so it is cheap.
STALE_RESET_INTERVAL_SECONDS = 60


async def reset_stale_claims(conn, *, older_than: int = STALE_CLAIM_SECONDS) -> int:
    """Targets a *crashed* worker left in ``sending`` go back to ``pending``.

    Only claims older than ``older_than`` are reset. Resetting every ``sending``
    row (what this used to do) is not safe with a second worker or a restart
    while one is mid-batch: the in-flight rows would be handed to another
    worker and those users would receive the broadcast twice. Rows predating
    m015 have ``claimed_at IS NULL`` and are treated as stale, which is correct
    — no live worker can have claimed them before the column existed.
    """
    cutoff = _now() - int(older_than)
    cursor = await conn.execute(
        "UPDATE broadcast_targets SET status = 'pending', claimed_at = NULL "
        "WHERE status = 'sending' AND (claimed_at IS NULL OR claimed_at < ?)",
        (cutoff,),
    )
    await conn.commit()
    return cursor.rowcount or 0


async def process_once(
    bot, *, connect=None, bucket: TokenBucket | None = None, pause: SendPause | None = None
) -> bool:
    """Pick up at most one active broadcast. True when there was work."""
    connect = connect or _default_connect()
    async with connect() as conn:
        broadcast_id = await _next_broadcast_id(conn)
    if broadcast_id is None:
        return False
    await run_broadcast(bot, broadcast_id, connect=connect, bucket=bucket, pause=pause)
    return True


async def _reset_stale(connect) -> int:
    try:
        async with connect() as conn:
            restored = await reset_stale_claims(conn)
    except asyncio.CancelledError:
        raise
    except Exception:  # pragma: no cover - fresh DB without the tables yet
        logger.exception("broadcast worker: stale claim reset failed")
        return 0
    if restored:
        logger.info("broadcast worker: %s stale claims reset to pending", restored)
    return restored


async def broadcast_worker_loop(
    bot=None, *, poll_interval: float = POLL_INTERVAL_SECONDS, connect=None
) -> None:
    """Entry point wired into the bot process by ``main.py``."""
    if bot is None:
        from config import bot as default_bot

        bot = default_bot
    connect = connect or _default_connect()
    bucket = TokenBucket()
    last_reset: float | None = None

    logger.info("broadcast worker started (poll %.1fs)", poll_interval)
    while True:
        now = time.monotonic()
        if last_reset is None or now - last_reset >= STALE_RESET_INTERVAL_SECONDS:
            last_reset = now
            await _reset_stale(connect)
        try:
            worked = await process_once(bot, connect=connect, bucket=bucket, pause=SHARED_PAUSE)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("broadcast worker tick failed")
            worked = False
        # A short breath between jobs; the full poll interval when idle.
        await asyncio.sleep(0.1 if worked else poll_interval)
