"""``X-Idempotency-Key`` on ``POST /admin/users/{id}/balance`` (m018 ``admin_idempotency``).

Contract: the same actor + key within 24 h returns the original response
(``Idempotent-Replayed: true``) and writes no second ledger row, even when the
duplicates arrive concurrently; the same key with a different body is 409
``IDEMPOTENCY_CONFLICT``; a refused request does not burn its key; no key at
all keeps the old behaviour.
"""

from __future__ import annotations

import asyncio
import json
import time

from tests import b3_support
from tests.b3_support import ADMIN, OWNER, USER, confirm_header

harness = b3_support.harness


async def _credit(h, actor: int, amount: int, key: str | None, *, headers=None, note=None):
    headers = dict(headers or await h.session(actor))
    headers |= confirm_header(actor, "users.balance", {"user_id": USER, "amount": amount})
    if key is not None:
        headers["X-Idempotency-Key"] = key
    body = {"user_id": USER, "amount": amount}
    if note is not None:
        body["note"] = note
    return await h.http.post(f"/api/admin/users/{USER}/balance", json=body, headers=headers)


async def test_same_key_replays_the_original_response(harness):
    first = await _credit(harness, ADMIN, 1000, "key-aaaaaaaa")
    second = await _credit(harness, ADMIN, 1000, "key-aaaaaaaa")

    assert first.status_code == 200 and second.status_code == 200, second.text
    assert second.json() == first.json()
    assert "idempotent-replayed" not in first.headers
    assert second.headers["idempotent-replayed"] == "true"
    assert await harness.balance(USER) == 1000
    assert len(await harness.ledger_rows(USER)) == 1
    audit = await harness.audit("users.balance")
    assert len(audit) == 1
    assert json.loads(audit[0]["payload_json"])["idempotency_key"] == "key-aaaaaaaa"


async def test_concurrent_duplicates_write_one_ledger_row(harness):
    # Sessions first, so the concurrent part is only the mutation itself.
    sessions = [await harness.session(ADMIN) for _ in range(5)]
    responses = await asyncio.gather(
        *(_credit(harness, ADMIN, 700, "key-concurrent", headers=s) for s in sessions)
    )

    assert [r.status_code for r in responses] == [200] * 5, [r.text for r in responses]
    assert len({r.json()["tx_id"] for r in responses}) == 1
    assert sum(r.headers.get("idempotent-replayed") == "true" for r in responses) == 4
    assert await harness.balance(USER) == 700
    assert len(await harness.ledger_rows(USER)) == 1
    assert len(await harness.audit("users.balance")) == 1


async def test_same_key_with_a_different_body_is_a_conflict(harness):
    assert (await _credit(harness, ADMIN, 1000, "key-bbbbbbbb")).status_code == 200

    other_amount = await _credit(harness, ADMIN, 2000, "key-bbbbbbbb")
    assert other_amount.status_code == 409
    assert other_amount.json()["detail"] == {"code": "IDEMPOTENCY_CONFLICT"}

    other_note = await _credit(harness, ADMIN, 1000, "key-bbbbbbbb", note="typo fix")
    assert other_note.status_code == 409

    assert await harness.balance(USER) == 1000
    assert len(await harness.ledger_rows(USER)) == 1


async def test_keys_are_per_actor(harness):
    """Another admin's key is a different claim, never someone else's replay."""
    assert (await _credit(harness, ADMIN, 100, "key-shared1")).status_code == 200
    response = await _credit(harness, OWNER, 100, "key-shared1")
    assert response.status_code == 200
    assert "idempotent-replayed" not in response.headers
    assert [row["actor_id"] for row in await harness.ledger_rows(USER)] == [ADMIN, OWNER]


async def test_distinct_keys_and_no_key_each_write(harness):
    for key in ("key-11111111", "key-22222222", None, None):
        assert (await _credit(harness, ADMIN, 10, key)).status_code == 200
    assert await harness.balance(USER) == 40
    assert len(await harness.ledger_rows(USER)) == 4


async def test_a_refused_request_does_not_burn_its_key(harness):
    refused = await _credit(harness, ADMIN, -500, "key-refused")
    assert refused.status_code == 400
    assert refused.json()["detail"]["code"] == "INSUFFICIENT_BALANCE"
    assert await harness.query("SELECT * FROM admin_idempotency") == []

    await harness.execute("UPDATE users SET user_balance = 800 WHERE user_id = ?", (USER,))
    retried = await _credit(harness, ADMIN, -500, "key-refused")
    assert retried.status_code == 200, retried.text
    assert "idempotent-replayed" not in retried.headers
    assert await harness.balance(USER) == 300


async def test_a_key_older_than_24h_counts_as_new(harness):
    assert (await _credit(harness, ADMIN, 100, "key-expiring")).status_code == 200
    await harness.execute(
        "UPDATE admin_idempotency SET created_at = ?", (int(time.time()) - 24 * 3600 - 5,)
    )
    again = await _credit(harness, ADMIN, 100, "key-expiring")
    assert again.status_code == 200
    assert "idempotent-replayed" not in again.headers
    assert len(await harness.ledger_rows(USER)) == 2
    # The expired claim was replaced, not duplicated.
    assert await harness.scalar("SELECT COUNT(*) FROM admin_idempotency") == 1


async def test_a_malformed_key_is_rejected(harness):
    for key in ("short", "x" * 129, "has space here", "semi;colon-key"):
        response = await _credit(harness, ADMIN, 100, key)
        assert response.status_code == 400, key
        assert response.json()["detail"] == {"code": "VALIDATION_ERROR", "field": "idempotency_key"}
    assert await harness.ledger_rows(USER) == []
