from webapp.core import errors


async def get_referral_gate_state(db, user_id: int) -> dict[str, int | bool]:
    """Referral gate state for one user. Admins are always unlocked.

    The import is deferred: ``entry_gate`` imports this module, and the admin
    bypass is the only thing it needs from there.
    """
    from webapp.core.entry_gate import admin_role  # noqa: PLC0415 - avoids a cycle

    cursor = await db.execute(
        "SELECT referral_enabled, referral_required_count FROM webapp_admin_settings WHERE singleton = 1"
    )
    settings_row = await cursor.fetchone()

    enabled = bool(int(settings_row["referral_enabled"] or 0)) if settings_row else False
    required = int(settings_row["referral_required_count"] or 0) if settings_row else 0

    cursor = await db.execute("SELECT COUNT(*) FROM users WHERE ref_by = ?", (user_id,))
    current = int((await cursor.fetchone())[0] or 0)

    unlocked = (not enabled) or required <= 0 or current >= required
    if not unlocked and await admin_role(db, int(user_id)) is not None:
        unlocked = True
    return {
        "enabled": enabled,
        "required": required,
        "current": current,
        "unlocked": unlocked,
    }


def raise_if_referral_locked(state: dict[str, int | bool]) -> None:
    if bool(state.get("unlocked")):
        return
    raise errors.api_error(
        403,
        errors.REFERRAL_LOCKED,
        count=int(state.get("current") or 0),
        required=int(state.get("required") or 0),
    )
