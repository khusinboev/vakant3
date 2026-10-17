"""Shared helpers for the ``users`` table."""

import logging
import time
from typing import Any

_log = logging.getLogger(__name__)

#: ``last_seen_at`` is part of the identity SELECT on purpose: the auth path
#: needs the previous value to decide whether to refresh it (see
#: ``touch_last_seen``), and reading it here costs nothing extra. The column
#: comes from migration m009 and from ``USER_EXTRA_COLUMNS`` in
#: ``webapp/core/database.py``, so it exists before any request is served.
USER_COLUMNS = (
    "user_id, lang, first_name, username, photo_url, date, region, district, "
    "specs, money, user_pro, user_balance, last_seen_at"
)

#: How stale ``users.last_seen_at`` may get before the auth path rewrites it.
LAST_SEEN_THROTTLE_SECONDS = 10 * 60


async def get_user_row(db, user_id: int) -> dict[str, Any] | None:
    cursor = await db.execute(
        f"SELECT {USER_COLUMNS} FROM users WHERE user_id = ?",
        (int(user_id),),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def ensure_user(
    db,
    user_id: int,
    lang: str = "uz",
    first_name: str | None = None,
    username: str | None = None,
    photo_url: str | None = None,
) -> dict[str, Any] | None:
    """Return the user row, inserting it (with a normalized lang) when missing."""
    row = await get_user_row(db, user_id)
    if row is None:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, date, lang) VALUES (?, ?, ?)",
            (int(user_id), int(time.time()), lang),
        )
        await db.commit()
        row = await get_user_row(db, user_id)

    if row is not None and (first_name or username or photo_url):
        fields: list[str] = []
        values: list[Any] = []
        if first_name and str(first_name) != str(row.get("first_name") or ""):
            fields.append("first_name = ?")
            values.append(str(first_name))
        if username and str(username) != str(row.get("username") or ""):
            fields.append("username = ?")
            values.append(str(username))
        if photo_url and str(photo_url) != str(row.get("photo_url") or ""):
            fields.append("photo_url = ?")
            values.append(str(photo_url))
        if fields:
            values.append(int(user_id))
            await db.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?", tuple(values))
            await db.commit()
            row = await get_user_row(db, user_id)

    return row


async def get_user_pro(db, user_id: int) -> bool:
    cursor = await db.execute("SELECT user_pro FROM users WHERE user_id = ?", (int(user_id),))
    row = await cursor.fetchone()
    return bool(int((row["user_pro"] if row else None) or 0))


async def set_user_lang(db, user_id: int, lang: str) -> None:
    await db.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, int(user_id)))
    await db.commit()


async def touch_last_seen(db, row: dict[str, Any] | None, now: int | None = None) -> bool:
    """Refresh ``users.last_seen_at``, at most once per 10 minutes per user.

    Called from the auth path once the identity is known, with the row that
    was just loaded — so the throttle costs no extra SELECT. Deliberately a
    standalone statement on the request's pooled connection: it runs before
    the handler body, commits only when it actually wrote a row, and leaves no
    transaction open either way, so it can never fold analytics-grade bookkeeping
    into a handler's transaction.

    The ``WHERE`` clause repeats the throttle so two concurrent requests from
    the same user cannot both write. Failures are swallowed: a stale
    ``last_seen_at`` must never turn into a failed request.

    Returns True when a row was updated.
    """
    if not row:
        return False
    try:
        user_id = int(row["user_id"])
    except (KeyError, TypeError, ValueError):
        return False

    now = int(now if now is not None else time.time())
    try:
        previous = int(row.get("last_seen_at") or 0)
    except (AttributeError, TypeError, ValueError):
        previous = 0
    if previous and now - previous < LAST_SEEN_THROTTLE_SECONDS:
        return False

    cutoff = now - LAST_SEEN_THROTTLE_SECONDS
    try:
        if db.in_transaction:
            # Someone else's transaction is open — do not join it.
            return False
        cursor = await db.execute(
            "UPDATE users SET last_seen_at = ? WHERE user_id = ? "
            "AND (last_seen_at IS NULL OR last_seen_at < ?)",
            (now, user_id, cutoff),
        )
        if cursor.rowcount:
            await db.commit()
            try:
                row["last_seen_at"] = now
            except TypeError:  # pragma: no cover - immutable row mapping
                pass
            return True
        if db.in_transaction:
            await db.rollback()
    except Exception as exc:
        _log.debug("last_seen_at update failed for %s: %s", user_id, exc)
    return False
