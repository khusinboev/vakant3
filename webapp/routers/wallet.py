from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from webapp.core.database import get_db
from webapp.core.identity import (
    require_admin_user_id_from_request_init_data,
    require_user_id_from_request_init_data,
)

router = APIRouter(prefix="/wallet", tags=["wallet"])


def _get_user_id(request: Request) -> int:
    return require_user_id_from_request_init_data(request)


class WalletResponse(BaseModel):
    balance: int
    is_pro: bool
    pro_price: int
    referral_reward: int


class ActivateProResponse(BaseModel):
    ok: bool
    balance: int
    is_pro: bool


class AddBalanceRequest(BaseModel):
    user_id: int
    amount: int = Field(gt=0)


class AddBalanceResponse(BaseModel):
    ok: bool
    new_balance: int


class ResetUserRequest(BaseModel):
    user_id: int


@router.get("", response_model=WalletResponse)
async def get_wallet(request: Request, db=Depends(get_db)) -> WalletResponse:
    user_id = _get_user_id(request)

    cursor = await db.execute(
        "SELECT user_balance, user_pro FROM users WHERE user_id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    balance = int(row["user_balance"] or 0) if row else 0
    is_pro = bool(int(row["user_pro"] or 0)) if row else False

    cursor2 = await db.execute(
        "SELECT pro_price, referral_reward FROM webapp_admin_settings WHERE singleton = 1"
    )
    settings_row = await cursor2.fetchone()
    pro_price = int(settings_row["pro_price"] or 10000) if settings_row else 10000
    referral_reward = int(settings_row["referral_reward"] or 2000) if settings_row else 2000

    return WalletResponse(balance=balance, is_pro=is_pro, pro_price=pro_price, referral_reward=referral_reward)


@router.post("/activate-pro", response_model=ActivateProResponse)
async def activate_pro(request: Request, db=Depends(get_db)) -> ActivateProResponse:
    user_id = _get_user_id(request)

    cursor = await db.execute(
        "SELECT user_balance, user_pro FROM users WHERE user_id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    balance = int(row["user_balance"] or 0)
    is_pro = bool(int(row["user_pro"] or 0))

    if is_pro:
        return ActivateProResponse(ok=True, balance=balance, is_pro=True)

    cursor2 = await db.execute(
        "SELECT pro_price FROM webapp_admin_settings WHERE singleton = 1"
    )
    settings_row = await cursor2.fetchone()
    pro_price = int(settings_row["pro_price"] or 10000) if settings_row else 10000

    if balance < pro_price:
        raise HTTPException(
            status_code=400,
            detail=f"Hisobingizda yetarli mablag' yo'q. Kerak: {pro_price} so'm, mavjud: {balance} so'm",
        )

    new_balance = balance - pro_price
    await db.execute(
        "UPDATE users SET user_balance = ?, user_pro = 1 WHERE user_id = ?",
        (new_balance, user_id),
    )
    await db.commit()

    return ActivateProResponse(ok=True, balance=new_balance, is_pro=True)


@router.post("/admin/add-balance", response_model=AddBalanceResponse)
async def admin_add_balance(payload: AddBalanceRequest, request: Request, db=Depends(get_db)) -> AddBalanceResponse:
    """Admin only: add balance to a user."""
    require_admin_user_id_from_request_init_data(request)

    cursor = await db.execute(
        "SELECT user_balance FROM users WHERE user_id = ?",
        (payload.user_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    new_balance = int(row["user_balance"] or 0) + payload.amount
    await db.execute(
        "UPDATE users SET user_balance = ? WHERE user_id = ?",
        (new_balance, payload.user_id),
    )
    await db.commit()

    return AddBalanceResponse(ok=True, new_balance=new_balance)


@router.post("/admin/reset-user")
async def admin_reset_user(payload: ResetUserRequest, request: Request, db=Depends(get_db)):
    """Admin only: set user balance to 0 and remove pro status."""
    require_admin_user_id_from_request_init_data(request)

    cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (payload.user_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="User not found")

    await db.execute(
        "UPDATE users SET user_balance = 0, user_pro = 0 WHERE user_id = ?",
        (payload.user_id,),
    )
    await db.commit()
    return {"ok": True, "user_id": payload.user_id}
