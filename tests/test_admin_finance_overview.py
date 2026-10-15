"""GET /api/admin/finance/overview against the real app (tests/b3_support harness)."""

from __future__ import annotations

import time

from src.core.timeutil import now_tz
from tests import b3_support
from tests.b3_support import MODERATOR, USER, VIEWER

harness = b3_support.harness


async def _order(h, oid, *, user, amount, state, method, paid_at=None, created=None):
    now = int(time.time())
    created = created or now
    await h.execute(
        "INSERT INTO payment_orders (id, user_id, amount_soum, state, click_method, perform_time, "
        "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (oid, user, amount, state, method, (paid_at or 0) * 1000, created, created),
    )


async def _tx(h, user, kind, amount, at):
    await h.execute(
        "INSERT INTO wallet_transactions (user_id, kind, amount, balance_after, created_at) "
        "VALUES (?, ?, ?, 0, ?)",
        (user, kind, amount, at),
    )


async def test_overview_empty_db(harness):
    h = harness
    r = await h.http.get("/api/admin/finance/overview?days=7", headers=await h.session(VIEWER))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["paid_today"] == {"count": 0, "sum": 0}
    assert body["paid_all_time"] == {"count": 0, "sum": 0}
    assert body["by_method"] == []
    assert body["pro_buyers_all_time"] == 0
    assert len(body["series"]) == 7
    assert all(p["paid_sum"] == 0 for p in body["series"])


async def test_overview_aggregates(harness):
    h = harness
    now = int(time.time())
    old = now - 200 * 86400
    await _order(h, "o1", user=USER, amount=10_000, state="paid", method="card", paid_at=now)
    await _order(h, "o2", user=USER, amount=5_000, state="paid", method="app", paid_at=now)
    await _order(h, "o3", user=USER, amount=7_000, state="paid", method="card", paid_at=old, created=old)
    await _order(h, "o6", user=USER, amount=2_000, state="paid", method="card", paid_at=now - 3 * 86400, created=now - 3 * 86400)
    await _order(h, "o4", user=USER, amount=1_000, state="pending", method="card")
    await _order(h, "o5", user=USER, amount=1_000, state="cancelled", method="card")
    await _tx(h, USER, "pro_activation", -30_000, now)
    await _tx(h, USER, "pro_activation", -30_000, now)
    await _tx(h, VIEWER, "pro_activation", -30_000, old)
    await _tx(h, USER, "topup_bonus", 500, now)
    await h.execute("UPDATE users SET user_balance = 1234 WHERE user_id = ?", (USER,))

    r = await h.http.get("/api/admin/finance/overview?days=7", headers=await h.session(VIEWER))
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["paid_period"] == {"count": 3, "sum": 17_000}
    assert b["paid_all_time"] == {"count": 4, "sum": 24_000}
    assert b["pending_count"] == 1 and b["cancelled_count"] == 1
    assert {m["method"]: (m["count"], m["sum"]) for m in b["by_method"]} == {
        "card": (2, 12_000),
        "app": (1, 5_000),
    }
    assert b["pro_buyers_period"] == 1 and b["pro_buyers_all_time"] == 2
    assert b["balance_outstanding"] >= 1234
    last = b["series"][-1]
    assert last["day"] == now_tz().date().isoformat()
    assert (last["paid_sum"], last["paid_count"], last["pro_activations"], last["bonus_sum"]) == (
        15_000,
        2,
        2,
        500,
    )
    assert b["paid_today"]["sum"] == 15_000


async def test_overview_roles_and_validation(harness):
    h = harness
    anon = await h.http.get("/api/admin/finance/overview")
    assert anon.status_code in (401, 403)
    plain = await h.http.get("/api/admin/finance/overview", headers=await h.session(USER))
    assert plain.status_code == 403
    mod = await h.http.get("/api/admin/finance/overview", headers=await h.session(MODERATOR))
    assert mod.status_code == 200
    bad = await h.http.get("/api/admin/finance/overview?days=0", headers=await h.session(VIEWER))
    assert bad.status_code == 422
