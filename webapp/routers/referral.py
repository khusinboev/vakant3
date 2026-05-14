from fastapi import APIRouter, Depends
from fastapi import HTTPException, Request

from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.identity import resolve_user_id_from_init_data
from webapp.core.referral_gate import get_referral_gate_state
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


@router.get("/stats")
async def referral_stats(request: Request, db=Depends(get_db)) -> dict[str, int | bool | str]:
    settings = get_settings()
    init_data = (request.headers.get("X-Telegram-Init-Data") or "").strip()
    user_id = resolve_user_id_from_init_data(init_data, settings.TOKEN) if init_data else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    gate_state = await get_referral_gate_state(db, user_id)
    return {
        "user_id": int(user_id),
        "enabled": bool(gate_state["enabled"]),
        "required": int(gate_state["required"]),
        "current": int(gate_state["current"]),
        "unlocked": bool(gate_state["unlocked"]),
        "ref_link": f"https://t.me/{settings.BOT_USERNAME}?start=ref_{user_id}",
    }
