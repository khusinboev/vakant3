"""The user's own referral link and the people who used it.

Behind ``require_entry`` like every other user-facing router: the referral
count is what unlocks the app, so a user who has not started the bot (or is
banned) must not be able to read or grow it through the API alone.

The list is paginated. It used to be an unbounded ``SELECT ... ORDER BY date``
returning every invited user in one response — a top inviter with thousands of
referrals made the API build (and the Mini App parse) a payload nobody scrolls.
``ref_count`` stays the *total*, so the counter the referral gate shows is
unchanged; only the rendered slice is capped.
"""

from fastapi import APIRouter, Depends, Query, Request

from webapp.core.auth import current_user
from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.entry_gate import require_entry
from webapp.core.limiter import limiter
from webapp.core.referral_gate import get_referral_gate_state
from webapp.models.schemas import ReferralResponse, ReferralUser

router = APIRouter(prefix="/referral", tags=["referral"], dependencies=[Depends(require_entry)])

#: Rows returned per page. Also the default: the Mini App shows a short list.
MAX_REFERRALS = 50

#: Beyond this the count is reported as-is rather than scanning further; the
#: partial index from m014 makes the capped count an index-only lookup.
COUNT_CAP = 10_000


@router.get("", response_model=ReferralResponse)
@limiter.limit("60/minute")
async def referral(
    request: Request,
    limit: int = Query(default=MAX_REFERRALS, ge=1, le=MAX_REFERRALS),
    before_date: int | None = Query(default=None, description="Keyset cursor: users.date"),
    user=Depends(current_user),
    db=Depends(get_db),
) -> ReferralResponse:
    settings = get_settings()
    user_id = int(user["user_id"])

    where = "ref_by = ?"
    params: list = [user_id]
    if before_date is not None:
        where += " AND date < ?"
        params.append(int(before_date))

    cursor = await db.execute(
        f"SELECT first_name, date, username FROM users WHERE {where} ORDER BY date DESC LIMIT ?",
        (*params, limit),
    )
    rows = await cursor.fetchall()

    referrals = [
        ReferralUser(
            first_name=(str(row["first_name"]).strip() or None) if row["first_name"] else None,
            date=int(row["date"] or 0),
            username=row["username"],
        )
        for row in rows
    ]

    count_cursor = await db.execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM users WHERE ref_by = ? LIMIT ?)",
        (user_id, COUNT_CAP),
    )
    count_row = await count_cursor.fetchone()
    ref_count = int((count_row[0] if count_row else 0) or 0)

    bot_username = settings.BOT_USERNAME or ""
    return ReferralResponse(
        ref_link=f"https://t.me/{bot_username}?start=ref_{user_id}",
        ref_count=ref_count,
        referrals=referrals,
    )


@router.get("/stats")
@limiter.limit("60/minute")
async def referral_stats(
    request: Request, user=Depends(current_user), db=Depends(get_db)
) -> dict[str, int | bool | str]:
    settings = get_settings()
    user_id = int(user["user_id"])

    gate_state = await get_referral_gate_state(db, user_id)
    return {
        "user_id": user_id,
        "enabled": bool(gate_state["enabled"]),
        "required": int(gate_state["required"]),
        "current": int(gate_state["current"]),
        "unlocked": bool(gate_state["unlocked"]),
        "ref_link": f"https://t.me/{settings.BOT_USERNAME}?start=ref_{user_id}",
    }
