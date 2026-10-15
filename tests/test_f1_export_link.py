"""The CSV download link has its own 300 s lifetime and a nonce per mint.

The link used to be a 60 s confirm token, which died while Telegram's native
``downloadFile`` popup waited for the admin, and whose single-use key was the
token itself, so two links minted for the same filters in the same second
were one link. ``POST /admin/users/export/link`` now mints
``<exp>.<nonce>.<mac>`` valid ``EXPORT_LINK_TTL_SECONDS``; the nonce is the
single-use claim. Confirm tokens for every other action are unchanged.

All ids are synthetic (>= 900000000000).
"""

from __future__ import annotations

import time

import pytest

from tests import b3_support
from tests.b3_support import ADMIN, OWNER
from webapp.core import confirm
from webapp.routers import admin_users

harness = b3_support.harness

URL = "/api/admin/users/export/download.csv"


class Clock:
    """``time.time`` the test can move; everything else keeps running."""

    def __init__(self, monkeypatch) -> None:
        self.now = float(int(time.time()))
        monkeypatch.setattr(time, "time", lambda: self.now)


@pytest.fixture
def clock(monkeypatch):
    return Clock(monkeypatch)


async def _mint(h, actor: int = ADMIN, params: dict | None = None) -> str:
    response = await h.http.post(
        "/api/admin/users/export/link",
        params=params or {"sort": "date"},
        headers=await h.session(actor),
    )
    assert response.status_code == 200, response.text
    assert response.json()["expires_in"] == 300
    return response.json()["token"]


def _download(h, token: str, actor: int = ADMIN, **params):
    return h.http.get(URL, params={"actor": actor, "dl": token, "sort": "date", **params})


def _refused(response) -> None:
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == {
        "code": "CONFIRMATION_REQUIRED",
        "action": "users.export_download",
    }


def test_link_ttl_is_longer_than_the_confirm_ttl():
    assert admin_users.EXPORT_LINK_TTL_SECONDS == 300
    assert confirm.confirm_ttl() == 60  # unchanged for every other action


async def test_link_still_works_after_the_confirm_ttl(harness, clock):
    token = await _mint(harness)
    clock.now += 290  # the admin took almost five minutes to tap "Download"
    response = await _download(harness, token)
    assert response.status_code == 200, response.text


async def test_link_dies_after_its_own_ttl(harness, clock):
    token = await _mint(harness)
    clock.now += 301
    _refused(await _download(harness, token))
    assert await harness.audit("users.export") == []


async def test_two_links_in_the_same_second_are_distinct_and_each_works_once(harness, clock):
    first = await _mint(harness)
    second = await _mint(harness)  # same actor, filters and second
    assert first != second
    assert first.split(".")[0] == second.split(".")[0]  # same expiry ...
    assert first.split(".")[1] != second.split(".")[1]  # ... different nonce

    assert (await _download(harness, first)).status_code == 200
    assert (await _download(harness, second)).status_code == 200
    _refused(await _download(harness, first))
    _refused(await _download(harness, second))

    claims = await harness.query(
        "SELECT idem_key FROM admin_idempotency WHERE action = 'users.export_download' "
        "ORDER BY rowid"
    )
    assert [row["idem_key"] for row in claims] == [first.split(".")[1], second.split(".")[1]]
    assert len(await harness.audit("users.export")) == 2


async def test_tampered_or_forged_links_are_refused(harness, clock):
    token = await _mint(harness)
    exp, nonce, mac = token.split(".")
    other_nonce = ("0" if nonce[0] != "0" else "1") + nonce[1:]
    far_exp = int(exp) + 3600
    forged_far = admin_users._export_link_mac(ADMIN, {"sort": "date"}, far_exp, nonce)
    for bad in (
        f"{exp}.{other_nonce}.{mac}",  # nonce swapped
        f"{int(exp) + 1}.{nonce}.{mac}",  # expiry stretched
        f"{far_exp}.{nonce}.{forged_far}",  # validly signed but past the TTL ceiling
        f"{exp}.{nonce.upper()}.{mac}",
        f"{exp}.{mac}",  # the old two-part shape
        f"x.{nonce}.{mac}",
    ):
        _refused(await _download(harness, bad))
    _refused(await _download(harness, token, actor=OWNER))  # another actor
    _refused(await _download(harness, token, pro="true"))  # widened filters
    # The genuine link is still unused after all of that.
    assert (await _download(harness, token)).status_code == 200


async def test_minting_writes_nothing_and_validates_sort(harness):
    await _mint(harness)
    assert await harness.scalar("SELECT COUNT(*) FROM admin_idempotency") == 0
    assert await harness.scalar("SELECT COUNT(*) FROM admin_audit_log") == 0

    bad = await harness.http.post(
        "/api/admin/users/export/link",
        params={"sort": "nope"},
        headers=await harness.session(ADMIN),
    )
    assert bad.status_code == 400, bad.text
    assert bad.json()["detail"]["code"] == "VALIDATION_ERROR"

    anonymous = await harness.http.post("/api/admin/users/export/link", params={"sort": "date"})
    assert anonymous.status_code == 401
