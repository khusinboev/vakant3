"""Banning revokes sessions; ``POST /admin/users/{id}/sessions/revoke`` does it alone.

The ``webapp_sessions`` row is the identity behind a Bearer token, so the
proof that revocation works is behavioural: the user's token, which worked a
moment ago, now answers 401 ``SESSION_EXPIRED`` on a gated route — not the
403 ``USER_BANNED`` a still-valid session of a banned user would get.
"""

from __future__ import annotations

import json
import time

import pytest

from tests import b3_support
from tests.b3_support import ADMIN, MODERATOR, OWNER, USER, USER2, confirm_header
from webapp.routers import admin_users

harness = b3_support.harness

GATED = "/api/notifications/settings"  # router-level require_entry
ME = "/api/auth/me"  # plain current_user


async def _ban(h, actor: int, target: int, banned: bool = True):
    return await h.http.post(
        f"/api/admin/users/{target}/ban",
        json={"banned": banned, "reason": "spam"},
        headers=await h.session(actor),
    )


async def _revoke(h, actor: int, target: int, *, token_for: int | None = None, body_id=None):
    headers = await h.session(actor)
    headers |= confirm_header(
        actor, "users.sessions_revoke", {"user_id": target if token_for is None else token_for}
    )
    return await h.http.post(
        f"/api/admin/users/{target}/sessions/revoke",
        json={"user_id": target if body_id is None else body_id},
        headers=headers,
    )


async def test_ban_deletes_sessions_and_the_token_stops_working(harness):
    phone = await harness.session(USER)
    laptop = await harness.session(USER)
    other = await harness.session(USER2)
    assert (await harness.http.get(GATED, headers=phone)).status_code == 200

    response = await _ban(harness, MODERATOR, USER)

    assert response.status_code == 200, response.text
    assert response.json()["sessions_revoked"] == 2
    assert await harness.sessions_of(USER) == 0
    for headers in (phone, laptop):
        for path in (GATED, ME):
            answer = await harness.http.get(path, headers=headers)
            assert answer.status_code == 401, (path, answer.text)
            assert answer.json()["detail"]["code"] == "SESSION_EXPIRED"
    # Nobody else is signed out.
    assert (await harness.http.get(GATED, headers=other)).status_code == 200

    rows = await harness.audit("users.ban")
    payload = json.loads(rows[-1]["payload_json"])
    assert payload["banned"] is True
    assert payload["sessions_revoked"] == 2


async def test_ban_also_drops_unused_handoff_tokens(harness):
    future = int(time.time()) + 600
    await harness.execute(
        "INSERT INTO bot_handoff_tokens (token, user_id, used, expires_at) VALUES (?, ?, 0, ?)",
        ("fresh", USER, future),
    )
    await harness.execute(
        "INSERT INTO bot_handoff_tokens (token, user_id, used, expires_at) VALUES (?, ?, 1, ?)",
        ("spent", USER, future),
    )
    assert (await _ban(harness, MODERATOR, USER)).status_code == 200
    rows = await harness.query("SELECT token FROM bot_handoff_tokens WHERE user_id = ?", (USER,))
    assert rows == [{"token": "spent"}]


async def test_unban_keeps_sessions(harness):
    await harness.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (USER,))
    await harness.session(USER)
    response = await _ban(harness, MODERATOR, USER, banned=False)
    assert response.status_code == 200
    assert response.json()["sessions_revoked"] == 0
    assert await harness.sessions_of(USER) == 1


async def test_ban_and_revocation_are_one_transaction(harness, monkeypatch):
    """A failure after the DELETE (here: the audit insert) rolls the DELETE back too."""
    await harness.session(USER)

    async def broken_audit(*args, **kwargs):
        raise RuntimeError("audit store down")

    monkeypatch.setattr(admin_users, "log_admin_action", broken_audit)
    with pytest.raises(RuntimeError):
        await _ban(harness, MODERATOR, USER)

    assert await harness.sessions_of(USER) == 1
    rows = await harness.query("SELECT banned FROM users WHERE user_id = ?", (USER,))
    assert rows[0]["banned"] in (0, None)


# ---------------------------------------------------------------------------
# POST /sessions/revoke
# ---------------------------------------------------------------------------
async def test_revoke_signs_the_user_out_without_banning(harness):
    user_headers = await harness.session(USER)
    await harness.session(USER)
    other = await harness.session(USER2)

    response = await _revoke(harness, ADMIN, USER)

    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True, "user_id": USER, "revoked": 2}
    assert await harness.sessions_of(USER) == 0
    answer = await harness.http.get(GATED, headers=user_headers)
    assert answer.status_code == 401
    assert answer.json()["detail"]["code"] == "SESSION_EXPIRED"
    assert (await harness.http.get(GATED, headers=other)).status_code == 200

    rows = await harness.query("SELECT banned FROM users WHERE user_id = ?", (USER,))
    assert rows[0]["banned"] in (0, None)
    audit = await harness.audit("users.sessions_revoke")
    assert [(r["actor_id"], r["target_id"]) for r in audit] == [(ADMIN, str(USER))]
    assert json.loads(audit[0]["payload_json"])["sessions_revoked"] == 2

    # A new launch works again: revocation is not a ban.
    fresh = await harness.session(USER)
    assert (await harness.http.get(GATED, headers=fresh)).status_code == 200


async def test_revoke_requires_a_confirm_token_bound_to_the_user(harness):
    await harness.session(USER)
    headers = await harness.session(ADMIN)
    missing = await harness.http.post(
        f"/api/admin/users/{USER}/sessions/revoke", json={"user_id": USER}, headers=headers
    )
    assert missing.status_code == 403
    assert missing.json()["detail"]["code"] == "CONFIRMATION_REQUIRED"

    # A token minted for USER2 cannot revoke USER.
    wrong = await _revoke(harness, ADMIN, USER, token_for=USER2)
    assert wrong.status_code == 403
    assert wrong.json()["detail"]["code"] == "CONFIRMATION_REQUIRED"
    assert await harness.sessions_of(USER) == 1
    assert await harness.audit("users.sessions_revoke") == []


async def test_revoke_validation_role_and_missing_user(harness):
    mismatch = await _revoke(harness, ADMIN, USER, token_for=USER2, body_id=USER2)
    assert mismatch.status_code == 400
    assert mismatch.json()["detail"] == {"code": "VALIDATION_ERROR", "field": "user_id"}

    moderator = await _revoke(harness, MODERATOR, USER)
    assert moderator.status_code == 403
    assert moderator.json()["detail"]["code"] == "ADMIN_REQUIRED"

    unknown = await _revoke(harness, OWNER, 900_000_009_999)
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == {"code": "NOT_FOUND", "resource": "user"}
