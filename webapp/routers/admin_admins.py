"""Admin roster management and confirmation-token minting.

Mounted from ``admin_panel.router`` (so ``webapp/main.py`` stays untouched);
every path here ends up under ``/api/admin``.

Managing the roster is owner-only: an ``admin`` may spend money and change
settings, but only an owner may hand out or revoke that power. The last
enabled owner is protected — removing, disabling or demoting them would lock
everybody out of the panel with no way back except editing the database by
hand.
"""

import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from webapp.core import errors
from webapp.core.audit import client_ip, log_admin_action
from webapp.core.auth import ROLES, require_admin, require_role, role_rank
from webapp.core.confirm import confirm_ttl, issue_confirm_token
from webapp.core.database import get_db
from webapp.core.limiter import limiter

router = APIRouter(tags=["admin"])

require_owner = require_role("owner")


class AdminRow(BaseModel):
    user_id: int
    role: str
    added_by: int | None = None
    added_at: int
    disabled: bool
    first_name: str = ""
    username: str = ""


class AdminListResponse(BaseModel):
    items: list[AdminRow]


class AdminCreateRequest(BaseModel):
    user_id: int = Field(ge=1)
    role: str = Field(pattern="^(owner|admin|moderator|viewer)$")


class AdminUpdateRequest(BaseModel):
    role: str | None = Field(default=None, pattern="^(owner|admin|moderator|viewer)$")
    disabled: bool | None = None


class ConfirmRequest(BaseModel):
    action: str = Field(min_length=1, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)


class ConfirmResponse(BaseModel):
    token: str
    expires_in: int


def _row_to_model(row) -> AdminRow:
    return AdminRow(
        user_id=int(row["user_id"]),
        role=str(row["role"] or "viewer"),
        added_by=int(row["added_by"]) if row["added_by"] is not None else None,
        added_at=int(row["added_at"] or 0),
        disabled=bool(int(row["disabled"] or 0)),
        first_name=str(row["first_name"] or "") if "first_name" in row.keys() else "",
        username=str(row["username"] or "") if "username" in row.keys() else "",
    )


async def _fetch_admin(db, user_id: int):
    cursor = await db.execute(
        "SELECT a.user_id, a.role, a.added_by, a.added_at, a.disabled, "
        "       COALESCE(u.first_name, '') AS first_name, COALESCE(u.username, '') AS username "
        "FROM admins a LEFT JOIN users u ON u.user_id = a.user_id "
        "WHERE a.user_id = ?",
        (int(user_id),),
    )
    return await cursor.fetchone()


async def _enabled_owner_count(db) -> int:
    cursor = await db.execute(
        "SELECT COUNT(*) AS c FROM admins WHERE role = 'owner' AND disabled = 0"
    )
    row = await cursor.fetchone()
    return int((row["c"] if row else 0) or 0)


async def _guard_last_owner(db, row) -> None:
    """Refuse a change that would leave the panel without an enabled owner."""
    if str(row["role"] or "") != "owner" or int(row["disabled"] or 0):
        return
    if await _enabled_owner_count(db) <= 1:
        raise errors.api_error(409, errors.CANNOT_REMOVE_LAST_OWNER)


@router.post("/confirm", response_model=ConfirmResponse)
@limiter.limit("20/minute")
async def create_confirm_token(
    request: Request,
    payload: ConfirmRequest,
    actor=Depends(require_admin),
) -> ConfirmResponse:
    """Mint a short-lived token bound to this actor, action and parameters.

    Minting is not itself authorisation: the destructive endpoint still checks
    the actor's role. A token for an action the actor may not perform is
    useless.
    """
    token = issue_confirm_token(int(actor["user_id"]), payload.action, payload.params)
    return ConfirmResponse(token=token, expires_in=confirm_ttl())


@router.get("/admins", response_model=AdminListResponse)
@limiter.limit("60/minute")
async def list_admins(
    request: Request,
    actor=Depends(require_owner),
    db=Depends(get_db),
) -> AdminListResponse:
    cursor = await db.execute(
        "SELECT a.user_id, a.role, a.added_by, a.added_at, a.disabled, "
        "       COALESCE(u.first_name, '') AS first_name, COALESCE(u.username, '') AS username "
        "FROM admins a LEFT JOIN users u ON u.user_id = a.user_id "
        "ORDER BY a.disabled ASC, a.added_at ASC"
    )
    rows = await cursor.fetchall()
    return AdminListResponse(items=[_row_to_model(row) for row in rows])


@router.post("/admins", response_model=AdminRow, status_code=201)
@limiter.limit("10/minute")
async def add_admin(
    request: Request,
    payload: AdminCreateRequest,
    actor=Depends(require_owner),
    db=Depends(get_db),
) -> AdminRow:
    user_id = int(payload.user_id)
    role = payload.role
    if role not in ROLES:
        raise errors.validation_error("role")

    existing = await _fetch_admin(db, user_id)
    if existing is not None and not int(existing["disabled"] or 0):
        raise errors.api_error(409, errors.ADMIN_EXISTS, user_id=user_id)

    now = int(time.time())
    if existing is None:
        await db.execute(
            "INSERT INTO admins (user_id, role, added_by, added_at, disabled) VALUES (?, ?, ?, ?, 0)",
            (user_id, role, int(actor["user_id"]), now),
        )
    else:
        # Reviving a previously disabled admin counts as adding them again.
        await db.execute(
            "UPDATE admins SET role = ?, added_by = ?, added_at = ?, disabled = 0 WHERE user_id = ?",
            (role, int(actor["user_id"]), now, user_id),
        )

    await log_admin_action(
        db,
        actor_id=int(actor["user_id"]),
        action="admins.add",
        target_type="admin",
        target_id=str(user_id),
        payload={"role": role, "revived": existing is not None},
        ip=client_ip(request),
    )
    await db.commit()

    row = await _fetch_admin(db, user_id)
    return _row_to_model(row)


@router.patch("/admins/{user_id}", response_model=AdminRow)
@limiter.limit("10/minute")
async def update_admin(
    request: Request,
    user_id: int,
    payload: AdminUpdateRequest,
    actor=Depends(require_owner),
    db=Depends(get_db),
) -> AdminRow:
    if payload.role is None and payload.disabled is None:
        raise errors.validation_error("role")

    row = await _fetch_admin(db, int(user_id))
    if row is None:
        raise errors.not_found("admin")

    demoting = payload.role is not None and role_rank(payload.role) < role_rank(str(row["role"]))
    disabling = payload.disabled is True
    if demoting or disabling:
        await _guard_last_owner(db, row)

    changes: dict[str, Any] = {}
    if payload.role is not None and payload.role != str(row["role"] or ""):
        await db.execute("UPDATE admins SET role = ? WHERE user_id = ?", (payload.role, int(user_id)))
        changes["role"] = [str(row["role"] or ""), payload.role]
    if payload.disabled is not None and bool(payload.disabled) != bool(int(row["disabled"] or 0)):
        await db.execute(
            "UPDATE admins SET disabled = ? WHERE user_id = ?",
            (1 if payload.disabled else 0, int(user_id)),
        )
        changes["disabled"] = [bool(int(row["disabled"] or 0)), bool(payload.disabled)]

    if changes:
        await log_admin_action(
            db,
            actor_id=int(actor["user_id"]),
            action="admins.role",
            target_type="admin",
            target_id=str(user_id),
            payload={"changes": changes},
            ip=client_ip(request),
        )
        await db.commit()

    updated = await _fetch_admin(db, int(user_id))
    return _row_to_model(updated)


@router.delete("/admins/{user_id}")
@limiter.limit("10/minute")
async def remove_admin(
    request: Request,
    user_id: int,
    actor=Depends(require_owner),
    db=Depends(get_db),
) -> dict[str, bool]:
    row = await _fetch_admin(db, int(user_id))
    if row is None:
        raise errors.not_found("admin")
    await _guard_last_owner(db, row)

    await db.execute("DELETE FROM admins WHERE user_id = ?", (int(user_id),))
    await log_admin_action(
        db,
        actor_id=int(actor["user_id"]),
        action="admins.remove",
        target_type="admin",
        target_id=str(user_id),
        payload={"role": str(row["role"] or "")},
        ip=client_ip(request),
    )
    await db.commit()
    return {"ok": True}
