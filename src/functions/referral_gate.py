"""
Referral gate — holatni hisoblashning yagona manbasi.

`compute_referral_state(conn, user_id)` toza funksiya: ochiq aiosqlite ulanishini
oladi, hech qanday admin bypass qilmaydi. Bot ham, API ham shundan foydalanadi.
"""
from __future__ import annotations

from typing import Any

import aiosqlite

from config import ADMIN_IDS, BOT_USERNAME
from src.db.connection import connect
from src.i18n import DEFAULT_LANG, t


async def compute_referral_state(
    conn: aiosqlite.Connection, user_id: int
) -> dict[str, Any]:
    """{enabled, required, count, unlocked} — sozlamalar va taklif qilinganlar soni."""
    enabled = False
    required = 0
    try:
        cursor = await conn.execute(
            "SELECT referral_enabled, referral_required_count "
            "FROM webapp_admin_settings WHERE singleton = 1"
        )
        settings_row = await cursor.fetchone()
        if settings_row is not None:
            enabled = bool(int(settings_row[0] or 0))
            required = int(settings_row[1] or 0)
    except Exception:
        # Jadval hali yaratilmagan bo'lsa — gate o'chirilgan deb hisoblaymiz.
        enabled = False
        required = 0

    count = 0
    try:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM users WHERE ref_by = ?", (user_id,)
        )
        row = await cursor.fetchone()
        count = int((row[0] if row else 0) or 0)
    except Exception:
        count = 0

    unlocked = (not enabled) or required <= 0 or count >= required
    return {
        "enabled": enabled,
        "required": required,
        "count": count,
        "unlocked": unlocked,
    }


def referral_link(user_id: int) -> str:
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"


async def get_referral_gate_state(user_id: int) -> dict[str, Any]:
    """Bot uchun: admin bypass + ref_link bilan boyitilgan holat."""
    if user_id in ADMIN_IDS:
        return {
            "enabled": False,
            "required": 0,
            "count": 0,
            "current": 0,
            "unlocked": True,
            "ref_link": referral_link(user_id),
        }

    async with connect() as conn:
        state = await compute_referral_state(conn, user_id)

    state["current"] = state["count"]
    state["ref_link"] = referral_link(user_id)
    return state


def referral_gate_message(
    state: dict[str, Any], lang: str = DEFAULT_LANG
) -> str:
    current = int(state.get("current") or state.get("count") or 0)
    required = int(state.get("required") or 0)
    ref_link = str(state.get("ref_link") or "")
    return t(lang, "referral.gate", current=current, required=required, link=ref_link)
