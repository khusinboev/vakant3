# ============================================================
# src/filters/admin.py
# Admin access filter: the role comes from the ``admins`` table on every event.
# ============================================================
from __future__ import annotations

import logging
import time

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from src.db.connection import connect
from src.functions.admin_roles import (
    admin_candidate_ids,
    env_admin_ids,
    has_role,
    resolve_admin_role,
)

logger = logging.getLogger(__name__)

#: How long the candidate set is trusted. The admin router sees every private
#: message before ``content.router`` does, so without this pre-check every
#: ordinary menu tap would open a connection just to learn "not an admin".
#: Members of the set still get the full per-update role lookup, so a
#: revocation is immediate; a newly added admin waits at most this long.
CANDIDATE_TTL_SECONDS = 30.0


class _CandidateCache:
    """Per-process ``admins`` row ids (env ids are read live, they cost nothing)."""

    def __init__(self) -> None:
        self.ids: frozenset[int] | None = None
        self.loaded_at = 0.0
        # The connection factory the ids came from: another factory is another
        # database (tests swap it), so the cached ids do not apply to it.
        self.source = None

    def fresh(self, now: float) -> bool:
        return (
            self.ids is not None
            and self.source is connect
            and now - self.loaded_at < CANDIDATE_TTL_SECONDS
        )

    def reset(self) -> None:
        self.ids, self.loaded_at, self.source = None, 0.0, None


_candidates = _CandidateCache()


def reset_admin_candidates() -> None:
    """Forget the candidate set (the next event reloads it)."""
    _candidates.reset()


async def is_admin_candidate(user_id: int) -> bool:
    """False only when the user certainly has no admin role. Never raises.

    On a failed refresh the answer is True: the full lookup then decides, and
    it fails closed on its own.
    """
    user_id = int(user_id)
    try:
        if user_id in env_admin_ids():
            return True
    except Exception as exc:  # config not importable: let the full lookup decide
        logger.warning("ADMIN_IDS unavailable: %s", exc)
        return True
    now = time.monotonic()
    if not _candidates.fresh(now):
        source = connect
        try:
            async with source() as conn:
                ids = await admin_candidate_ids(conn, admin_ids=())
        except Exception as exc:
            logger.warning("admin candidate refresh failed: %s", exc)
            return True
        _candidates.ids, _candidates.loaded_at, _candidates.source = frozenset(ids), now, source
    return user_id in _candidates.ids


async def current_admin_role(user_id: int) -> str | None:
    """The user's admin role read now (no cache), or None. Never raises.

    Users outside the candidate set are refused without a query.
    """
    if not await is_admin_candidate(user_id):
        return None
    try:
        async with connect() as conn:
            return await resolve_admin_role(conn, user_id)
    except Exception as exc:  # unreadable DB: fail closed
        logger.warning("admin role check failed user_id=%s: %s", user_id, exc)
        return None


class IsAdmin(BaseFilter):
    """Passes admins whose role is at least ``min_role`` and injects ``admin_role``.

    The role is read from the database for every update of an admin candidate
    (see ``CANDIDATE_TTL_SECONDS``). When an earlier filter of the same update
    already resolved it (the router-level filter), that value is reused instead
    of querying twice.
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
