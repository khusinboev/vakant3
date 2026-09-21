"""Wallet endpoints. Every balance change goes through ``webapp.core.ledger``.

Admin mutations require a role (``admin``), a short-lived confirmation token and
leave an ``admin_audit_log`` row.
"""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from webapp.core import errors, ledger
from webapp.core.admin_settings import get_admin_settings
from webapp.core.audit import log_admin_action
from webapp.core.auth import current_user, require_role
from webapp.core.confirm import require_confirmation
from webapp.core.database import get_db
from webapp.core.entry_gate import require_entry
from webapp.core.limiter import limiter
from webapp.core.request_ip import client_ip as _client_ip

router = APIRouter(prefix="/wallet", tags=["wallet"], dependencies=[Depends(require_entry)])


class WalletResponse(BaseModel):
    balance: int
    is_pro: bool
    pro_price: int
    referral_reward: int


class ActivateProResponse(BaseModel):
    ok: bool
    balance: int
    is_pro: bool
    tx_id: int


class AddBalanceRequest(BaseModel):
    user_id: int
    amount: int = Field(gt=0, le=ledger.MAX_AMOUNT)
    note: str | None = Field(default=None, max_length=500)


class AddBalanceResponse(BaseModel):
    ok: bool
    new_balance: int
    tx_id: int


class ResetUserRequest(BaseModel):
    user_id: int
    note: str | None = Field(default=None, max_length=500)


class TransactionItem(BaseModel):
    id: int
    kind: str
    amount: int
    balance_after: int
    price_snapshot: int | None = None
    note: str | None = None
    created_at: int


class TransactionsResponse(BaseModel):
    items: list[TransactionItem]
    next_cursor: int | None = None




def _raise_ledger_error(exc: ledger.LedgerError) -> None:
    if isinstance(exc, ledger.AlreadyPro):
        raise errors.api_error(400, errors.ALREADY_PRO) from exc
    if isinstance(exc, ledger.InsufficientBalance):
        raise errors.api_error(
            400, errors.INSUFFICIENT_BALANCE, required=exc.required, balance=exc.balance
        ) from exc
    if isinstance(exc, ledger.UserNotFound):
        raise errors.not_found("user") from exc
    raise errors.api_error(500, errors.UPSTREAM_ERROR) from exc


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


@router.get("/transactions", response_model=TransactionsResponse)
@limiter.limit("60/minute")
async def list_transactions(
    request: Request,
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    user=Depends(current_user),
    db=Depends(get_db),
) -> TransactionsResponse:
    """The caller's own ledger history, newest first."""
    rows = await ledger.list_transactions(
        db, user_id=int(user["user_id"]), before_id=before_id, limit=limit
    )
    items = [
        TransactionItem(
            id=int(row["id"]),
            kind=str(row["kind"]),
            amount=int(row["amount"]),
            balance_after=int(row["balance_after"]),
            price_snapshot=row["price_snapshot"],
            note=row["note"],
            created_at=int(row["created_at"]),
        )
        for row in rows
    ]
    next_cursor = items[-1].id if len(items) == limit else None
    return TransactionsResponse(items=items, next_cursor=next_cursor)


@router.post("/activate-pro", response_model=ActivateProResponse)
@limiter.limit("10/minute")
async def activate_pro(
    request: Request,
    user=Depends(current_user),
    db=Depends(get_db),
) -> ActivateProResponse:
    user_id = int(user["user_id"])
    pro_price = int((await get_admin_settings(db))["pro_price"])

    try:
        result = await ledger.activate_pro(db, user_id, pro_price)
    except ledger.LedgerError as exc:
        await db.rollback()
        _raise_ledger_error(exc)

    await db.commit()
    return ActivateProResponse(
        ok=True, balance=int(result["balance_after"]), is_pro=True, tx_id=int(result["tx_id"])
    )


@router.post("/admin/add-balance", response_model=AddBalanceResponse)
@limiter.limit("10/minute")
async def admin_add_balance(
    request: Request,
    payload: AddBalanceRequest,
    admin=Depends(require_role("admin")),
    _confirmed=Depends(require_confirmation("wallet.add_balance", ["user_id", "amount"])),
    db=Depends(get_db),
) -> AddBalanceResponse:
    """Admin only: credit a user's balance (audited, confirmation token required)."""
    actor_id = int(admin["user_id"])
    try:
        result = await ledger.apply_balance_change(
            db,
            user_id=int(payload.user_id),
            amount=int(payload.amount),
            kind="admin_credit",
            actor_id=actor_id,
            note=payload.note,
        )
    except ledger.LedgerError as exc:
        await db.rollback()
        _raise_ledger_error(exc)

    await log_admin_action(
        db,
        actor_id=actor_id,
        action="wallet.add_balance",
        target_type="user",
        target_id=str(payload.user_id),
        payload={
            "amount": int(payload.amount),
            "balance_after": int(result["balance_after"]),
            "tx_id": int(result["tx_id"]),
            "note": payload.note,
        },
        ip=_client_ip(request),
    )
    await db.commit()
    return AddBalanceResponse(
        ok=True, new_balance=int(result["balance_after"]), tx_id=int(result["tx_id"])
    )


@router.post("/admin/reset-user")
@limiter.limit("10/minute")
async def admin_reset_user(
    request: Request,
    payload: ResetUserRequest,
    admin=Depends(require_role("admin")),
    _confirmed=Depends(require_confirmation("wallet.reset_user", ["user_id"])),
    db=Depends(get_db),
) -> dict[str, object]:
    """Admin only: zero the balance and drop Pro (audited, confirmation required)."""
    actor_id = int(admin["user_id"])
    try:
        result = await ledger.reset_user(
            db, user_id=int(payload.user_id), actor_id=actor_id, note=payload.note
        )
    except ledger.LedgerError as exc:
        await db.rollback()
        _raise_ledger_error(exc)

    await log_admin_action(
        db,
        actor_id=actor_id,
        action="wallet.reset_user",
        target_type="user",
        target_id=str(payload.user_id),
        payload={"amount": int(result["amount"]), "tx_id": int(result["tx_id"])},
        ip=_client_ip(request),
    )
    await db.commit()
    return {
        "ok": True,
        "user_id": int(payload.user_id),
        "new_balance": 0,
        "tx_id": int(result["tx_id"]),
    }
