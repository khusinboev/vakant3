import aiosqlite

from config import BASE_DIR, BOT_USERNAME, ADMIN_IDS


async def get_referral_gate_state(user_id: int) -> dict[str, int | bool | str]:
    if user_id in ADMIN_IDS:
        return {
            "enabled": False,
            "required": 0,
            "current": 0,
            "unlocked": True,
            "ref_link": f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}",
        }

    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute(
            "SELECT referral_enabled, referral_required_count FROM webapp_admin_settings WHERE singleton = 1"
        )
        settings_row = await cursor.fetchone()
        enabled = bool(int(settings_row[0] or 0)) if settings_row else False
        required = int(settings_row[1] or 0) if settings_row else 0

        cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE ref_by = ?", (user_id,))
        current = int((await cursor.fetchone())[0] or 0)

    unlocked = (not enabled) or required <= 0 or current >= required
    return {
        "enabled": enabled,
        "required": required,
        "current": current,
        "unlocked": unlocked,
        "ref_link": f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}",
    }


def referral_gate_message(state: dict[str, int | bool | str]) -> str:
    current = int(state.get("current") or 0)
    required = int(state.get("required") or 0)
    ref_link = str(state.get("ref_link") or "")
    return (
        "🔒 Botdan foydalanish uchun referral sharti yoqilgan.\n\n"
        f"📊 Holat: {current}/{required}\n"
        "👥 Avval do'stlaringizni taklif qiling:\n"
        f"{ref_link}"
    )
