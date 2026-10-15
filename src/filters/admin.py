# ============================================================
# src/filters/admin.py
# Admin access filter: the role comes from the ``admins`` table on every event.
# ============================================================
from __future__ import annotations

import logging

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from src.db.connection import connect
from src.functions.admin_roles import has_role, resolve_admin_role

logger = logging.getLogger(__name__)


async def current_admin_role(user_id: int) -> str | None:
    """The user's admin role read now (no cache), or None. Never raises."""
    try:
        async with connect() as conn:
            return await resolve_admin_role(conn, user_id)
    except Exception as exc:  # unreadable DB: fail closed
        logger.warning("admin role check failed user_id=%s: %s", user_id, exc)
        return None


class IsAdmin(BaseFilter):
    """Passes admins whose role is at least ``min_role`` and injects ``admin_role``.

    The role is read from the database for every update. When an earlier
    filter of the same update already resolved it (the router-level filter),
    that value is reused instead of querying twice.
    """

    def __init__(self, min_role: str = "viewer") -> None:
        has_role("viewer", min_role)  # validates the name
        self.min_role = min_role

    async def __call__(
        self, event: Message | CallbackQuery, admin_role: str | None = None
    ) -> bool | dict[str, str]:
        user = getattr(event, "from_user", None)
        if user is None:
            return False
        role = admin_role if admin_role is not None else await current_admin_role(user.id)
        if not has_role(role, self.min_role):
            return False
        return {"admin_role": role}
