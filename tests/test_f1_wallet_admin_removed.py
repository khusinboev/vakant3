"""The rank-less ``/wallet/admin/*`` money endpoints are gone.

``POST /wallet/admin/add-balance`` and ``/wallet/admin/reset-user`` checked
only role ``admin`` plus a confirm token, so an admin could credit the owner,
another admin or themselves. The supported routes are
``POST /admin/users/{id}/balance`` and ``/reset``, which apply the rank rule
(``admin_users._guard_target``). These tests pin both halves: the old paths
answer 404 even with a valid token, and self-credit through the supported
route is refused without writing anything.

All ids are synthetic (>= 900000000000).
"""

from __future__ import annotations

import pytest

from tests import b3_support
from tests.b3_support import ADMIN, OWNER, USER, confirm_header

harness = b3_support.harness


@pytest.mark.parametrize(
    "path,action,body",
    [
        (
            "/api/wallet/admin/add-balance",
            "wallet.add_balance",
            {"user_id": ADMIN, "amount": 1_000_000},
        ),
        ("/api/wallet/admin/reset-user", "wallet.reset_user", {"user_id": OWNER}),
    ],
)
async def test_old_wallet_admin_paths_are_gone(harness, path, action, body):
    await harness.execute("UPDATE users SET user_balance = 500 WHERE user_id = ?", (OWNER,))
    params = {key: body[key] for key in ("user_id", "amount") if key in body}
    headers = await harness.session(ADMIN) | confirm_header(ADMIN, action, params)

    response = await harness.http.post(path, json=body, headers=headers)

    assert response.status_code == 404, response.text
    assert response.json()["detail"]["code"] == "NOT_FOUND"
    assert await harness.balance(ADMIN) == 0
    assert await harness.balance(OWNER) == 500
    assert await harness.ledger_rows(ADMIN) == []
    assert await harness.ledger_rows(OWNER) == []
    assert await harness.scalar("SELECT COUNT(*) FROM admin_audit_log") == 0


def test_no_route_is_left_under_wallet_admin():
    from fastapi.routing import APIRoute

    from webapp.main import app

    paths = [r.path for r in app.routes if isinstance(r, APIRoute)]
    assert [p for p in paths if p.startswith("/api/wallet/admin")] == []
    # The supported, rank-checked replacements are still registered.
    assert "/api/admin/users/{user_id}/balance" in paths
    assert "/api/admin/users/{user_id}/reset" in paths


@pytest.mark.parametrize("actor,role", [(ADMIN, "admin"), (OWNER, "owner")])
async def test_self_credit_through_the_supported_route_is_refused(harness, actor, role):
    body = {"user_id": actor, "amount": 1_000_000}
    headers = await harness.session(actor) | confirm_header(
        actor, "users.balance", {"user_id": actor, "amount": 1_000_000}
    )

    response = await harness.http.post(
        f"/api/admin/users/{actor}/balance", json=body, headers=headers
    )

    assert response.status_code == 403, response.text
    assert response.json()["detail"] == {"code": "CANNOT_TARGET_ADMIN", "role": role}
    assert await harness.balance(actor) == 0
    assert await harness.ledger_rows(actor) == []
    assert await harness.audit("users.balance") == []


async def test_admin_still_credits_a_plain_user_through_the_supported_route(harness):
    body = {"user_id": USER, "amount": 700}
    headers = await harness.session(ADMIN) | confirm_header(
        ADMIN, "users.balance", {"user_id": USER, "amount": 700}
    )

    response = await harness.http.post(f"/api/admin/users/{USER}/balance", json=body, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["new_balance"] == 700
    assert [row["kind"] for row in await harness.ledger_rows(USER)] == ["admin_credit"]
