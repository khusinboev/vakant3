from fastapi import APIRouter, Depends

from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.session import get_current_user
from webapp.models.schemas import ReferralResponse, ReferralUser

router = APIRouter(prefix="/referral", tags=["referral"])


@router.get("", response_model=ReferralResponse)
async def referral(current=Depends(get_current_user), db=Depends(get_db)) -> ReferralResponse:
    settings = get_settings()
    user_id = int(current["user"]["user_id"])

    cursor = await db.execute(
        "SELECT first_name, date, username FROM users WHERE ref_by = ? ORDER BY date DESC",
        (user_id,),
    )
    rows = await cursor.fetchall()

    referrals = [
        ReferralUser(
            first_name=str(row["first_name"] or "Foydalanuvchi"),
            date=int(row["date"] or 0),
            username=row["username"],
        )
        for row in rows
    ]

    bot_username = settings.BOT_USERNAME or ""
    return ReferralResponse(
        ref_link=f"https://t.me/{bot_username}?start=ref_{user_id}",
        ref_count=len(referrals),
        referrals=referrals,
    )
