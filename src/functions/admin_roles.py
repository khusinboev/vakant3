"""Admin identity and roles for the bot process.

The bot must not import the ``webapp`` package, so this is a plain-SQL copy of
the rule in ``webapp/core/entry_gate.py:admin_role`` (the read-only twin of
``webapp/core/auth.py:resolve_admin_role``). ``tests/test_b1_admin_roles.py``
runs all three on the same databases, so they cannot drift apart silently.

The rule:

* the ``admins`` table is the source of truth: an enabled row gives its role
  (an unknown role string degrades to ``viewer``), a disabled row gives nothing,
  even when the id is still listed in ``ADMIN_IDS``;
* ``ADMIN_IDS`` (env) is bootstrap only: an env id without a row counts as
  ``owner`` while the table is missing or holds no enabled owner;
* any other lookup failure fails closed (no role).

Nothing here caches: the bot re-reads the role on every admin message and every
admin callback, so a revocation in the panel takes effect on the next tap.
``src/filters/admin.py`` only keeps a short-lived *candidate* set
(:func:`admin_candidate_ids`) so that ordinary users never reach this lookup.
"""

from __future__ import annotations

import logging
from typing import Iterable

logger = logging.getLogger(__name__)

#: From most to least privileged, as in ``webapp/core/auth.py``.
ROLES: tuple[str, ...] = ("owner", "admin", "moderator", "viewer")
ROLE_RANK: dict[str, int] = {"viewer": 0, "moderator": 1, "admin": 2, "owner": 3}


def role_rank(role: str | None) -> int:
    return ROLE_RANK.get(str(role or ""), -1)


def has_role(role: str | None, min_role: str) -> bool:
    """True when ``role`` is at least ``min_role`` (``None`` never is)."""
    if min_role not in ROLE_RANK:
        raise ValueError(f"unknown role: {min_role}")
    return role is not None and role_rank(role) >= ROLE_RANK[min_role]


def env_admin_ids(admin_ids: Iterable[int] | None = None) -> set[int]:
    if admin_ids is not None:
        return {int(x) for x in admin_ids}
    import config  # local: importing config needs a TOKEN; tests patch ADMIN_IDS

    return {int(x) for x in config.ADMIN_IDS}


def _is_missing_table(exc: Exception) -> bool:
    return "no such table" in str(exc).lower()


async def resolve_admin_role(
    conn, user_id: int, admin_ids: Iterable[int] | None = None
) -> str | None:
    """The user's admin role, or ``None``. Read-only, never raises."""
    user_id = int(user_id)
    env_ids = env_admin_ids(admin_ids)
    try:
        cursor = await conn.execute(
            "SELECT role, disabled FROM admins WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
    except Exception as exc:
        if _is_missing_table(exc):
            return "owner" if user_id in env_ids else None
        logger.warning("admin role lookup failed user_id=%s: %s", user_id, exc)
        return None

    if row is not None:
        if int(row[1] or 0):
            return None  # an explicit revocation beats the env list
        role = str(row[0] or "")
        return role if role in ROLES else "viewer"

    if user_id not in env_ids:
        return None
    try:
        cursor = await conn.execute(
            "SELECT 1 FROM admins WHERE role = 'owner' AND disabled = 0 LIMIT 1"
        )
        owner_exists = await cursor.fetchone() is not None
    except Exception as exc:
        logger.warning("admin owner lookup failed: %s", exc)
        return None
    return None if owner_exists else "owner"


async def enabled_admin_row_ids(conn) -> set[int]:
    """User ids of the enabled ``admins`` rows; empty while the table is missing.

    Any other failure is raised: the caller decides how to degrade.
    """
    try:
        cursor = await conn.execute(
            "SELECT user_id FROM admins WHERE COALESCE(disabled, 0) = 0"
        )
        return {int(row[0]) for row in await cursor.fetchall()}
    except Exception as exc:
        if _is_missing_table(exc):
            return set()
        raise


async def admin_candidate_ids(conn, admin_ids: Iterable[int] | None = None) -> set[int]:
    """Every user :func:`resolve_admin_role` could give a role to, and more.

    A superset by construction: an enabled row or an ``ADMIN_IDS`` entry is
    required for any role, so a user outside this set has none. Members still
    need the full lookup (an env id loses the bootstrap once an owner row
    exists). Raises when the table cannot be read.
    """
    return env_admin_ids(admin_ids) | await enabled_admin_row_ids(conn)


async def broadcast_admin_ids(conn, admin_ids: Iterable[int] | None = None) -> list[int]:
    """Recipients of the ``test_admins`` segment: enabled admins plus env ids.

    Same set as ``webapp/routers/admin_broadcasts.py:_admin_ids``.
    """
    ids = env_admin_ids(admin_ids)
    try:
        ids |= await enabled_admin_row_ids(conn)
    except Exception as exc:
        logger.warning("admin ids lookup failed: %s", exc)
    return sorted(ids)
