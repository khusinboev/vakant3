import time
from datetime import datetime

from fastapi import APIRouter, Depends

from webapp.core.database import get_db
from webapp.core.session import get_current_user
from webapp.models.schemas import (
    CurrentFilters,
    ProfileFiltersPatchRequest,
    ProfileResponse,
    ProfileStats,
    UpdateResultResponse,
    UserProfile,
)

router = APIRouter(prefix="/profile", tags=["profile"])


def _fmt_date(ts: int) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%d.%m.%Y")
    except Exception:
        return "N/A"


@router.get("", response_model=ProfileResponse)
async def get_profile(current=Depends(get_current_user), db=Depends(get_db)) -> ProfileResponse:
    user = current["user"]
    user_id = int(user["user_id"])

    cursor = await db.execute("SELECT COUNT(*) FROM saves WHERE user_id = ?", (user_id,))
    saves_count = int((await cursor.fetchone())[0] or 0)

    cursor = await db.execute("SELECT COUNT(*) FROM users WHERE ref_by = ?", (user_id,))
    referrals_count = int((await cursor.fetchone())[0] or 0)

    created_ts = int(user.get("date") or int(time.time()))
    days_active = max(1, (int(time.time()) - created_ts) // 86400 + 1)

    return ProfileResponse(
        user=UserProfile(
            user_id=user_id,
            first_name=str(user.get("first_name") or ""),
            username=user.get("username"),
            photo_url=user.get("photo_url"),
            lang=str(user.get("lang") or "uz"),
        ),
        stats=ProfileStats(
            saves_count=saves_count,
            referrals_count=referrals_count,
            member_since=_fmt_date(created_ts),
            days_active=days_active,
        ),
        current_filters=CurrentFilters(
            region=user.get("region"),
            district=user.get("district"),
            specs=user.get("specs"),
            money=user.get("money"),
        ),
    )


@router.patch("/filters", response_model=UpdateResultResponse)
async def patch_filters(
    payload: ProfileFiltersPatchRequest,
    current=Depends(get_current_user),
    db=Depends(get_db),
) -> UpdateResultResponse:
    user_id = int(current["user"]["user_id"])
    data = payload.model_dump(exclude_unset=True)

    if not data:
        return UpdateResultResponse(updated=True)

    fields = []
    values = []
    for key, value in data.items():
        fields.append(f"{key} = ?")
        values.append(value)

    values.append(user_id)
    await db.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?", tuple(values))
    await db.commit()

    return UpdateResultResponse(updated=True)
