"""A banned admin loses the panel, even with a session minted after the ban.

Banning deletes the target's sessions, but ``/auth/launch`` can mint a new
one, and the entry gate lets admins through. So the admin dependencies
(``require_admin`` / ``require_role``) and the CSV download link re-read
``users.banned`` themselves and answer 403 ``USER_BANNED``.

All ids are synthetic (>= 900000000000).
"""

from __future__ import annotations

import pytest

from tests import b3_support
from tests.b3_support import ADMIN, MODERATOR, OWNER, USER, VIEWER

harness = b3_support.harness


def _banned(response) -> None:
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "USER_BANNED"


async def test_owner_bans_an_admin_and_a_fresh_session_is_refused(harness):
    owner = await harness.session(OWNER)
    ban = await harness.http.post(
        f"/api/admin/users/{ADMIN}/ban", json={"banned": True}, headers=owner
    )
    assert ban.status_code == 200, ban.text

    fresh = await harness.session(ADMIN)  # a new login after the ban
    _banned(await harness.http.get("/api/admin/users", headers=fresh))
    _banned(await harness.http.get(f"/api/admin/users/{USER}", headers=fresh))
    _banned(
        await harness.http.post(
            "/api/admin/confirm",
            json={"action": "users.balance", "params": {"user_id": USER, "amount": 1}},
            headers=fresh,
        )
    )
    _banned(
        await harness.http.post(
            f"/api/admin/users/{USER}/ban", json={"banned": True}, headers=fresh
        )
    )
    rows = await harness.query("SELECT banned FROM users WHERE user_id = ?", (USER,))
    assert rows == [{"banned": 0}]

    unban = await harness.http.post(
        f"/api/admin/users/{ADMIN}/ban", json={"banned": False}, headers=owner
    )
    assert unban.status_code == 200, unban.text
    again = await harness.http.get("/api/admin/users", headers=fresh)
    assert again.status_code == 200, again.text


@pytest.mark.parametrize("actor", [OWNER, ADMIN, MODERATOR, VIEWER])
async def test_every_role_is_refused_while_banned(harness, actor):
    await harness.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (actor,))
    headers = await harness.session(actor)
    _banned(await harness.http.get("/api/admin/users", headers=headers))

    await harness.execute("UPDATE users SET banned = 0 WHERE user_id = ?", (actor,))
    ok = await harness.http.get("/api/admin/users", headers=headers)
    assert ok.status_code == 200, ok.text


async def test_banned_check_runs_after_the_admin_check(harness):
    """A banned non-admin still gets ADMIN_REQUIRED: the ban says nothing about rank."""
    await harness.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (USER,))
    response = await harness.http.get("/api/admin/users", headers=await harness.session(USER))
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "ADMIN_REQUIRED"


async def test_a_banned_admins_download_link_is_dead(harness):
    minted = await harness.http.post(
        "/api/admin/users/export/link",
        params={"sort": "date"},
        headers=await harness.session(ADMIN),
    )
    assert minted.status_code == 200, minted.text
    token = minted.json()["token"]
    await harness.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (ADMIN,))
    response = await harness.http.get(
        "/api/admin/users/export/download.csv",
        params={"actor": ADMIN, "dl": token, "sort": "date"},
    )
    _banned(response)
    assert await harness.audit("users.export") == []
