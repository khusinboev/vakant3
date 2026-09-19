"""Single read of the ``webapp_admin_settings`` singleton row."""

from typing import Any

DEFAULTS: dict[str, Any] = {
    "auto_post_enabled": 0,
    "auto_post_channel": "",
    "auto_post_min_salary": 8_000_000,
    "referral_enabled": 0,
    "referral_required_count": 0,
    "next_auto_post_ts": 0,
    "pro_price": 10_000,
    "referral_reward": 2_000,
    "pro_min_salary": 8_000_000,
    "resume_target_creation_minutes": 8.0,
    "resume_target_completion_rate": 60.0,
    "resume_target_send_success_rate": 98.0,
    "resume_target_export_success_rate": 99.0,
    "auto_post_per_day_min": 4,
    "auto_post_per_day_max": 8,
    "auto_post_scheduled_times_json": "[]",
}


async def get_admin_settings(db) -> dict[str, Any]:
    """Return the settings row merged over DEFAULTS (never raises, never returns None)."""
    values = dict(DEFAULTS)
    try:
        cursor = await db.execute("SELECT * FROM webapp_admin_settings WHERE singleton = 1")
        row = await cursor.fetchone()
    except Exception:
        return values
    if not row:
        return values
    for key, default in DEFAULTS.items():
        try:
            raw = row[key]
        except (IndexError, KeyError):
            continue
        if raw is None:
            continue
        if isinstance(default, bool):
            values[key] = bool(int(raw))
        elif isinstance(default, int):
            values[key] = int(raw)
        elif isinstance(default, float):
            values[key] = float(raw)
        else:
            values[key] = str(raw)
    return values
