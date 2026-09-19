import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from webapp.core import errors
from webapp.core.auth import current_user
from webapp.core.database import get_db
from webapp.core.users import get_user_pro

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationSettings(BaseModel):
    enabled: bool


@router.get("/settings", response_model=NotificationSettings)
async def get_notification_settings(
    user=Depends(current_user),
    db=Depends(get_db),
) -> NotificationSettings:
    user_id = int(user["user_id"])
    cursor = await db.execute(
        "SELECT enabled FROM notification_settings WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    return NotificationSettings(enabled=bool(row["enabled"]) if row else False)


@router.post("/toggle", response_model=NotificationSettings)
async def toggle_notifications(
    user=Depends(current_user),
    db=Depends(get_db),
) -> NotificationSettings:
    user_id = int(user["user_id"])

    is_pro = await get_user_pro(db, user_id)

    cursor = await db.execute(
        "SELECT enabled FROM notification_settings WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    current_enabled = bool(row["enabled"]) if row else False

    # Turning notifications ON is a Pro-only feature; turning them off is always allowed.
    if not current_enabled and not is_pro:
        raise errors.api_error(403, errors.PRO_REQUIRED)

    new_enabled = not current_enabled
    now = int(time.time())

    await db.execute(
        """
        INSERT INTO notification_settings (user_id, enabled, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET enabled = excluded.enabled, updated_at = excluded.updated_at
        """,
        (user_id, int(new_enabled), now, now),
    )
    await db.commit()
    return NotificationSettings(enabled=new_enabled)
