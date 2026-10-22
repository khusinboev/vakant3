"""``GET /admin/users/export.csv`` and its single-use download-link twin.

Checks the contract the Users page relies on: same filters and order as the
list endpoint, formula-injection-safe cells, UTF-8 BOM, chunked keyset reads
on the stream's own connection, the row cap, role ``admin``+, the 2/minute
limit, the ``users.export`` audit row, and that the link variant is bound to
its actor and filters and works once.
"""

from __future__ import annotations

import csv
import io
import json
import re

import pytest

from tests import b3_support
from tests.b3_support import ADMIN, MODERATOR, OWNER, confirm_header
from webapp.core.database import open_connection
from webapp.main import app
from webapp.routers import admin_users

harness = b3_support.harness

BOM = chr(0xFEFF)
BASE = 900_000_100_000


def _parse(response) -> list[dict[str, str]]:
    text = response.content.decode("utf-8")
    assert text.startswith(BOM)
    return list(csv.DictReader(io.StringIO(text[1:], newline="")))


async def _seed(h, count: int = 30) -> None:
    for i in range(count):
        await h.add_user(
            BASE + i,
            date=1_700_000_000 + (i % 7) * 1000,  # ties, so the user_id tie-break matters
            lang=("uz", "ru", "en")[i % 3],
            user_pro=1 if i % 4 == 0 else 0,
            user_balance=(i * 37) % 11 * 100,
            last_seen_at=None if i % 5 == 0 else 1_700_100_000 + i,
            first_name=f"User {i}",
        )


async def _list_ids(h, headers, params) -> list[int]:
    ids: list[int] = []
    cursor = None
    while True:
        query = dict(params, limit=4)
        if cursor:
            query["cursor"] = cursor
        body = (await h.http.get("/api/admin/users", params=query, headers=headers)).json()
        ids.extend(item["user_id"] for item in body["items"])
        cursor = body["next_cursor"]
        if not cursor:
            return ids


# ---------------------------------------------------------------------------
# cell escaping
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r"])
def test_formula_prefixes_are_neutralised(prefix):
    assert admin_users.csv_cell(f"{prefix}cmd|' /C calc'!A0") == f"'{prefix}cmd|' /C calc'!A0"


def test_other_cells_are_left_alone():
    assert admin_users.csv_cell("Ali") == "Ali"
    assert admin_users.csv_cell("a=b") == "a=b"
    assert admin_users.csv_cell(-500) == -500  # a real negative number stays numeric
    assert admin_users.csv_cell("-500") == "'-500"  # ... but text that looks like one does not
    assert admin_users.csv_cell(None) == ""
    assert admin_users.csv_cell(True) == 1
    assert admin_users.csv_cell("nul\x00byte") == "nulbyte"


# ---------------------------------------------------------------------------
# the endpoint
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "params",
    [
        {},
        {"sort": "balance"},
        {"sort": "last_seen"},
        {"lang": "ru", "sort": "last_seen"},
        {"pro": "true"},
        {"pro": "false", "from": 1_700_002_000, "to": 1_700_005_000},
        {"q": "User 1"},
    ],
)
async def test_export_matches_the_list_filters_and_order(harness, params):
    await _seed(harness)
    headers = await harness.session(ADMIN)
    expected = [i for i in await _list_ids(harness, headers, params) if i >= BASE]

    response = await harness.http.get("/api/admin/users/export.csv", params=params, headers=headers)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    exported = [int(row["user_id"]) for row in _parse(response) if int(row["user_id"]) >= BASE]
    assert exported == expected
    assert expected  # the filters do match something


async def test_columns_are_exactly_the_list_fields_and_cells_are_safe(harness):
    await harness.add_user(
        BASE,
        first_name='=HYPERLINK("http://evil","x")',
        username="@sneaky",
        banned_reason='line one\nline "two", three',
        user_balance=-300,
        photo_url="https://t.me/i/secret.jpg",
        pref_filters_json='{"x": 1}',
    )
    response = await harness.http.get(
        "/api/admin/users/export.csv", params={"q": str(BASE)}, headers=await harness.session(ADMIN)
    )
    text = response.content.decode("utf-8")
    header = text[1:].split("\r\n", 1)[0]
    assert header.split(",") == list(admin_users.CSV_COLUMNS)
    assert "secret.jpg" not in text and "pref_filters" not in text

    (row,) = _parse(response)
    assert row["first_name"] == "'=HYPERLINK(\"http://evil\",\"x\")"
    assert row["username"] == "'@sneaky"
    assert row["banned_reason"] == 'line one\nline "two", three'  # quoted, not split
    assert row["balance"] == "-300"


async def test_export_reads_in_chunks_on_its_own_connection(harness, monkeypatch):
    await _seed(harness, 23)
    monkeypatch.setattr(admin_users, "EXPORT_CHUNK", 5)
    statements: list[str] = []

    async def traced():
        conn = await open_connection(harness.path)
        await conn.set_trace_callback(statements.append)
        return conn

    app.dependency_overrides[admin_users.get_export_connector] = lambda: traced
    response = await harness.http.get(
        "/api/admin/users/export.csv", params={"sort": "last_seen"}, headers=await harness.session(ADMIN)
    )

    rows = _parse(response)
    ids = [int(row["user_id"]) for row in rows]
    assert len(ids) == len(set(ids))
    assert {i for i in ids if i >= BASE} == {BASE + i for i in range(23)}
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    # The trace shows the bound values: every read is one chunk of EXPORT_CHUNK.
    limits = [int(re.search(r"LIMIT (\d+)\s*$", s).group(1)) for s in selects]
    assert limits and max(limits) == 5, selects
    assert len(selects) >= -(-len(ids) // 5)


async def test_row_cap_truncates_and_is_reported(harness, monkeypatch):
    await _seed(harness, 12)
    monkeypatch.setattr(admin_users, "EXPORT_MAX_ROWS", 5)
    response = await harness.http.get(
        "/api/admin/users/export.csv", headers=await harness.session(ADMIN)
    )
    assert len(_parse(response)) == 5
    assert response.headers["x-export-rows"] == "5"
    assert response.headers["x-export-truncated"] == "1"
    payload = json.loads((await harness.audit("users.export"))[-1]["payload_json"])
    assert payload["row_count"] == 5 and payload["truncated"] is True


async def test_export_is_audited_with_filters_and_count(harness):
    await _seed(harness, 9)
    response = await harness.http.get(
        "/api/admin/users/export.csv",
        params={"lang": "ru", "pro": "false", "q": "  User  "},
        headers=await harness.session(OWNER),
    )
    assert response.status_code == 200
    rows = await harness.audit("users.export")
    assert [r["actor_id"] for r in rows] == [OWNER]
    payload = json.loads(rows[0]["payload_json"])
    assert payload["filters"] == {"sort": "date", "lang": "ru", "pro": False, "q": "User"}
    assert payload["row_count"] == len(_parse(response))
    assert payload["via"] == "session"


async def test_export_requires_admin(harness):
    moderator = await harness.http.get(
        "/api/admin/users/export.csv", headers=await harness.session(MODERATOR)
    )
    assert moderator.status_code == 403
    assert moderator.json()["detail"]["code"] == "ADMIN_REQUIRED"
    anonymous = await harness.http.get("/api/admin/users/export.csv")
    assert anonymous.status_code == 401
    assert await harness.audit("users.export") == []


async def test_export_is_rate_limited(harness):
    limiter = app.state.limiter
    limiter.reset()
    limiter.enabled = True
    try:
        headers = await harness.session(ADMIN)
        codes = [
            (await harness.http.get("/api/admin/users/export.csv", headers=headers)).status_code
            for _ in range(3)
        ]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes == [200, 200, 429]


# ---------------------------------------------------------------------------
# single-use download link (Telegram.WebApp.downloadFile)
# ---------------------------------------------------------------------------
async def _mint_link(h, actor: int, params: dict) -> str:
    """``POST /admin/users/export/link`` with the filters as query parameters."""
    response = await h.http.post(
        "/api/admin/users/export/link", params=params, headers=await h.session(actor)
    )
    assert response.status_code == 200, response.text
    assert response.json()["expires_in"] == admin_users.EXPORT_LINK_TTL_SECONDS
    return response.json()["token"]


async def test_download_link_works_once_and_matches_the_session_export(harness):
    await _seed(harness, 8)
    # Same canonical dict the frontend signs: unset filters omitted, real types.
    signed = {"sort": "balance", "lang": "uz", "pro": False}
    token = await _mint_link(harness, ADMIN, signed)
    query = {"sort": "balance", "lang": "uz", "pro": "false", "actor": ADMIN, "dl": token}

    first = await harness.http.get("/api/admin/users/export/download.csv", params=query)
    assert first.status_code == 200, first.text
    via_session = await harness.http.get(
        "/api/admin/users/export.csv",
        params={"sort": "balance", "lang": "uz", "pro": "false"},
        headers=await harness.session(ADMIN),
    )
    assert _parse(first) == _parse(via_session)
    assert json.loads((await harness.audit("users.export"))[0]["payload_json"])["via"] == "link"

    replay = await harness.http.get("/api/admin/users/export/download.csv", params=query)
    assert replay.status_code == 403
    assert replay.json()["detail"]["code"] == "CONFIRMATION_REQUIRED"


async def test_download_link_is_bound_to_actor_filters_and_role(harness):
    token = await _mint_link(harness, ADMIN, {"sort": "date"})
    url = "/api/admin/users/export/download.csv"

    widened = await harness.http.get(url, params={"actor": ADMIN, "dl": token, "sort": "date", "pro": "true"})
    assert widened.status_code == 403
    other_actor = await harness.http.get(url, params={"actor": OWNER, "dl": token, "sort": "date"})
    assert other_actor.status_code == 403

    # A moderator cannot mint a link ...
    refused_mint = await harness.http.post(
        "/api/admin/users/export/link",
        params={"sort": "date"},
        headers=await harness.session(MODERATOR),
    )
    assert refused_mint.status_code == 403
    assert refused_mint.json()["detail"]["code"] == "ADMIN_REQUIRED"
    # ... and a link minted while they still ranked admin dies with the demotion,
    # because the role is re-read at download.
    moderator_token = admin_users.issue_export_link_token(MODERATOR, {"sort": "date"})
    moderator = await harness.http.get(
        url, params={"actor": MODERATOR, "dl": moderator_token, "sort": "date"}
    )
    assert moderator.status_code == 403
    assert moderator.json()["detail"]["code"] == "ADMIN_REQUIRED"

    # Revoking the admin kills a link minted a moment earlier.
    await harness.execute("UPDATE admins SET disabled = 1 WHERE user_id = ?", (ADMIN,))
    revoked = await harness.http.get(url, params={"actor": ADMIN, "dl": token, "sort": "date"})
    assert revoked.status_code == 403
    assert revoked.json()["detail"]["code"] == "ADMIN_REQUIRED"
    assert await harness.audit("users.export") == []


async def test_download_link_needs_a_real_token(harness):
    url = "/api/admin/users/export/download.csv"
    forged = confirm_header(ADMIN, "users.balance", {"sort": "date"})["X-Confirm-Token"]
    # A confirm token for the export action itself is not a link token either.
    confirm_kind = confirm_header(ADMIN, "users.export_download", {"sort": "date"})[
        "X-Confirm-Token"
    ]
    for params in (
        {"actor": ADMIN, "sort": "date"},  # no token at all
        {"actor": ADMIN, "dl": "1.deadbeef", "sort": "date"},
        {"actor": ADMIN, "dl": forged, "sort": "date"},  # a token for another action
        {"actor": ADMIN, "dl": confirm_kind, "sort": "date"},
    ):
        response = await harness.http.get(url, params=params)
        assert response.status_code in (403, 422), params
