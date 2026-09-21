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
  crash are reset once at loop start (``reset_stale_claims``).
* **Cancellable.** ``status`` is re-read at every batch boundary.

Both the bot (``src/handlers/admin.py``) and the API
(``webapp/routers/admin_broadcasts.py``) create jobs through
``create_broadcast``/``queue_broadcast`` here, so the targeting rules exist
once.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup

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
        sender = bot.copy_message if target.get("forward_mode") == "copy" else bot.forward_message
        return await sender(user_id, job["forward_chat_id"], job["forward_message_id"])

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


async def _deliver(bot, job: dict[str, Any], user_id: int) -> dict[str, Any]:
    """Send once, retrying a single time on flood wait. Never raises."""
    for attempt in (0, 1):
        try:
            message = await send_to_user(bot, job, user_id)
        except TelegramRetryAfter as exc:
            if attempt:
                return {"user_id": user_id, "status": "failed", "error": "flood_wait"}
            logger.warning("broadcast %s: flood wait %ss", job["id"], exc.retry_after)
            await asyncio.sleep(float(exc.retry_after))
            continue
        except TelegramForbiddenError:
            return {"user_id": user_id, "status": "blocked", "error": "forbidden"}
        except Exception as exc:  # noqa: BLE001 - one bad chat must not stop the run
            logger.warning("broadcast %s: user %s failed: %s", job["id"], user_id, exc)
            return {"user_id": user_id, "status": "failed", "error": str(exc)[:300]}
        return {
            "user_id": user_id,
            "status": "sent",
            "error": None,
            "file_id": _extract_file_id(message),
        }
    return {"user_id": user_id, "status": "failed", "error": "flood_wait"}  # pragma: no cover


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

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


async def _next_broadcast_id(conn) -> int | None:
    cursor = await conn.execute(
        "SELECT id FROM broadcasts WHERE status IN ('queued', 'running') ORDER BY id LIMIT 1"
    )
    row = await cursor.fetchone()
    return int(row[0]) if row else None


async def _claim_batch(conn, broadcast_id: int, limit: int) -> list[int]:
    """Atomically take up to ``limit`` pending targets for this worker."""
    select_pending = (
        "SELECT user_id FROM broadcast_targets "
        "WHERE broadcast_id = ? AND status = 'pending' ORDER BY user_id LIMIT ?"
    )
    now = int(time.time())
    if _HAS_RETURNING:
        cursor = await conn.execute(
            "UPDATE broadcast_targets SET status = 'sending', claimed_at = ? "
            f"WHERE broadcast_id = ? AND user_id IN ({select_pending}) RETURNING user_id",
            (now, broadcast_id, broadcast_id, limit),
        )
        claimed = [int(row[0]) for row in await cursor.fetchall()]
        await conn.commit()
        return claimed

    await conn.execute("BEGIN IMMEDIATE")  # pragma: no cover - SQLite < 3.35
    try:
        cursor = await conn.execute(select_pending, (broadcast_id, limit))
        claimed = [int(row[0]) for row in await cursor.fetchall()]
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
    conn, broadcast_id: int, results: list[dict[str, Any]], file_id: str | None
) -> None:
    """Persist a finished batch: targets, users.blocked, progress counters."""
    now = int(time.time())
    sent = [r for r in results if r["status"] == "sent"]
    blocked = [r for r in results if r["status"] == "blocked"]
    failed = [r for r in results if r["status"] == "failed"]

    await conn.execute("BEGIN IMMEDIATE")
    try:
        await conn.executemany(
            # claimed_at is cleared: the row has reached a terminal state, so
            # it must not look like an outstanding claim to reset_stale_claims.
            "UPDATE broadcast_targets SET status = ?, error = ?, sent_at = ?, claimed_at = NULL "
            "WHERE broadcast_id = ? AND user_id = ?",
            [
                (r["status"], r["error"], now if r["status"] == "sent" else None, broadcast_id, r["user_id"])
                for r in results
            ],
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
            "UPDATE broadcasts SET sent = sent + ?, failed = failed + ?, blocked = blocked + ? "
            "WHERE id = ?",
            (len(sent), len(failed), len(blocked), broadcast_id),
        )
        if file_id:
            await conn.execute(
                "UPDATE broadcasts SET media_file_id = ? WHERE id = ? AND media_file_id IS NULL",
                (file_id, broadcast_id),
            )
        await conn.execute("COMMIT")
    except Exception:
        await conn.execute("ROLLBACK")
        raise


async def _finish(conn, broadcast_id: int, status: str, error: str | None = None) -> None:
    await conn.execute(
        "UPDATE broadcasts SET status = ?, error = COALESCE(?, error), finished_at = ? WHERE id = ?",
        (status, error, int(time.time()), broadcast_id),
    )
    await conn.commit()


async def _remaining(conn, broadcast_id: int) -> tuple[int, int]:
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
    batch_size: int = BATCH_SIZE,
    max_batches: int | None = None,
) -> dict[str, Any] | None:
    """Drain one broadcast, one connection per batch."""
    connect = connect or _default_connect()
    bucket = bucket or TokenBucket()
    batches = 0

    while max_batches is None or batches < max_batches:
        batches += 1
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
                    (int(time.time()), broadcast_id),
                )
                await conn.commit()

            claimed = await _claim_batch(conn, broadcast_id, batch_size)
            if not claimed:
                pending, sending = await _remaining(conn, broadcast_id)
                if pending == 0 and sending == 0:
                    await _finish(conn, broadcast_id, "done")
                    return await broadcast_progress(conn, broadcast_id)
                # Another worker owns the rest; come back on the next poll.
                return await broadcast_progress(conn, broadcast_id)

            # No write transaction is open from here until the batch is done.
            results: list[dict[str, Any]] = []
            new_file_id: str | None = None
            for user_id in claimed:
                await bucket.acquire()
                result = await _deliver(bot, job, user_id)
                if not job.get("media_file_id") and result.get("file_id"):
                    new_file_id = result["file_id"]
                    job["media_file_id"] = new_file_id
                results.append(result)

            await _write_results(conn, broadcast_id, results, new_file_id)
    return None


#: A claim older than this is assumed to belong to a worker that died. A batch
#: of 100 sends at the 25 msg/s token-bucket rate takes ~4 s, and a single send
#: retried after a Telegram ``RetryAfter`` adds at most a minute, so ten minutes
#: is far beyond any healthy batch.
STALE_CLAIM_SECONDS = 600


async def reset_stale_claims(conn, *, older_than: int = STALE_CLAIM_SECONDS) -> int:
    """Targets a *crashed* worker left in ``sending`` go back to ``pending``.

    Only claims older than ``older_than`` are reset. Resetting every ``sending``
    row (what this used to do) is not safe with a second worker or a restart
    while one is mid-batch: the in-flight rows would be handed to another
    worker and those users would receive the broadcast twice. Rows predating
    m015 have ``claimed_at IS NULL`` and are treated as stale, which is correct
    — no live worker can have claimed them before the column existed.
    """
    cutoff = int(time.time()) - int(older_than)
    cursor = await conn.execute(
        "UPDATE broadcast_targets SET status = 'pending', claimed_at = NULL "
        "WHERE status = 'sending' AND (claimed_at IS NULL OR claimed_at < ?)",
        (cutoff,),
    )
    await conn.commit()
    return cursor.rowcount or 0


async def process_once(bot, *, connect=None, bucket: TokenBucket | None = None) -> bool:
    """Pick up at most one active broadcast. True when there was work."""
    connect = connect or _default_connect()
    async with connect() as conn:
        broadcast_id = await _next_broadcast_id(conn)
    if broadcast_id is None:
        return False
    await run_broadcast(bot, broadcast_id, connect=connect, bucket=bucket)
    return True


async def broadcast_worker_loop(bot=None, *, poll_interval: float = POLL_INTERVAL_SECONDS) -> None:
    """Entry point wired into the bot process by ``main.py``."""
    if bot is None:
        from config import bot as default_bot

        bot = default_bot
    connect = _default_connect()
    bucket = TokenBucket()
    try:
        async with connect() as conn:
            restored = await reset_stale_claims(conn)
        if restored:
            logger.info("broadcast worker: %s stale claims reset to pending", restored)
    except Exception:  # pragma: no cover - fresh DB without the tables yet
        logger.exception("broadcast worker: stale claim reset failed")

    logger.info("broadcast worker started (poll %.1fs)", poll_interval)
    while True:
        try:
            worked = await process_once(bot, connect=connect, bucket=bucket)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("broadcast worker tick failed")
            worked = False
        # A short breath between jobs; the full poll interval when idle.
        await asyncio.sleep(0.1 if worked else poll_interval)
