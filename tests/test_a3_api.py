"""API package A3: upstream failures, pool release around HTTP, input bounds, unknown /api.

The real app runs in the test's event loop through ``httpx.ASGITransport``
(so ``asyncio`` events can pause a stubbed upstream mid-request), against the
session's temp database. Only the osonish boundary
(``fetch_osonish_list`` / ``get_osonish_detail`` as imported by the routers)
and Telegram's ``getChatMember`` are stubbed.
"""

import asyncio
import hashlib
import hmac
import json
import time
import urllib.parse

import aiohttp
import aiosqlite
import httpx
import pytest

from src.functions import cache as cache_module
from src.functions.scraping import MAX_OSONISH_ID, UpstreamError, Vacancy
from webapp.core import database, entry_gate, subscription
from webapp.core.config import DB_PATH, get_settings
from webapp.main import app
from webapp.routers import jobs as jobs_router
from webapp.routers import saves as saves_router

USER_ID = 900_000_000_301

BOT_OWNED_DDL = (
    "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, date INTEGER, "
    "lang TEXT, region TEXT, district TEXT, specs TEXT, money INTEGER)",
    "CREATE TABLE IF NOT EXISTS channels (id TEXT PRIMARY KEY)",
    "CREATE TABLE IF NOT EXISTS saves (user_id INTEGER, save_id INTEGER, "
    "PRIMARY KEY (user_id, save_id))",
    "CREATE TABLE IF NOT EXISTS regions (soato TEXT PRIMARY KEY, name_uz TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS districts (soato TEXT PRIMARY KEY, "
    "region_soato TEXT NOT NULL, name_uz TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS referral_payouts (user_id INTEGER PRIMARY KEY, "
    "inviter_id INTEGER NOT NULL, amount INTEGER NOT NULL, ts INTEGER NOT NULL)",
)


def init_data_for(user_id: int) -> str:
    token = get_settings().TOKEN
    fields = {
        "auth_date": str(int(time.time())),
        "query_id": "AAE-a3",
        "user": json.dumps({"id": user_id, "first_name": "A3", "language_code": "uz"}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(fields)


HEADERS = {"X-Telegram-Init-Data": init_data_for(USER_ID)}


async def _sql(sql: str, params: tuple = ()) -> list[dict]:
    async with aiosqlite.connect(str(DB_PATH)) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA busy_timeout=5000")
        cursor = await conn.execute(sql, params)
        rows = [dict(r) for r in await cursor.fetchall()]
        await conn.commit()
        return rows


async def _telegram_member(method, params):
    return 200, {"ok": True, "result": {"status": "member", "id": 1}}


@pytest.fixture
def pool_size():
    return 16


@pytest.fixture
async def client(monkeypatch, pool_size):
    monkeypatch.setattr(database, "POOL_SIZE", pool_size)
    monkeypatch.setattr(database, "ACQUIRE_TIMEOUT_SECONDS", 0.5)
    await database.reset_pool()
    async with aiosqlite.connect(str(DB_PATH)) as conn:
        for ddl in BOT_OWNED_DDL:
            await conn.execute(ddl)
        await conn.commit()
    await database.init_db()
    entry_gate.reset_users_columns_cache()
    monkeypatch.setattr(subscription, "_request", _telegram_member)

    async def _no_network(*args, **kwargs):
        raise AssertionError("an outbound HTTP call escaped the stubs")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", _no_network)
    cache_module._mem_cache.clear()

    await _sql("INSERT OR IGNORE INTO users (user_id, date, lang) VALUES (?, ?, 'uz')", (USER_ID, int(time.time())))
    await _sql(
        "UPDATE users SET started_at = ?, region = NULL, district = NULL, specs = NULL, money = NULL, "
        "pref_filters_json = NULL, user_pro = 0 WHERE user_id = ?",
        (int(time.time()), USER_ID),
    )
    await _sql("DELETE FROM saves WHERE user_id = ?", (USER_ID,))
    await _sql("UPDATE webapp_admin_settings SET referral_enabled = 0 WHERE singleton = 1")

    previous = app.state.limiter.enabled
    app.state.limiter.enabled = False
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http
    finally:
        app.state.limiter.enabled = previous
        cache_module._mem_cache.clear()
        await database.reset_pool()


def _vacancy(raw_id: int) -> Vacancy:
    return Vacancy(
        uid=f"osonish_{raw_id}", title="Synthetic", company="ACME", salary_text="1 000",
        location="Toshkent", district="", posted_at="01.10.2026", raw_id=raw_id, max_salary=1000,
    )


# ---------------------------------------------------------------------------
# 1. Upstream failure contract
# ---------------------------------------------------------------------------


async def test_search_outage_is_502_and_never_cached(client, monkeypatch):
    calls = {"n": 0, "down": True}

    async def fake_list(**kwargs):
        calls["n"] += 1
        if calls["down"]:
            raise UpstreamError("http_status", 503)
        return [_vacancy(900000000001)], 4

    monkeypatch.setattr(jobs_router, "fetch_osonish_list", fake_list)

    down = await client.get("/api/jobs/search", headers=HEADERS)
    assert down.status_code == 502, down.text
    assert down.json()["detail"] == {"code": "UPSTREAM_ERROR"}

    # osonish recovers: the very next identical request goes upstream again.
    calls["down"] = False
    up = await client.get("/api/jobs/search", headers=HEADERS)
    assert up.status_code == 200, up.text
    assert [v["uid"] for v in up.json()["vacancies"]] == ["osonish_900000000001"]
    assert calls["n"] == 2

    # A good answer *is* cached.
    again = await client.get("/api/jobs/search", headers=HEADERS)
    assert again.status_code == 200
    assert calls["n"] == 2


async def test_search_genuine_empty_result_is_200(client, monkeypatch):
    async def fake_list(**kwargs):
        return [], 1

    monkeypatch.setattr(jobs_router, "fetch_osonish_list", fake_list)
    response = await client.get("/api/jobs/search", headers=HEADERS)
    assert response.status_code == 200, response.text
    assert response.json()["vacancies"] == []


async def test_search_marks_saved_vacancies(client, monkeypatch):
    async def fake_list(**kwargs):
        return [_vacancy(900000000011), _vacancy(900000000012)], 1

    monkeypatch.setattr(jobs_router, "fetch_osonish_list", fake_list)
    await _sql("INSERT INTO saves (user_id, save_id) VALUES (?, ?)", (USER_ID, 900000000012))
    body = (await client.get("/api/jobs/search", headers=HEADERS)).json()
    assert {v["uid"]: v["is_saved"] for v in body["vacancies"]} == {
        "osonish_900000000011": False,
        "osonish_900000000012": True,
    }


async def test_detail_404_only_when_osonish_says_not_found(client, monkeypatch):
    answers = {}

    async def fake_detail(raw_id):
        answer = answers[raw_id]
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(jobs_router, "get_osonish_detail", fake_detail)
    answers[900000000021] = None
    answers[900000000022] = UpstreamError("transport: TimeoutError")
    answers[900000000023] = {"id": 900000000023, "title": "Found"}

    missing = await client.get("/api/jobs/osonish_900000000021", headers=HEADERS)
    assert missing.status_code == 404
    assert missing.json()["detail"] == {"code": "NOT_FOUND", "resource": "vacancy"}

    outage = await client.get("/api/jobs/osonish_900000000022", headers=HEADERS)
    assert outage.status_code == 502
    assert outage.json()["detail"] == {"code": "UPSTREAM_ERROR"}
    # Not cached: once osonish answers, the same uid works.
    answers[900000000022] = {"id": 900000000022, "title": "Back"}
    recovered = await client.get("/api/jobs/osonish_900000000022", headers=HEADERS)
    assert recovered.status_code == 200
    assert recovered.json()["data"]["title"] == "Back"

    found = await client.get("/api/jobs/osonish_900000000023", headers=HEADERS)
    assert found.status_code == 200
    assert found.json()["data"]["title"] == "Found"


# ---------------------------------------------------------------------------
# 2. The pooled connection is not held across upstream HTTP
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pool_size", [1])
async def test_slow_search_does_not_pin_the_only_connection(client, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked_list(**kwargs):
        entered.set()
        await release.wait()
        return [_vacancy(900000000031)], 1

    monkeypatch.setattr(jobs_router, "fetch_osonish_list", blocked_list)
    search = asyncio.create_task(client.get("/api/jobs/search", headers=HEADERS))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        # The search is parked inside "osonish"; an unrelated DB route still gets the slot.
        other = await asyncio.wait_for(client.get("/api/filters/regions"), 5)
        assert other.status_code == 200, other.text
    finally:
        release.set()
    response = await asyncio.wait_for(search, 5)
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("pool_size", [1])
async def test_slow_detail_does_not_pin_the_only_connection(client, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked_detail(raw_id):
        entered.set()
        await release.wait()
        return {"id": raw_id, "title": "Slow"}

    monkeypatch.setattr(jobs_router, "get_osonish_detail", blocked_detail)
    detail = asyncio.create_task(client.get("/api/jobs/osonish_900000000041", headers=HEADERS))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        other = await asyncio.wait_for(client.get("/api/filters/regions"), 5)
        assert other.status_code == 200, other.text
    finally:
        release.set()
    assert (await asyncio.wait_for(detail, 5)).status_code == 200


async def _park_and_probe(client, monkeypatch, request_coro, expected_parked: int):
    """Park ``request_coro`` inside the stubbed osonish detail fetch, probe an unrelated DB route."""
    release = asyncio.Event()
    waiting = {"n": 0}

    async def blocked_detail(raw_id):
        waiting["n"] += 1
        await release.wait()
        return {"id": raw_id, "title": f"Saved {raw_id}"}

    monkeypatch.setattr(saves_router, "get_osonish_detail", blocked_detail)
    task = asyncio.create_task(request_coro)
    try:
        for _ in range(500):
            if waiting["n"] >= expected_parked:
                break
            await asyncio.sleep(0.01)
        assert waiting["n"] == expected_parked
        other = await asyncio.wait_for(client.get("/api/filters/regions"), 5)
        assert other.status_code == 200, other.text
    finally:
        release.set()
    return await asyncio.wait_for(task, 5)


@pytest.mark.parametrize("pool_size", [1])
async def test_saves_list_does_not_pin_the_only_connection(client, monkeypatch):
    for raw_id in (900000000051, 900000000052, 900000000053):
        await _sql("INSERT INTO saves (user_id, save_id) VALUES (?, ?)", (USER_ID, raw_id))
    listed = await _park_and_probe(client, monkeypatch, client.get("/api/saves", headers=HEADERS), 3)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] == 3
    assert sorted(item["data"]["title"] for item in body["items"]) == [
        "Saved 900000000051", "Saved 900000000052", "Saved 900000000053",
    ]


@pytest.mark.parametrize("pool_size", [1])
async def test_saves_add_does_not_pin_the_only_connection(client, monkeypatch):
    added = await _park_and_probe(
        client, monkeypatch, client.post("/api/saves/osonish_900000000054", headers=HEADERS), 1
    )
    assert added.status_code == 200 and added.json()["saved"] is True
    rows = await _sql("SELECT save_id FROM saves WHERE user_id = ?", (USER_ID,))
    assert [r["save_id"] for r in rows] == [900000000054]


async def test_saves_list_marks_outage_rows_unavailable(client, monkeypatch):
    await _sql("INSERT INTO saves (user_id, save_id) VALUES (?, ?)", (USER_ID, 900000000061))

    async def down(raw_id):
        raise UpstreamError("http_status", 500)

    monkeypatch.setattr(saves_router, "get_osonish_detail", down)
    body = (await client.get("/api/saves", headers=HEADERS)).json()
    assert body["total"] == 1
    assert body["items"][0]["uid"] == "osonish_900000000061"
    assert body["items"][0]["unavailable"] is True


# ---------------------------------------------------------------------------
# 3. Input validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uid",
    [
        "osonish_" + "9" * 40,
        f"osonish_{MAX_OSONISH_ID + 1}",
        "osonish_-5",
        "osonish_0",
        "osonish_abc",
        "12345",
    ],
)
async def test_add_save_rejects_bad_uid(client, monkeypatch, uid):
    async def never(raw_id):  # pragma: no cover - must not be reached
        raise AssertionError("upstream called for an invalid uid")

    monkeypatch.setattr(saves_router, "get_osonish_detail", never)
    response = await client.post(f"/api/saves/{uid}", headers=HEADERS)
    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "INVALID_UID"
    assert await _sql("SELECT save_id FROM saves WHERE user_id = ?", (USER_ID,)) == []


async def test_add_save_accepts_the_largest_id(client, monkeypatch):
    async def none(raw_id):
        return None

    monkeypatch.setattr(saves_router, "get_osonish_detail", none)
    response = await client.post(f"/api/saves/osonish_{MAX_OSONISH_ID}", headers=HEADERS)
    assert response.status_code == 200, response.text
    rows = await _sql("SELECT save_id FROM saves WHERE user_id = ?", (USER_ID,))
    assert [r["save_id"] for r in rows] == [MAX_OSONISH_ID]


@pytest.mark.parametrize(
    "stored, uid",
    [
        (0, "osonish_0"),
        (-5, "osonish_-5"),
        (MAX_OSONISH_ID + 1, f"osonish_{MAX_OSONISH_ID + 1}"),
        (2**63 - 1, f"osonish_{2**63 - 1}"),
        ("osonish_77", "osonish_77"),  # legacy text row
    ],
)
async def test_legacy_rows_rejected_by_post_can_still_be_deleted(client, monkeypatch, stored, uid):
    """Rows stored before the strict uid check must not stay stuck in the free 5-save limit."""
    async def gone(raw_id):
        return None

    monkeypatch.setattr(saves_router, "get_osonish_detail", gone)
    await _sql("INSERT INTO saves (user_id, save_id) VALUES (?, ?)", (USER_ID, stored))
    listed = (await client.get("/api/saves", headers=HEADERS)).json()
    assert [item["uid"] for item in listed["items"]] == [uid]

    response = await client.delete(f"/api/saves/{uid}", headers=HEADERS)
    assert response.status_code == 200, response.text
    assert await _sql("SELECT save_id FROM saves WHERE user_id = ?", (USER_ID,)) == []


@pytest.mark.parametrize("uid", ["osonish_abc", "osonish_" + "9" * 40, "12345", "osonish_"])
async def test_delete_still_rejects_garbage_uids(client, uid):
    response = await client.delete(f"/api/saves/{uid}", headers=HEADERS)
    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "INVALID_UID"


async def test_delete_only_removes_the_matching_row(client):
    await _sql("INSERT INTO saves (user_id, save_id) VALUES (?, ?)", (USER_ID, 900000000081))
    await _sql("INSERT INTO saves (user_id, save_id) VALUES (?, ?)", (USER_ID, 900000000082))
    assert (await client.delete("/api/saves/osonish_900000000081", headers=HEADERS)).status_code == 200
    rows = await _sql("SELECT save_id FROM saves WHERE user_id = ?", (USER_ID,))
    assert [r["save_id"] for r in rows] == [900000000082]


@pytest.mark.parametrize(
    "body",
    [
        {"money": 10**30},
        {"money": 10**12 + 1},
        {"money": -1},
        {"region": "1" * 33},
        {"district": "1" * 33},
        {"specs": "1," * 200},
    ],
)
async def test_filters_out_of_range_is_422(client, body):
    response = await client.patch("/api/profile/filters", headers=HEADERS, json=body)
    assert response.status_code == 422, response.text
    rows = await _sql("SELECT money, region, specs, pref_filters_json FROM users WHERE user_id = ?", (USER_ID,))
    assert rows == [{"money": None, "region": None, "specs": None, "pref_filters_json": None}]


async def test_clearing_filters_clears_pref_filters_json(client):
    async def prefs():
        rows = await _sql("SELECT pref_filters_json FROM users WHERE user_id = ?", (USER_ID,))
        raw = rows[0]["pref_filters_json"]
        return None if raw is None else json.loads(raw)

    ok = await client.patch(
        "/api/profile/filters", headers=HEADERS, json={"region": "1726", "money": 10**12, "specs": "spec:42"}
    )
    assert ok.status_code == 200, ok.text
    assert await prefs() == {"region_soato": "1726", "min_salary": 10**12, "specs": "spec:42"}

    # Partial clear keeps the rest.
    await client.patch("/api/profile/filters", headers=HEADERS, json={"region": None})
    assert await prefs() == {"min_salary": 10**12, "specs": "spec:42"}

    # Clearing everything leaves no stale filter for the notification scheduler.
    cleared = await client.patch("/api/profile/filters", headers=HEADERS, json={"money": 0, "specs": ""})
    assert cleared.status_code == 200
    assert await prefs() is None


# ---------------------------------------------------------------------------
# 6. Unknown /api/* paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
async def test_unknown_api_path_is_404_json_for_every_method(client, method):
    response = await client.request(method, "/api/definitely/not/here", headers=HEADERS)
    assert response.status_code == 404, response.text
    assert response.json() == {"detail": {"code": "NOT_FOUND", "resource": "endpoint"}}


async def test_known_api_path_with_wrong_method_stays_405(client):
    assert (await client.delete("/api/health")).status_code == 405
    assert (await client.post("/api/jobs/osonish_1", headers=HEADERS)).status_code == 405
    assert (await client.get("/api/health")).json() == {"ok": True}


@pytest.fixture
def spa_catch_all():
    """Production shape: frontend/dist exists, so main.py registered GET /{path:path} last."""
    async def frontend(path: str):
        return {"spa": path}

    before = list(app.router.routes)
    # A local build (webapp/frontend/dist) makes main.py register the real catch-all already; replace it so the
    # test sees the same shape with or without dist.
    app.router.routes[:] = [r for r in before if getattr(r, "path", None) != "/{path:path}"]
    app.add_api_route("/{path:path}", frontend, methods=["GET"])
    try:
        yield
    finally:
        app.router.routes[:] = before


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
async def test_unknown_api_path_is_404_json_with_the_spa_catch_all(client, spa_catch_all, method):
    response = await client.request(method, "/api/definitely/not/here", headers=HEADERS)
    assert response.status_code == 404, response.text
    assert response.json() == {"detail": {"code": "NOT_FOUND", "resource": "endpoint"}}
    # Known paths keep their 405, and non-API GETs still reach the SPA.
    assert (await client.delete("/api/health")).status_code == 405
    assert (await client.get("/some/page")).json() == {"spa": "some/page"}


# ---------------------------------------------------------------------------
# 2b. Resume send-telegram does not hold the connection across PDF/Telegram
# ---------------------------------------------------------------------------


class _FakeTelegramResponse:
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body
        self.content = json.dumps(body).encode()

    def json(self):
        return self._body


def _stub_telegram_send(monkeypatch, handler):
    """Replace only the router's ``httpx.AsyncClient`` (the test client keeps the real one)."""
    import importlib
    import types

    # ``webapp.resume`` re-exports the APIRouter as ``router``; load the module itself.
    resume_router = importlib.import_module("webapp.resume.router")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, data=None, files=None):
            assert "/sendDocument" in url
            assert data["chat_id"] == str(USER_ID)
            return await handler()

    fake_httpx = types.SimpleNamespace(AsyncClient=FakeClient, HTTPError=httpx.HTTPError)
    monkeypatch.setattr(resume_router, "httpx", fake_httpx)


async def _export_rows() -> list[dict]:
    return await _sql(
        "SELECT status, error_text, completed_at FROM resume_exports WHERE user_id = ? ORDER BY id",
        (USER_ID,),
    )


@pytest.mark.parametrize("pool_size", [1])
async def test_slow_resume_send_does_not_pin_the_only_connection(client, monkeypatch):
    await _sql("DELETE FROM resume_exports WHERE user_id = ?", (USER_ID,))
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked_send():
        entered.set()
        await release.wait()
        return _FakeTelegramResponse(200, {"ok": True, "result": {}})

    _stub_telegram_send(monkeypatch, blocked_send)
    send = asyncio.create_task(
        client.post("/api/resume/send-telegram", json={"template_id": "clean"}, headers=HEADERS)
    )
    try:
        await asyncio.wait_for(entered.wait(), 15)
        # Parked inside "Telegram": the export row is already committed as pending
        # and an unrelated DB route still gets the only slot.
        assert [r["status"] for r in await _export_rows()] == ["pending"]
        other = await asyncio.wait_for(client.get("/api/filters/regions"), 5)
        assert other.status_code == 200, other.text
    finally:
        release.set()
    response = await asyncio.wait_for(send, 15)
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True, "status": "SENT"}
    rows = await _export_rows()
    assert len(rows) == 1
    assert rows[0]["status"] == "completed" and rows[0]["error_text"] is None
    assert rows[0]["completed_at"]


@pytest.mark.parametrize("pool_size", [1])
async def test_resume_send_failure_is_recorded_after_release(client, monkeypatch):
    await _sql("DELETE FROM resume_exports WHERE user_id = ?", (USER_ID,))

    async def rejected():
        return _FakeTelegramResponse(403, {"ok": False, "description": "Forbidden"})

    _stub_telegram_send(monkeypatch, rejected)
    response = await client.post("/api/resume/send-telegram", json={"template_id": "clean"}, headers=HEADERS)
    assert response.status_code == 502, response.text
    assert response.json()["detail"]["code"] == "TELEGRAM_SEND_FAILED"
    rows = await _export_rows()
    assert [(r["status"], r["error_text"]) for r in rows] == [("failed", "telegram_http_error")]
    # The single slot is free again for the next request.
    assert (await client.get("/api/filters/regions")).status_code == 200
