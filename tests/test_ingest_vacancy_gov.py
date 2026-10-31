"""vacancy.gov.uz adapter: normalizer, regions, paging/cursor, rate limit, failure handling, runner.

No request leaves the machine: a fake transport plays the portal's JSON API.
The sample items have the exact key set of the real ``GetHRMVacancyList`` /
``GetHRMVacancyDetail`` answers (observed 2026-10-18) with synthetic content.
"""
from __future__ import annotations

from datetime import datetime

import aiohttp
import aiosqlite
import pytest

from src.core.timeutil import TZ
from src.db.connection import apply_pragmas
from src.db.migrate import run_migrations
from src.ingest import repo
from src.ingest.base import RateLimiter, SourceError
from src.ingest.runner import IngestRunner
from src.ingest.sources import vacancy_gov as vg
from src.ingest.sources.vacancy_gov import HttpResponse, VacancyGovAdapter, normalize, parse_region

NOW = 1_792_213_200  # 2026-10-17 10:00 Asia/Tashkent
DAY = 86_400


def iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%dT%H:%M:%S")


def org_full(**over):
    base = {
        "extId": 0, "region": None, "regionSoato": None, "name": None, "sphere": None, "parent": None,
        "super_parent": None, "email": None, "mail_address": None, "phone": None, "website": None,
        "contact_person": None, "all_vacancies": None, "open_vacancies": None, "applications": None,
        "order": None, "level": None, "is_active": None, "is_accepting": None, "category": None,
        "tin": None, "is_social": None, "id": 0, "active": True, "createdBy": None, "createdDate": None,
        "lastModifiedBy": None, "lastModifiedDate": None,
    }
    base.update(over)
    return base


def gov_item(i: int, start: int = NOW - 3600, **over):
    """A list item exactly shaped like the portal's (duties/requirements are null in lists)."""
    item = {
        "id": 900000 + i, "extID": 800000 + i,
        "region": "Namangan viloyati , Yangiqo‘rg‘on tumani",
        "organization": f"Synthetic tuman tibbiyot birlashmasi {i}",
        "structure_name": "Ko`p tarmoqli markaziy poliklinika ",
        "position_name": f"Vrach terapevt {i}", "position_salary": 3_265_185,
        "position_requirements": None, "testTypeCode": None, "position_duties": None,
        "position_conditions": None, "position_mark_surcharge": None, "position_type": None,
        "position_rate": 1.0, "views_count": 12, "likesCount": 0, "get_candidates_count": 1,
        "date_start": iso(start), "date_stop": iso(start + 9 * DAY) , "created": iso(start - 30 * DAY),
        "is_internal": 0, "academic_Title_Or_Degree": None, "is_published": True, "is_liked": False,
        "is_disablity": False, "is_small_employee": None, "is35yearsOld": False, "tin": "200000000",
        "org_ext_id": None, "education_Level_Id": None, "experience": 0, "leader_experience": None,
        "is_dfx": True, "process": None, "organizationFull": org_full(),
    }
    item.update(over)
    return item


def gov_detail(i: int, start: int = NOW - 3600, **over):
    return gov_item(
        i, start,
        position_duties="<p>Bemorlarni qabul qilish &amp; davolash</p><script>alert(1)</script>",
        position_requirements="Oliy ma’lumot, 3 yil tajriba",
        position_conditions="haftasiga 5 kunlik ish kuni",
        position_mark_surcharge="Vrach ", testTypeCode=1226, education_Level_Id=17, experience=3,
        organizationFull=org_full(mail_address="Namangan viloyati, Yangiqo‘rg‘on tumani, 4-uy",
                                  phone="+998690000000", email="hr@example.test", id=22146),
        **over,
    )


class FakePortal:
    """Plays the portal: list ordered by date_start desc (page size capped at 40), details, scripted answers."""

    def __init__(self, items=None):
        self.items = {it["id"]: it for it in (items or [])}
        self.details: dict[int, dict] = {}
        self.calls: list[tuple[str, str, dict, dict | None, dict]] = []
        self.script: list = []  # HttpResponse or Exception, consumed first

    async def __call__(self, method, url, params, json_body, headers):
        self.calls.append((method, url, dict(params), json_body, dict(headers)))
        if self.script:
            nxt = self.script.pop(0)
            if isinstance(nxt, Exception):
                raise nxt
            return nxt
        if url.endswith(vg.LIST_PATH):
            size = min(int(json_body["pageSize"]), 40)
            rows = sorted(self.items.values(), key=lambda r: (r["date_start"], r["id"]), reverse=True)
            page = int(json_body["page"])
            return HttpResponse(200, {"count": len(rows), "next": None, "previous": None,
                                      "results": rows[page * size:(page + 1) * size]}, {})
        if url.endswith(vg.DETAIL_PATH):
            found = self.details.get(int(params["id"]))
            if found is None:
                return HttpResponse(404, {"statusCode": 404, "message": "Vacancy not found", "error": 404}, {})
            return HttpResponse(200, found, {})
        return HttpResponse(404, None, {})

    @property
    def list_calls(self):
        return [c for c in self.calls if c[1].endswith(vg.LIST_PATH)]


async def _no_sleep(_s):
    return None


def make_adapter(portal, sleeps=None, **kw):
    async def sleep(s):
        if sleeps is not None:
            sleeps.append(s)

    kw.setdefault("rate", RateLimiter(0, sleep=_no_sleep))
    kw.setdefault("clock", lambda: NOW)
    return VacancyGovAdapter(transport=portal, sleep=sleep, user_agent="BandlikUZ-tests/1.0", **kw)


async def collect(adapter, cursor, now=NOW):
    batches = []
    async for b in adapter.iter_new(cursor, now):
        batches.append(b)
    return batches


# ---------------------------------------------------------------- regions


@pytest.mark.parametrize(
    "raw,soato",
    [
        ("Namangan viloyati , Yangiqo‘rg‘on tumani", "1714"),
        ("Toshkent shahri  , Mirobod tumani", "1726"),
        ("Toshkent shahri , Bektemir tumani", "1726"),
        ("Toshkent viloyati , Angren shahri", "1727"),
        ("Farg‘ona viloyati , Marg‘ilon shahri", "1730"),
        ("Qoraqalpog‘iston Respublikasi , Nukus shahri", "1735"),
        ("Surxondaryo viloyati , Termiz shahri", "1722"),
        ("Jizzax viloyati , Mirzacho‘l tumani", "1708"),
        ("Samarqand viloyati", "1718"),
        ("Тошкент шаҳри , Чилонзор тумани", "1726"),
        ("Тошкент вилояти , Олмалиқ шаҳри", "1727"),
        ("Самарқанд вилояти", "1718"),
        ("Atlantis viloyati", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_region(raw, soato):
    assert parse_region(raw)[0] == soato


def test_parse_region_keeps_district_in_display_name_and_falls_back_to_table_names():
    assert parse_region("Namangan viloyati , Yangiqo‘rg‘on tumani")[1] == "Namangan viloyati, Yangiqo‘rg‘on tumani"
    # An unknown spelling resolves through the regions-table map the runner injects.
    assert parse_region("Yangi viloyat", {"yangi viloyat": "1706"})[0] == "1706"
    assert parse_region("Yangi viloyat", {"yangi viloyat": "9999"})[0] is None


# ---------------------------------------------------------------- normalize


def test_normalize_list_item():
    v = normalize(gov_item(1), NOW)
    assert v.uid == "vacancy_gov_900001" and v.source == "vacancy_gov"
    assert v.title == "Vrach terapevt 1" and v.employer == "Synthetic tuman tibbiyot birlashmasi 1"
    assert (v.salary_min, v.salary_max, v.currency) == (3_265_185, None, "UZS")
    assert v.region_soato == "1714" and "Yangiqo‘rg‘on" in v.region_name
    assert v.published_at == NOW - 3600
    assert v.url == "https://vacancy.gov.uz/hrm-vacancy-detail/900001"
    assert v.is_open and v.contacts == {} and v.experience == ""
    assert v.description_text == "Tuzilma: Ko`p tarmoqli markaziy poliklinika"


def test_normalize_zero_salary_means_no_salary():
    v = normalize(gov_item(2, position_salary=0), NOW)
    assert (v.salary_min, v.salary_max, v.currency) == (None, None, None)
    assert normalize(gov_item(3, position_salary=None), NOW).salary_min is None


def test_normalize_detail_sanitizes_and_collects_institution_contacts_only():
    v = normalize(gov_detail(4), NOW, detail=True)
    assert "<" not in v.description_text and "alert(1)" not in v.description_text
    assert "Vazifalar: Bemorlarni qabul qilish & davolash" in v.description_text
    assert "Talablar: Oliy ma’lumot, 3 yil tajriba" in v.description_text
    assert v.schedule == "haftasiga 5 kunlik ish kuni" and v.experience == "3"
    assert v.contacts == {
        "phones": ["+998690000000"], "email": "hr@example.test",
        "address": "Namangan viloyati, Yangiqo‘rg‘on tumani, 4-uy",
    }
    # Contacts never ride along on list items.
    assert normalize(gov_detail(4), NOW).contacts == {}


def test_normalize_strips_markup_from_title_and_employer():
    v = normalize(gov_item(5, position_name="<b>Hamshira</b><img src=x onerror=alert(1)>", organization="<i>Poliklinika</i>"), NOW)
    assert v.title == "Hamshira" and v.employer == "Poliklinika"


def test_normalize_open_state_follows_window_and_publication_flag():
    assert normalize(gov_item(6), NOW).is_open
    expired = gov_item(7, NOW - 12 * DAY)  # date_stop = start + 9 days = 3 days ago
    assert normalize(expired, NOW).is_open is False
    assert normalize(gov_item(8, is_published=False), NOW).is_open is False
    # No date_stop at all: nothing says it closed.
    assert normalize(gov_item(9, date_stop=None), NOW).is_open is True


def test_normalize_rejects_unusable_items():
    assert normalize(None, NOW) is None
    assert normalize("x", NOW) is None
    assert normalize(gov_item(10, id="12"), NOW) is None
    assert normalize(gov_item(10, id=True), NOW) is None
    assert normalize(gov_item(10, id=0), NOW) is None
    assert normalize(gov_item(10, position_name="  "), NOW) is None
    assert normalize(gov_item(10, date_start="soon", created="never"), NOW) is None
    # date_start missing falls back to created.
    v = normalize(gov_item(11, date_start=None), NOW)
    assert v.published_at == NOW - 3600 - 30 * DAY


def test_parse_cursor():
    assert vg.parse_cursor("100:200") == (100, 200)
    for bad in (None, "", "100", "a:b", "100:", ":5", "1:2:3x"):
        assert vg.parse_cursor(bad) == (None, None)


# ---------------------------------------------------------------- paging and cursor


async def test_first_run_walks_every_page_and_saves_cursor_with_sweep_time():
    portal = FakePortal([gov_item(i, NOW - i * 60) for i in range(95)])  # 3 pages of 40
    adapter = make_adapter(portal)
    batches = await collect(adapter, None)
    assert [len(b.items) for b in batches] == [40, 40, 15]
    assert [b.cursor for b in batches] == [None, None, f"{NOW}:{NOW}"]
    assert all(c[3] == {"page": p, "pageSize": 40} for p, c in enumerate(portal.list_calls))
    assert len(portal.list_calls) == 3 and adapter.stats["requests"] == 3 and adapter.stats["items"] == 95


async def test_incremental_run_stops_at_the_first_page_older_than_cursor_minus_overlap():
    fresh = [gov_item(i, NOW - 600 - i) for i in range(10)]
    old = [gov_item(100 + i, NOW - 5 * DAY - i) for i in range(200)]  # 5 pages worth of old windows
    portal = FakePortal(fresh + old)
    adapter = make_adapter(portal)
    cursor = f"{NOW - 600 - 20}:{NOW - 3600}"  # swept an hour ago -> no full sweep due
    batches = await collect(adapter, cursor)
    # page 0 = 10 fresh + 30 old (mixed, kept), page 1 is wholly older than cursor - 1 day -> stop.
    assert len(portal.list_calls) == 2
    assert [len(b.items) for b in batches] == [40, 40]
    assert batches[0].cursor is None and batches[1].cursor == f"{NOW - 600}:{NOW - 3600}"


async def test_overlap_keeps_walking_through_items_just_behind_the_cursor():
    # 40 items at the cursor day, then 40 that started 12 h earlier (inside the 1-day overlap), then old ones.
    head = [gov_item(i, NOW - 600 - i) for i in range(40)]
    inside = [gov_item(100 + i, NOW - 600 - 12 * 3600 - i) for i in range(40)]
    old = [gov_item(200 + i, NOW - 6 * DAY - i) for i in range(40)]
    portal = FakePortal(head + inside + old)
    batches = await collect(make_adapter(portal), f"{NOW - 600}:{NOW - 3600}")
    assert len(portal.list_calls) == 3 and batches[-1].cursor == f"{NOW - 600}:{NOW - 3600}"


async def test_full_sweep_is_repeated_once_a_day_even_with_a_cursor():
    portal = FakePortal([gov_item(i, NOW - i * 60 - (0 if i < 10 else 5 * DAY)) for i in range(120)])
    adapter = make_adapter(portal)
    stale_cursor = f"{NOW - 600}:{NOW - DAY - 1}"
    batches = await collect(adapter, stale_cursor)
    assert len(portal.list_calls) == 3  # whole list, not just the fresh head
    assert batches[-1].cursor == f"{NOW - 0}:{NOW}"
    portal2 = FakePortal([gov_item(i, NOW - i * 60 - (0 if i < 10 else 5 * DAY)) for i in range(120)])
    await collect(make_adapter(portal2), f"{NOW - 600}:{NOW - DAY + 60}")
    assert len(portal2.list_calls) == 2  # not due: stops after the first old page


async def test_garbage_cursor_means_full_sweep_and_empty_portal_saves_nothing():
    portal = FakePortal([gov_item(i, NOW - i) for i in range(45)])
    batches = await collect(make_adapter(portal), "not-a-cursor")
    assert len(portal.list_calls) == 2 and batches[-1].cursor is not None
    empty = FakePortal([])
    batches = await collect(make_adapter(empty), None)
    assert [(len(b.items), b.cursor) for b in batches] == [(0, None)]


async def test_page_cap_stops_the_run_and_does_not_advance_the_cursor():
    portal = FakePortal([gov_item(i, NOW - i) for i in range(200)])
    batches = await collect(make_adapter(portal, max_pages=2), None)
    assert len(portal.list_calls) == 2
    assert all(b.cursor is None for b in batches)


async def test_duplicates_across_shifting_pages_and_junk_items_are_dropped():
    items = [gov_item(i, NOW - i) for i in range(5)]
    portal = FakePortal(items)
    junk = {"id": "nope", "position_name": "x"}
    portal.script = [HttpResponse(200, {"count": 100, "results": [items[0], junk, items[0], items[1]]}, {}),
                     HttpResponse(200, {"count": 100, "results": [items[1], items[2]]}, {}),
                     HttpResponse(200, {"count": 100, "results": []}, {})]
    batches = await collect(make_adapter(portal), None)
    assert [[v.source_id for v in b.items] for b in batches] == [["900000", "900001"], ["900002"], []]


# ---------------------------------------------------------------- detail


async def test_fetch_detail_posts_without_counting_a_view_and_normalizes():
    portal = FakePortal()
    portal.details[900004] = gov_detail(4)
    adapter = make_adapter(portal)
    v = await adapter.fetch_detail("900004")
    assert v.uid == "vacancy_gov_900004" and "Talablar:" in v.description_text and v.contacts["phones"]
    method, url, params, body, headers = portal.calls[0]
    assert method == "POST" and url == vg.BASE_URL + vg.DETAIL_PATH
    assert params == {"id": "900004", "isView": "false"} and body is None
    assert headers["User-Agent"] == "BandlikUZ-tests/1.0" and headers["Accept"] == "application/json"


async def test_fetch_detail_unknown_is_none_and_expired_is_closed():
    portal = FakePortal()
    portal.details[900007] = gov_detail(7, NOW - 12 * DAY)
    adapter = make_adapter(portal)
    assert await adapter.fetch_detail("12345") is None  # portal answers 404
    assert await adapter.fetch_detail("../x") is None and len(portal.calls) == 1  # never sent
    assert (await adapter.fetch_detail("900007")).is_open is False


async def test_unreadable_detail_is_an_error_not_a_vanished_vacancy():
    portal = FakePortal()
    portal.details[900001] = {"id": 900001, "position_name": ""}
    portal.details[900002] = gov_detail(3)  # answers for another id
    adapter = make_adapter(portal)
    with pytest.raises(SourceError) as exc:
        await adapter.fetch_detail("900001")
    assert exc.value.reason == "invalid_payload"
    with pytest.raises(SourceError):
        await adapter.fetch_detail("900002")


# ---------------------------------------------------------------- rate limit and failures


async def test_requests_are_spaced_one_second_apart():
    clock = {"t": 100.0}
    waits: list[float] = []

    async def fake_sleep(s):
        waits.append(round(s, 3))
        clock["t"] += s

    portal = FakePortal([gov_item(i, NOW - i) for i in range(95)])
    adapter = make_adapter(portal, rate=RateLimiter(1.0, clock=lambda: clock["t"], sleep=fake_sleep))
    await collect(adapter, None)
    assert len(portal.list_calls) == 3
    assert waits == [1.0, 1.0]  # first call immediate, then one second between consecutive requests


async def test_default_rate_limiter_is_one_request_per_second():
    assert VacancyGovAdapter(transport=FakePortal()).rate.interval == 1.0


async def test_retries_5xx_and_429_with_backoff_then_succeeds():
    portal = FakePortal([gov_item(1)])
    portal.script = [HttpResponse(503, None, {}), HttpResponse(429, None, {"Retry-After": "7"}),
                     aiohttp.ClientConnectionError("reset")]
    sleeps: list[float] = []
    adapter = make_adapter(portal, sleeps)
    batches = await collect(adapter, None)
    assert [len(b.items) for b in batches] == [1]
    assert sleeps == [1.0, 7.0, 4.0]  # 2**0 backoff, Retry-After wins, 2**2 for the third attempt
    assert adapter.stats["retries"] == 3 and adapter.stats["requests"] == 4 and adapter.stats["errors"] == 0


async def test_retries_exhausted_raises_source_error():
    portal = FakePortal()
    portal.script = [HttpResponse(502, None, {})] * 4
    adapter = make_adapter(portal, max_retries=3)
    with pytest.raises(SourceError) as exc:
        await collect(adapter, None)
    assert exc.value.reason == "server_error_retries_exhausted" and exc.value.status == 502
    assert adapter.stats["requests"] == 4 and adapter.stats["errors"] == 1


async def test_forbidden_fails_fast_without_retry():
    portal = FakePortal()
    portal.script = [HttpResponse(403, "<html>blocked</html>", {})]
    adapter = make_adapter(portal)
    with pytest.raises(SourceError) as exc:
        await collect(adapter, None)
    assert (exc.value.reason, exc.value.status) == ("forbidden", 403)
    assert adapter.stats["requests"] == 1 and adapter.stats["retries"] == 0


@pytest.mark.parametrize(
    "answer",
    [
        HttpResponse(200, None, {}),  # HTML instead of JSON: transport yields body None
        HttpResponse(200, [], {}),
        HttpResponse(200, {"data": []}, {}),  # renamed key
        HttpResponse(200, {"count": "many", "results": []}, {}),
        HttpResponse(200, {"count": 5, "results": "oops"}, {}),
        HttpResponse(400, {"message": "bad"}, {}),
    ],
)
async def test_changed_or_broken_payload_is_a_clean_source_error(answer):
    portal = FakePortal()
    portal.script = [answer]
    adapter = make_adapter(portal)
    with pytest.raises(SourceError):
        await collect(adapter, None)
    assert adapter.stats["errors"] == 1


async def test_error_mid_run_keeps_the_pages_already_yielded():
    portal = FakePortal([gov_item(i, NOW - i) for i in range(95)])
    adapter = make_adapter(portal)
    got = []
    first_page = await portal("POST", vg.BASE_URL + vg.LIST_PATH, {}, {"page": 0, "pageSize": 40}, {})
    portal.calls.clear()
    portal.script = [first_page, HttpResponse(403, None, {})]
    with pytest.raises(SourceError):
        async for b in adapter.iter_new(None, NOW):
            got.append(b)
    assert len(got) == 1 and len(got[0].items) == 40 and got[0].cursor is None


async def test_breaker_pauses_the_source_after_repeated_failures_and_recovers():
    now = {"t": float(NOW)}
    portal = FakePortal()
    portal.script = [HttpResponse(403, None, {})] * 3
    adapter = make_adapter(portal, clock=lambda: now["t"])
    assert adapter.enabled()
    for _ in range(2):
        with pytest.raises(SourceError):
            await collect(adapter, None)
        assert adapter.enabled()
    with pytest.raises(SourceError):
        await collect(adapter, None)
    assert not adapter.enabled()  # third consecutive failure: paused
    now["t"] += vg.BREAKER_PAUSE_SECONDS - 1
    assert not adapter.enabled()
    now["t"] += 2
    assert adapter.enabled()


async def test_a_success_resets_the_failure_streak():
    portal = FakePortal([gov_item(1)])
    adapter = make_adapter(portal)
    for _ in range(2):
        portal.script = [HttpResponse(403, None, {})]
        with pytest.raises(SourceError):
            await collect(adapter, None)
    await collect(adapter, None)  # healthy run
    for _ in range(2):
        portal.script = [HttpResponse(403, None, {})]
        with pytest.raises(SourceError):
            await collect(adapter, None)
    assert adapter.enabled()  # 2 + 2 failures never reached 3 in a row


def test_env_switch_disables_the_source(monkeypatch):
    monkeypatch.setenv("VACANCY_GOV_ENABLED", "0")
    assert VacancyGovAdapter(transport=FakePortal()).enabled() is False
    monkeypatch.setenv("VACANCY_GOV_ENABLED", "1")
    assert VacancyGovAdapter(transport=FakePortal()).enabled() is True
    monkeypatch.delenv("VACANCY_GOV_ENABLED")
    assert VacancyGovAdapter(transport=FakePortal()).enabled() is True


def test_adapter_protocol_attributes():
    a = VacancyGovAdapter(transport=FakePortal())
    assert a.name == "vacancy_gov" and 600 <= a.interval_seconds <= 1800
    assert a.recheck_per_run > 0 and a.stale_after_seconds >= 14 * DAY
    assert set(a.stats) >= {"requests", "errors", "retries", "items"}


# ---------------------------------------------------------------- runner end to end


@pytest.fixture
async def conn(tmp_path):
    async with aiosqlite.connect(tmp_path / "ingest.sqlite3") as c:
        await apply_pragmas(c)
        await run_migrations(c)
        yield c


async def test_runner_end_to_end_list_detail_search_and_expiry(conn):
    items = [gov_item(1, NOW - 600), gov_item(2, NOW - 700, region="Toshkent shahri , Mirobod tumani"),
             gov_item(3, NOW - 800)]
    portal = FakePortal(items)
    portal.details[900001] = gov_detail(1, NOW - 600)
    portal.details[900002] = gov_detail(2, NOW - 700, region="Toshkent shahri , Mirobod tumani")
    # 900003 vanished from the portal (404), nothing else to say about it.
    adapter = make_adapter(portal)
    runner = IngestRunner([adapter], clock=lambda: NOW)
    result = await runner.run_once(conn)
    stats = result["vacancy_gov"]
    assert stats["new"] == 3 and stats["checked"] == 2 and stats["closed"] == 1
    found = await repo.search(conn, region_soato="1726")
    assert [i["uid"] for i in found["items"]] == ["vacancy_gov_900002"]
    row = await repo.get(conn, "vacancy_gov_900001")
    assert "Talablar: Oliy ma’lumot" in row["description_text"] and row["status"] == "open"
    assert (await repo.get(conn, "vacancy_gov_900003"))["status"] == "closed"
    cursor = (await repo.get_cursor(conn, "vacancy_gov"))["cursor"]
    assert cursor == f"{NOW - 600}:{NOW}"

    # Next run (cursor present, sweep not due): the portal now says 900001 expired.
    portal.details[900001] = gov_detail(1, NOW - 12 * DAY)
    runner.clock = lambda: NOW + 1900
    portal.calls.clear()
    await runner.run_once(conn)
    assert (await repo.get(conn, "vacancy_gov_900001"))["status"] == "closed"
    assert all(c[3] == {"page": 0, "pageSize": 40} for c in portal.list_calls)


async def test_runner_records_a_blocked_portal_and_never_crashes(conn):
    portal = FakePortal()
    portal.script = [HttpResponse(403, "<html>forbidden</html>", {})]
    adapter = make_adapter(portal)
    result = await IngestRunner([adapter], clock=lambda: NOW).run_once(conn)
    assert result["vacancy_gov"]["failed"] == 1 and "forbidden" in result["vacancy_gov"]["error"]
    state = await repo.get_cursor(conn, "vacancy_gov")
    assert "forbidden" in (state["last_error"] or "")


async def test_runner_skips_a_paused_source(conn):
    adapter = make_adapter(FakePortal(), enabled=False)
    assert await IngestRunner([adapter], clock=lambda: NOW).run_once(conn) == {}
