from fastapi import HTTPException


async def get_referral_gate_state(db, user_id: int) -> dict[str, int | bool]:
    cursor = await db.execute(
        "SELECT referral_enabled, referral_required_count FROM webapp_admin_settings WHERE singleton = 1"
    )
    settings_row = await cursor.fetchone()

    enabled = bool(int(settings_row["referral_enabled"] or 0)) if settings_row else False
    required = int(settings_row["referral_required_count"] or 0) if settings_row else 0

    cursor = await db.execute("SELECT COUNT(*) FROM users WHERE ref_by = ?", (user_id,))
    current = int((await cursor.fetchone())[0] or 0)
    remaining = max(0, required - current)

    unlocked = (not enabled) or remaining == 0
    return {
        "enabled": enabled,
        "required": required,
        "current": current,
        "remaining": remaining,
        "unlocked": unlocked,
    }


def raise_if_referral_locked(state: dict[str, int | bool]) -> None:
    if bool(state.get("unlocked")):
        return
    required = int(state.get("required") or 0)
    current = int(state.get("current") or 0)
    remaining = int(state.get("remaining") or max(0, required - current))
    raise HTTPException(
        status_code=403,
        detail=f"Referral sharti bajarilmagan: {current}/{required}. Yana kerak: {remaining}",
    )
