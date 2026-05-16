from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.identity import resolve_user_id_from_init_data

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(request: Request) -> int:
    settings = get_settings()
    init_data = (request.headers.get("X-Telegram-Init-Data") or "").strip()
    if not init_data:
        raise HTTPException(status_code=401, detail="Telegram initData required")

    user_id = resolve_user_id_from_init_data(init_data, settings.TOKEN)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid initData")

    if user_id not in settings.admin_ids_set:
        raise HTTPException(status_code=403, detail="Admin only")

    return user_id


class AdminStateResponse(BaseModel):
    is_admin: bool
    auto_post_enabled: bool
    auto_post_channel: str
    auto_post_min_salary: int
    referral_enabled: bool
    referral_required_count: int
    pro_price: int
    referral_reward: int
    pro_min_salary: int


class AdminSettingsPatch(BaseModel):
    auto_post_enabled: bool | None = None
    auto_post_channel: str | None = None
    auto_post_min_salary: int | None = Field(default=None, ge=0)
    referral_enabled: bool | None = None
    referral_required_count: int | None = Field(default=None, ge=0)
    pro_price: int | None = Field(default=None, ge=0)
    referral_reward: int | None = Field(default=None, ge=0)
    pro_min_salary: int | None = Field(default=None, ge=0)


@router.get("/state", response_model=AdminStateResponse)
async def get_admin_state(request: Request, db=Depends(get_db)) -> AdminStateResponse:
    _require_admin(request)
    cursor = await db.execute(
        "SELECT auto_post_enabled, auto_post_channel, auto_post_min_salary, referral_enabled, referral_required_count, "
        "pro_price, referral_reward, pro_min_salary "
        "FROM webapp_admin_settings WHERE singleton = 1"
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Settings not initialized")

    return AdminStateResponse(
        is_admin=True,
        auto_post_enabled=bool(int(row["auto_post_enabled"] or 0)),
        auto_post_channel=str(row["auto_post_channel"] or ""),
        auto_post_min_salary=int(row["auto_post_min_salary"] or 0),
        referral_enabled=bool(int(row["referral_enabled"] or 0)),
        referral_required_count=int(row["referral_required_count"] or 0),
        pro_price=int(row["pro_price"] or 10000),
        referral_reward=int(row["referral_reward"] or 2000),
        pro_min_salary=int(row["pro_min_salary"] or 8000000),
    )


@router.patch("/state", response_model=AdminStateResponse)
async def patch_admin_state(payload: AdminSettingsPatch, request: Request, db=Depends(get_db)) -> AdminStateResponse:
    _require_admin(request)

    if payload.auto_post_enabled is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET auto_post_enabled = ? WHERE singleton = 1",
            (1 if payload.auto_post_enabled else 0,),
        )
    if payload.auto_post_channel is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET auto_post_channel = ? WHERE singleton = 1",
            (payload.auto_post_channel.strip(),),
        )
    if payload.auto_post_min_salary is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET auto_post_min_salary = ? WHERE singleton = 1",
            (int(payload.auto_post_min_salary),),
        )
    if payload.referral_enabled is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET referral_enabled = ? WHERE singleton = 1",
            (1 if payload.referral_enabled else 0,),
        )
    if payload.referral_required_count is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET referral_required_count = ? WHERE singleton = 1",
            (int(payload.referral_required_count),),
        )
    if payload.pro_price is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET pro_price = ? WHERE singleton = 1",
            (int(payload.pro_price),),
        )
    if payload.referral_reward is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET referral_reward = ? WHERE singleton = 1",
            (int(payload.referral_reward),),
        )
    if payload.pro_min_salary is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET pro_min_salary = ? WHERE singleton = 1",
            (int(payload.pro_min_salary),),
        )

    await db.commit()
    return await get_admin_state(request, db)
