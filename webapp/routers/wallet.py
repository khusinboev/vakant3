from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from webapp.core import errors
from webapp.core.admin_settings import get_admin_settings
from webapp.core.auth import current_user, require_admin
from webapp.core.database import get_db

router = APIRouter(prefix="/wallet", tags=["wallet"])


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


async def _balance_and_pro(db, user_id: int) -> tuple[int, bool]:
    cursor = await db.execute(
        "SELECT user_balance, user_pro FROM users WHERE user_id = ?",
        (int(user_id),),
    )
    row = await cursor.fetchone()
    if not row:
        raise errors.not_found("user")
    return int(row["user_balance"] or 0), bool(int(row["user_pro"] or 0))


@router.get("", response_model=WalletResponse)
async def get_wallet(user=Depends(current_user), db=Depends(get_db)) -> WalletResponse:
    user_id = int(user["user_id"])

    cursor = await db.execute(
        "SELECT user_balance, user_pro FROM users WHERE user_id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    balance = int(row["user_balance"] or 0) if row else 0
    is_pro = bool(int(row["user_pro"] or 0)) if row else False

    settings_row = await get_admin_settings(db)
    return WalletResponse(
        balance=balance,
        is_pro=is_pro,
        pro_price=int(settings_row["pro_price"]),
        referral_reward=int(settings_row["referral_reward"]),
    )


@router.post("/activate-pro", response_model=ActivateProResponse)
async def activate_pro(user=Depends(current_user), db=Depends(get_db)) -> ActivateProResponse:
    user_id = int(user["user_id"])
    balance, is_pro = await _balance_and_pro(db, user_id)

    if is_pro:
        raise errors.api_error(400, errors.ALREADY_PRO)

    pro_price = int((await get_admin_settings(db))["pro_price"])

    # Conditional update: only one concurrent request can win.
    cursor = await db.execute(
        """
        UPDATE users
        SET user_balance = user_balance - ?, user_pro = 1
        WHERE user_id = ? AND COALESCE(user_pro, 0) = 0 AND COALESCE(user_balance, 0) >= ?
        """,
        (pro_price, user_id, pro_price),
    )
    if not cursor.rowcount:
        await db.commit()
        balance, is_pro = await _balance_and_pro(db, user_id)
        if is_pro:
            raise errors.api_error(400, errors.ALREADY_PRO)
        raise errors.api_error(400, errors.INSUFFICIENT_BALANCE, required=pro_price, balance=balance)

    await db.commit()
    new_balance, _ = await _balance_and_pro(db, user_id)
    return ActivateProResponse(ok=True, balance=new_balance, is_pro=True)


@router.post("/admin/add-balance", response_model=AddBalanceResponse)
async def admin_add_balance(
    payload: AddBalanceRequest,
    admin=Depends(require_admin),
    db=Depends(get_db),
) -> AddBalanceResponse:
    """Admin only: add balance to a user."""
    cursor = await db.execute(
        "UPDATE users SET user_balance = COALESCE(user_balance, 0) + ? WHERE user_id = ?",
        (int(payload.amount), int(payload.user_id)),
    )
    if not cursor.rowcount:
        raise errors.not_found("user")
    await db.commit()

    new_balance, _ = await _balance_and_pro(db, int(payload.user_id))
    return AddBalanceResponse(ok=True, new_balance=new_balance)


@router.post("/admin/reset-user")
async def admin_reset_user(
    payload: ResetUserRequest,
    admin=Depends(require_admin),
    db=Depends(get_db),
) -> dict[str, object]:
    """Admin only: set user balance to 0 and remove Pro status."""
    cursor = await db.execute(
        "UPDATE users SET user_balance = 0, user_pro = 0 WHERE user_id = ?",
        (int(payload.user_id),),
    )
    if not cursor.rowcount:
        raise errors.not_found("user")
    await db.commit()
    return {"ok": True, "user_id": int(payload.user_id)}
