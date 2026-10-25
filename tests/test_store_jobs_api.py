"""Mini App jobs/saves API over the vacancy store (``webapp/core/vacancy_store.py``).

Real app through ``httpx.ASGITransport`` (``tests/test_a3_api.py`` harness) on
the session's temp DB. Store rows are written with ``src.ingest.repo`` and
removed after each test, so other tests keep the live-osonish path. osonish
calls are stubbed; any other outbound HTTP fails the test. Synthetic data only.
"""
from __future__ import annotations

import time

import aiosqlite
import pytest

from src.functions.scraping import UpstreamError
from src.i18n import t
from src.ingest import repo
from src.ingest.base import NormalizedVacancy
from webapp.core.config import DB_PATH
from webapp.routers import jobs as jobs_router
from webapp.routers import saves as saves_router
from tests import test_a3_api
from tests.test_a3_api import HEADERS, USER_ID, _sql, _vacancy

# Shared fixtures of the A3 harness.
client = test_a3_api.client
pool_size = test_a3_api.pool_size

HOUR = 3600


def vac(source="hh", sid="900000000001", *, title="Python developer", employer="Synthetic LLC", region="1726",
        district=None, smin=5_000_000, smax=7_000_000, currency="UZS", age=HOUR, desc="Talablar: Python. " * 60,
        **kw) -> NormalizedVacancy:
    return NormalizedVacancy(
        source=source, source_id=sid, title=title, employer=employer, region_soato=region, district_soato=district,
        salary_min=smin, salary_max=smax, currency=currency, published_at=int(time.time()) - age,
        description_text=desc, url=f"https://{'hh.uz' if source == 'hh' else 'osonish.uz'}/vacancy/{sid}",
        contacts={"phones": ["+998900000000"]}, **kw,
    )


async def put(*items: NormalizedVacancy, detail: bool = False) -> None:
    async with aiosqlite.connect(str(DB_PATH)) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA busy_timeout=5000")
        if detail:
            for item in items:
                await repo.apply_detail(conn, item, int(time.time()))
        else:
            await repo.upsert_batch(conn, list(items), int(time.time()))


@pytest.fixture
async def api(client, monkeypatch):
    async def no_live(**kwargs):
        raise AssertionError("the store path must not call the live osonish search")

    monkeypatch.setattr(jobs_router, "fetch_osonish_list", no_live)
    yield client
    await _sql("DELETE FROM vacancies")
    await _sql("DELETE FROM saves WHERE user_id = ?", (USER_ID,))


async def search(api, **params):
    response = await api.get("/api/jobs/search", params=params, headers=HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------- search


async def test_search_reads_the_store_with_source_and_url(api):
    await put(vac("hh", "900000000001", title="Backend", age=HOUR),
              vac("osonish", "900000000002", title="Haydovchi", employer="Taksi", age=2 * HOUR))
    body = await search(api, lang="ru")
    assert [v["uid"] for v in body["vacancies"]] == ["hh_900000000001", "osonish_900000000002"]
    first = body["vacancies"][0]
    assert first["source"] == "hh" and first["source_label"] == "hh.uz"
    assert first["url"] == "https://hh.uz/vacancy/900000000001"
    assert first["salary_text"] == "5 000 000 – 7 000 000 сум"
    assert first["location"] == "город Ташкент"
    assert first["company"] == "Synthetic LLC"
    assert body["vacancies"][1]["source"] == "osonish"
    assert body["total_estimate"] == 2 and body["page"] == 1 and body["last_page"] == 1
    assert body["next_cursor"] is None


async def test_search_cursor_pages_without_duplicates(api):
    await put(*[vac(sid=str(900000000100 + i), title=f"Role {i}", employer=f"E{i}", age=HOUR + i) for i in range(45)])
    first = await search(api)
    assert len(first["vacancies"]) == 20 and first["total_estimate"] == 45
    assert first["last_page"] == 3 and first["next_cursor"]
    seen = [v["uid"] for v in first["vacancies"]]
    page, cursor = 1, first["next_cursor"]
    while cursor:
        page += 1
        body = await search(api, page=page, cursor=cursor)
        assert body["page"] == page and body["total_estimate"] == 45
        seen += [v["uid"] for v in body["vacancies"]]
        cursor = body["next_cursor"]
    assert len(seen) == 45 == len(set(seen))
    assert body["last_page"] == body["page"] == 3
    # Legacy page numbers (no cursor) still land on the right slice.
    legacy = await search(api, page=2)
    assert [v["uid"] for v in legacy["vacancies"]] == seen[20:40]


async def test_search_filters_map_onto_the_store(api):
    await put(
        vac(sid="900000000201", title="Python backend", region="1726", smin=8_000_000, smax=12_000_000),
        vac(sid="900000000202", title="Oshpaz", employer="Restoran", region="1718", district="1718206",
            smin=3_000_000, smax=4_000_000, desc="Taom tayyorlash. " * 60),
        vac(sid="900000000203", title="Python remote", employer="Abroad", smin=2000, smax=3000, currency="USD",
            age=5 * HOUR),
    )
    uids = lambda body: [v["uid"] for v in body["vacancies"]]  # noqa: E731
    assert sorted(uids(await search(api, q="python"))) == ["hh_900000000201", "hh_900000000203"]
    assert uids(await search(api, region_soato="1718")) == ["hh_900000000202"]
    assert uids(await search(api, district_soato="1718206")) == ["hh_900000000202"]
    assert uids(await search(api, money=5_000_000)) == ["hh_900000000201"]  # USD never passes a UZS floor
    by_salary = await search(api, sort_key="salary", sort_type="desc")
    assert uids(by_salary)[:2] == ["hh_900000000201", "hh_900000000202"]
    oldest = await search(api, sort_key="published_at", sort_type="asc")
    assert uids(oldest)[0] == "hh_900000000203"


async def test_category_filter_reads_the_store_across_sources(api):
    # ``api`` makes any live osonish call fail the test: a category no longer leaves the store.
    await put(
        vac("hh", "900000000301", title="Python developer", category_id=12, age=HOUR),
        vac("osonish", "900000000302", title="Dasturchi", category_id=12, age=2 * HOUR),
        vac("vacancy_gov", "900000000303", title="Axborot texnologiyalari mutaxassisi", category_id=12, age=3 * HOUR),
        vac("hh", "900000000304", title="Врач", category_id=47, age=HOUR),
        vac("osonish", "900000000305", title="Noma'lum", age=HOUR),
    )
    body = await search(api, specs="spec:12")
    assert [v["uid"] for v in body["vacancies"]] == [
        "hh_900000000301", "osonish_900000000302", "vacancy_gov_900000000303",
    ]
    assert body["total_estimate"] == 3
    assert [v["uid"] for v in (await search(api, specs="47"))["vacancies"]] == ["hh_900000000304"]
    # A legacy bot spec code maps onto its field id (``"22,322,323,324"`` -> 47).
    assert [v["uid"] for v in (await search(api, specs="22,322,323,324"))["vacancies"]] == ["hh_900000000304"]
    # The category combines with the other filters; no category = everything.
    assert [v["uid"] for v in (await search(api, specs="spec:12", q="dasturchi"))["vacancies"]] == ["osonish_900000000302"]
    assert (await search(api))["total_estimate"] == 5
    # An id outside the taxonomy matches nothing instead of falling back to osonish.
    assert (await search(api, specs="spec:999"))["vacancies"] == []


async def test_category_filter_on_an_empty_store_uses_the_live_search(client, monkeypatch):
    calls = []

    async def fake_list(**kwargs):
        calls.append(kwargs)
        return [_vacancy(900000000306)], 1

    monkeypatch.setattr(jobs_router, "fetch_osonish_list", fake_list)
    body = (await client.get("/api/jobs/search", params={"specs": "spec:12"}, headers=HEADERS)).json()
    assert calls and calls[0]["mmk_group_field_id"] == 12
    assert [v["uid"] for v in body["vacancies"]] == ["osonish_900000000306"]
    assert body["vacancies"][0]["url"] == "https://osonish.uz/vacancies/900000000306"


async def test_empty_store_keeps_the_live_osonish_search(client, monkeypatch):
    async def fake_list(**kwargs):
        return [_vacancy(900000000311)], 1

    monkeypatch.setattr(jobs_router, "fetch_osonish_list", fake_list)
    body = (await client.get("/api/jobs/search", headers=HEADERS)).json()
    assert [v["uid"] for v in body["vacancies"]] == ["osonish_900000000311"]


async def test_search_marks_saves_and_pro_locks_from_the_store(api):
    await put(vac("osonish", "900000000401", title="Saved", age=HOUR),
              vac("hh", "900000000402", title="Rich", employer="Bank", smin=9_000_000, smax=20_000_000, age=2 * HOUR),
              vac("hh", "900000000403", title="Rich USD", employer="Fund", smin=9000, smax=20000, currency="USD",
                  age=3 * HOUR))
    await _sql("INSERT INTO saves (user_id, save_id) VALUES (?, ?)", (USER_ID, 900000000401))
    await _sql("INSERT INTO saves (user_id, save_id) VALUES (?, ?)", (USER_ID, "hh_900000000403"))
    body = await search(api)
    by_uid = {v["uid"]: v for v in body["vacancies"]}
    assert by_uid["osonish_900000000401"]["is_saved"] is True
    assert by_uid["hh_900000000403"]["is_saved"] is True
    assert by_uid["hh_900000000402"]["is_saved"] is False
    assert by_uid["hh_900000000402"]["is_pro_locked"] is True
    assert by_uid["hh_900000000402"]["salary_text"] == "🔒 Pro"
    assert by_uid["hh_900000000403"]["is_pro_locked"] is False  # foreign currency is never compared


# ---------------------------------------------------------------- detail


async def test_hh_detail_is_an_excerpt_with_the_link_and_no_contacts(api):
    await put(vac(sid="900000000501", desc="Batafsil matn. " * 200, experience="between3And6",
                  employment="part", schedule="remote"), detail=True)
    response = await api.get("/api/jobs/hh_900000000501", params={"lang": "en"}, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()["data"]
    n = data["normalized"]
    assert data["source"] == "hh" and data["url"] == "https://hh.uz/vacancy/900000000501"
    assert len(n["description"]) <= 500
    assert n["hr_phone"] == "" and "hr" not in data and "contacts" not in data
    assert n["experience"] == t("en", "vacancy.hh.experience.between3And6")
    assert n["busyness_type"] == t("en", "vacancy.hh.employment.part")
    assert n["work_type"] == t("en", "vacancy.hh.schedule.remote")
    assert n["region"] == "Tashkent City"
    assert data["company"] == {"name": "Synthetic LLC"}


async def test_unknown_hh_uid_is_404_and_bad_uids_400(api):
    missing = await api.get("/api/jobs/hh_900000000599", headers=HEADERS)
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "NOT_FOUND"
    for bad in ("hh_abc", "zz_1", "hh_0"):
        response = await api.get(f"/api/jobs/{bad}", headers=HEADERS)
        assert response.status_code == 400 and response.json()["detail"]["code"] == "INVALID_UID", bad


async def test_checked_osonish_row_is_served_from_the_store(api, monkeypatch):
    async def no_detail(raw_id):
        raise AssertionError("a checked store row must not trigger a live detail call")

    monkeypatch.setattr(jobs_router, "get_osonish_detail", no_detail)
    raw = {"id": 900000000601, "title": "Oshpaz", "hr": {"phone": "+998900000003"}, "work_experiance": 2,
           "company": {"name": "Restoran"}, "soato_region": {"name_uz": "Toshkent shahri"}}
    await put(vac("osonish", "900000000601", title="Oshpaz", employer="Restoran", raw=raw), detail=True)
    data = (await api.get("/api/jobs/osonish_900000000601", headers=HEADERS)).json()["data"]
    assert data["hr"]["phone"] == "+998900000003"
    assert data["normalized"]["codes"]["experience"] == 2
    assert data["source"] == "osonish" and data["url"] == "https://osonish.uz/vacancy/900000000601"


async def test_unchecked_osonish_row_uses_the_live_detail_then_store_on_outage(api, monkeypatch):
    await put(vac("osonish", "900000000701", title="Kassir", employer="Market"))
    calls = []

    async def live(raw_id):
        calls.append(raw_id)
        return {"id": raw_id, "title": "Kassir (live)", "hr": {"phone": "+998900000004"}}

    monkeypatch.setattr(jobs_router, "get_osonish_detail", live)
    data = (await api.get("/api/jobs/osonish_900000000701", headers=HEADERS)).json()["data"]
    assert calls == [900000000701] and data["title"] == "Kassir (live)"
    assert data["source"] == "osonish" and data["normalized"]["source"] == "osonish"

    async def down(raw_id):
        raise UpstreamError("timeout")

    monkeypatch.setattr(jobs_router, "get_osonish_detail", down)
    await put(vac("osonish", "900000000702", title="Sotuvchi", employer="Market 2"))
    fallback = await api.get("/api/jobs/osonish_900000000702", headers=HEADERS)
    assert fallback.status_code == 200
    assert fallback.json()["data"]["normalized"]["title"] == "Sotuvchi"
    # No store row and osonish down: still the UPSTREAM_ERROR contract.
    outage = await api.get("/api/jobs/osonish_900000000703", headers=HEADERS)
    assert outage.status_code == 502 and outage.json()["detail"]["code"] == "UPSTREAM_ERROR"


# ---------------------------------------------------------------- saves


async def test_hh_save_roundtrip_next_to_an_old_osonish_save(api, monkeypatch):
    await put(vac(sid="900000000801", title="Analyst"))

    async def live(raw_id):
        return {"id": raw_id, "title": "Old osonish save"}

    monkeypatch.setattr(saves_router, "get_osonish_detail", live)
    await _sql("INSERT INTO saves (user_id, save_id) VALUES (?, ?)", (USER_ID, 900000000802))

    saved = await api.post("/api/saves/hh_900000000801", headers=HEADERS)
    assert saved.status_code == 200 and saved.json()["saved"] is True
    rows = await _sql("SELECT save_id FROM saves WHERE user_id = ? ORDER BY save_id", (USER_ID,))
    assert [r["save_id"] for r in rows] == [900000000802, "hh_900000000801"]

    listing = (await api.get("/api/saves", headers=HEADERS)).json()
    assert listing["total"] == 2
    by_uid = {i["uid"]: i for i in listing["items"]}
    assert by_uid["osonish_900000000802"]["data"]["title"] == "Old osonish save"
    assert by_uid["hh_900000000801"]["data"]["normalized"]["title"] == "Analyst"

    unknown = await api.post("/api/saves/hh_900000000899", headers=HEADERS)
    assert unknown.status_code == 400 and unknown.json()["detail"]["code"] == "INVALID_UID"

    removed = await api.delete("/api/saves/hh_900000000801", headers=HEADERS)
    assert removed.status_code == 200
    rows = await _sql("SELECT save_id FROM saves WHERE user_id = ?", (USER_ID,))
    assert [r["save_id"] for r in rows] == [900000000802]


async def test_hh_saves_count_toward_the_free_limit(api):
    await put(*[vac(sid=str(900000000900 + i), title=f"R{i}", employer=f"E{i}") for i in range(6)])
    for i in range(5):
        assert (await api.post(f"/api/saves/hh_{900000000900 + i}", headers=HEADERS)).status_code == 200
    over = await api.post("/api/saves/hh_900000000905", headers=HEADERS)
    assert over.status_code == 403 and over.json()["detail"] == {
        "code": "SAVE_LIMIT_REACHED", "limit": 5, "current": 5,
    }


# ---------------------------------------------------------------- openings


async def test_list_and_detail_carry_the_number_of_openings(api):
    await put(*(vac("osonish", str(900000000700 + i), title="Sanitarka", employer="Shifoxona") for i in range(3)),
              vac("hh", "900000000799", title="Kassir", employer="Boshqa"))
    body = await search(api)
    by_title = {v["title"]: v for v in body["vacancies"]}
    assert len(body["vacancies"]) == 2
    assert by_title["Sanitarka"]["openings"] == 3 and by_title["Kassir"]["openings"] == 1
    for uid in (by_title["Sanitarka"]["uid"], by_title["Kassir"]["uid"]):
        response = await api.get(f"/api/jobs/{uid}", headers=HEADERS)
        assert response.status_code == 200, response.text
        expected = 3 if uid.startswith("osonish_") else 1
        assert response.json()["data"]["openings"] == expected


# ---------------------------------------------------------------- vacancy_gov uids


async def test_vacancy_gov_detail_and_save_roundtrip(api):
    gov = NormalizedVacancy(
        source="vacancy_gov", source_id="900000000701", title="Inspektor", employer="Synthetic Agency",
        region_soato="1726", salary_min=4_000_000, salary_max=6_000_000, currency="UZS",
        published_at=int(time.time()) - HOUR, description_text="Talablar: yuqori malaka. " * 10,
        url="https://vacancy.example.test/900000000701",
    )
    await put(gov, detail=True)
    uid = "vacancy_gov_900000000701"

    detail = await api.get(f"/api/jobs/{uid}", headers=HEADERS)
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["normalized"]["title"] == "Inspektor"

    saved = await api.post(f"/api/saves/{uid}", headers=HEADERS)
    assert saved.status_code == 200 and saved.json()["saved"] is True
    rows = await _sql("SELECT save_id FROM saves WHERE user_id = ?", (USER_ID,))
    assert [r["save_id"] for r in rows] == [uid]
    listing = (await api.get("/api/saves", headers=HEADERS)).json()
    assert [i["uid"] for i in listing["items"]] == [uid]

    unknown = await api.post("/api/saves/vacancy_gov_900000000799", headers=HEADERS)
    assert unknown.status_code == 400 and unknown.json()["detail"]["code"] == "INVALID_UID"
    assert (await api.get("/api/jobs/vacancy_gov_900000000799", headers=HEADERS)).status_code == 404

    removed = await api.delete(f"/api/saves/{uid}", headers=HEADERS)
    assert removed.status_code == 200
    assert await _sql("SELECT save_id FROM saves WHERE user_id = ?", (USER_ID,)) == []
