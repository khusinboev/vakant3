"""Rank protection on every admin action that targets a user.

Rule (``webapp/routers/admin_users.py``): an action is refused with 403
``CANNOT_TARGET_ADMIN{role}`` when the target holds an admin role ranked at or
above the actor's. So a moderator cannot touch a moderator/admin/owner, an
admin cannot touch an admin/owner, and nobody can act on an owner — not even
another owner, and not on themselves. A refusal writes nothing.
"""

from __future__ import annotations

import json

import pytest

from tests import b3_support
from tests.b3_support import (
    ADMIN,
    ADMIN2,
    BOOTSTRAP,
    DISABLED_ADMIN,
    MODERATOR,
    MODERATOR2,
    OWNER,
    OWNER2,
    USER,
    VIEWER,
    confirm_header,
)
from webapp.routers import admin_users

harness = b3_support.harness


@pytest.fixture(autouse=True)
def _telegram_stub(monkeypatch):
    """The message action's only network seam; nothing leaves the process."""
    sent: list[int] = []

    async def fake_send(token, chat_id, text):
        sent.append(int(chat_id))
        return {"ok": True, "result": {"message_id": 1}}

    monkeypatch.setattr(admin_users, "send_telegram_message", fake_send)
    return sent


async def _do(h, action: str, actor: int, target: int, headers: dict | None = None):
    """Perform ``action`` as ``actor`` on ``target`` with a valid confirm token."""
    headers = dict(headers or await h.session(actor))
    base = f"/api/admin/users/{target}"
    if action == "ban":
        return await h.http.post(f"{base}/ban", json={"banned": True}, headers=headers)
    if action == "unban":
        return await h.http.post(f"{base}/ban", json={"banned": False}, headers=headers)
    if action == "pro":
        return await h.http.post(f"{base}/pro", json={"enabled": True, "days": 3}, headers=headers)
    if action == "message":
        return await h.http.post(f"{base}/message", json={"text": "hi"}, headers=headers)
    if action == "balance":
        body = {"user_id": target, "amount": 100}
        headers |= confirm_header(actor, "users.balance", {"user_id": target, "amount": 100})
        return await h.http.post(f"{base}/balance", json=body, headers=headers)
    if action == "reset":
        headers |= confirm_header(actor, "users.reset", {"user_id": target})
        return await h.http.post(f"{base}/reset", json={"user_id": target}, headers=headers)
    if action == "sessions_revoke":
        headers |= confirm_header(actor, "users.sessions_revoke", {"user_id": target})
        return await h.http.post(
            f"{base}/sessions/revoke", json={"user_id": target}, headers=headers
        )
    raise AssertionError(action)


NAMES = {
    OWNER: "owner",
    OWNER2: "owner2",
    ADMIN: "admin",
    ADMIN2: "admin2",
    MODERATOR: "moderator",
    MODERATOR2: "moderator2",
    VIEWER: "viewer",
    DISABLED_ADMIN: "disabled_admin",
    USER: "user",
}

#: Actions open to moderators, and the ones that need ``admin``+.
MODERATOR_ACTIONS = ("ban", "unban", "message")
ADMIN_ACTIONS = ("pro", "balance", "reset", "sessions_revoke")
ALL_ACTIONS = MODERATOR_ACTIONS + ADMIN_ACTIONS


async def _snapshot(h, target: int) -> dict:
    """Everything a refused action must leave untouched."""
    user = (await h.query("SELECT * FROM users WHERE user_id = ?", (target,)))[0]
    # The auth path stamps the ACTOR's last_seen_at, which is the target when
    # an admin acts on themselves; it is bookkeeping, not the action.
    user.pop("last_seen_at", None)
    return {
        "user": user,
        "ledger": await h.ledger_rows(target),
        "sessions": await h.sessions_of(target),
        "audit": await h.scalar("SELECT COUNT(*) FROM admin_audit_log"),
    }


def _assert_refused(response, role: str) -> None:
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == {"code": "CANNOT_TARGET_ADMIN", "role": role}


# ---------------------------------------------------------------------------
# refused
# ---------------------------------------------------------------------------
REFUSED = [
    # (actor, target, target role, actions)
    *[(MODERATOR, OWNER, "owner", a) for a in MODERATOR_ACTIONS],
    *[(MODERATOR, ADMIN, "admin", a) for a in MODERATOR_ACTIONS],
    *[(MODERATOR, MODERATOR2, "moderator", a) for a in MODERATOR_ACTIONS],
    *[(ADMIN, ADMIN2, "admin", a) for a in ALL_ACTIONS],
    *[(ADMIN, OWNER, "owner", a) for a in ALL_ACTIONS],
    *[(OWNER, OWNER2, "owner", a) for a in ALL_ACTIONS],
    # Acting on yourself is acting on an equal rank.
    *[(OWNER, OWNER, "owner", a) for a in ALL_ACTIONS],
    *[(ADMIN, ADMIN, "admin", a) for a in ALL_ACTIONS],
]


@pytest.mark.parametrize(
    "actor,target,role,action",
    REFUSED,
    ids=[f"{a}:{NAMES[actor]}->{NAMES[t]}" for actor, t, _r, a in REFUSED],
)
async def test_action_on_equal_or_higher_rank_is_refused(harness, actor, target, role, action):
    # The target has a balance and a live session, so a leak would be visible.
    await harness.execute("UPDATE users SET user_balance = 500 WHERE user_id = ?", (target,))
    await harness.session(target)
    actor_headers = await harness.session(actor)
    before = await _snapshot(harness, target)

    response = await _do(harness, action, actor, target, actor_headers)

    _assert_refused(response, role)
    assert await _snapshot(harness, target) == before


async def test_nobody_can_ban_an_owner(harness):
    for actor in (MODERATOR, ADMIN, OWNER2):
        _assert_refused(await _do(harness, "ban", actor, OWNER), "owner")
    rows = await harness.query("SELECT banned FROM users WHERE user_id = ?", (OWNER,))
    assert rows[0]["banned"] in (0, None)


# ---------------------------------------------------------------------------
# allowed
# ---------------------------------------------------------------------------
ALLOWED = [
    *[(OWNER, ADMIN, a) for a in ALL_ACTIONS],
    *[(OWNER, MODERATOR, a) for a in ALL_ACTIONS],
    *[(ADMIN, MODERATOR, a) for a in ALL_ACTIONS],
    *[(ADMIN, VIEWER, a) for a in ALL_ACTIONS],
    *[(ADMIN, USER, a) for a in ALL_ACTIONS],
    *[(MODERATOR, VIEWER, a) for a in MODERATOR_ACTIONS],
    *[(MODERATOR, USER, a) for a in MODERATOR_ACTIONS],
    # A disabled admin row is not an admin any more (same rule as auth).
    *[(ADMIN, DISABLED_ADMIN, a) for a in ALL_ACTIONS],
]


@pytest.mark.parametrize(
    "actor,target,action",
    ALLOWED,
    ids=[f"{a}:{NAMES[actor]}->{NAMES[t]}" for actor, t, a in ALLOWED],
)
async def test_action_on_lower_rank_is_allowed(harness, actor, target, action):
    response = await _do(harness, action, actor, target)
    assert response.status_code == 200, response.text


async def test_moderator_still_cannot_use_admin_actions(harness):
    """Rank protection does not widen the route's own role requirement."""
    for action in ADMIN_ACTIONS:
        response = await _do(harness, action, MODERATOR, USER)
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "ADMIN_REQUIRED"


# ---------------------------------------------------------------------------
# the ADMIN_IDS bootstrap owner
# ---------------------------------------------------------------------------
async def test_bootstrap_owner_is_protected_only_while_no_enabled_owner_exists(harness):
    # With enabled owners in the table, the env id is a regular user.
    assert (await _do(harness, "ban", ADMIN, BOOTSTRAP)).status_code == 200
    await harness.execute("UPDATE users SET banned = 0 WHERE user_id = ?", (BOOTSTRAP,))

    # Disable every owner: BOOTSTRAP is now the bootstrap owner (auth.resolve_admin_role).
    await harness.execute("UPDATE admins SET disabled = 1 WHERE role = 'owner'")
    _assert_refused(await _do(harness, "ban", ADMIN, BOOTSTRAP), "owner")
    # Resolving the TARGET's role never provisions it (unlike the actor path).
    assert await harness.query("SELECT 1 FROM admins WHERE user_id = ?", (BOOTSTRAP,)) == []


# ---------------------------------------------------------------------------
# detail exposes the target's role
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "viewer,target,role,actionable",
    [
        (OWNER, ADMIN, "admin", True),
        (OWNER, OWNER2, "owner", False),
        (ADMIN, ADMIN2, "admin", False),
        (ADMIN, MODERATOR, "moderator", True),
        (MODERATOR, ADMIN, "admin", False),
        (MODERATOR, USER, None, True),
        (VIEWER, VIEWER, "viewer", False),
        (ADMIN, DISABLED_ADMIN, None, True),
    ],
)
async def test_detail_reports_target_role_and_actionable(harness, viewer, target, role, actionable):
    response = await harness.http.get(
        f"/api/admin/users/{target}", headers=await harness.session(viewer)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["target_role"] == role
    assert body["actionable"] is actionable


async def test_refusal_is_not_audited_but_success_is(harness):
    _assert_refused(await _do(harness, "ban", ADMIN, ADMIN2), "admin")
    assert await harness.audit("users.ban") == []
    assert (await _do(harness, "ban", ADMIN, USER)).status_code == 200
    rows = await harness.audit("users.ban")
    assert [(r["actor_id"], r["target_id"]) for r in rows] == [(ADMIN, str(USER))]
    assert json.loads(rows[0]["payload_json"])["banned"] is True
