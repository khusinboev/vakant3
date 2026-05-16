from fastapi import APIRouter, Depends
from fastapi import Request

from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.identity import require_user_id_from_request_init_data
from webapp.core.referral_gate import get_referral_gate_state
from webapp.models.schemas import ReferralResponse, ReferralUser

router = APIRouter(prefix="/referral", tags=["referral"])

@router.get("", response_model=ReferralResponse)
async def referral(request: Request, db=Depends(get_db)) -> ReferralResponse:
    settings = get_settings()
    user_id = require_user_id_from_request_init_data(request)

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


@router.get("/stats")
async def referral_stats(request: Request, db=Depends(get_db)) -> dict[str, int | bool | str]:
    settings = get_settings()
    user_id = require_user_id_from_request_init_data(request)

    gate_state = await get_referral_gate_state(db, user_id)
    return {
        "user_id": int(user_id),
        "enabled": bool(gate_state["enabled"]),
        "required": int(gate_state["required"]),
        "current": int(gate_state["current"]),
        "unlocked": bool(gate_state["unlocked"]),
        "ref_link": f"https://t.me/{settings.BOT_USERNAME}?start=ref_{user_id}",
    }
