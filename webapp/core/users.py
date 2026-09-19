"""Shared helpers for the ``users`` table."""

import time
from typing import Any

USER_COLUMNS = (
    "user_id, lang, first_name, username, photo_url, date, region, district, "
    "specs, money, user_pro, user_balance"
)


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
