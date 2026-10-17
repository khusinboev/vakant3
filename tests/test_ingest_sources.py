"""Ingestion sources: hh client/normalizer/windowing, osonish adapter, text and region helpers.

No request leaves the machine: hh goes through a fake transport, osonish
through a local aiohttp server (``OSONISH_BASE`` points at it) or stub fetchers.
"""
from __future__ import annotations

import asyncio

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from src.functions import scraping
from src.ingest.base import RateLimiter, SourceError, parse_ts
from src.ingest.regions import hh_area_to_region, osonish_region
from src.ingest.sources import hh as hh_mod
from src.ingest.sources import osonish as os_mod
from src.ingest.sources.hh import HHAdapter, HHClient, HttpResponse
from src.ingest.sources.osonish import OsonishAdapter
from src.ingest.text import clean_line, excerpt, html_to_text

NOW = 1_792_213_200  # 2026-10-17 10:00 Asia/Tashkent


# ---------------------------------------------------------------- helpers


class FakeHH:
    """Stands in for api.hh.ru: a list of vacancies filtered by date window, 2000-result cap like hh."""

    def __init__(self, vacancies=None):
        self.vacancies = vacancies or []
        self.calls: list[tuple[str, dict, dict]] = []
        self.script: list[HttpResponse] = []  # forced answers, consumed first
        self.details: dict[str, HttpResponse] = {}

    async def __call__(self, url, params, headers):
        self.calls.append((url, dict(params), dict(headers)))
        if self.script:
            return self.script.pop(0)
        path = url.removeprefix(hh_mod.HH_BASE)
        if path.startswith("/vacancies/"):
            return self.details.get(path.rsplit("/", 1)[1], HttpResponse(404, {"errors": []}, {}))
        lo, hi = parse_ts(params["date_from"]), parse_ts(params["date_to"])
        rows = sorted((v for v in self.vacancies if lo <= v["_ts"] <= hi), key=lambda v: -v["_ts"])
        page, per_page = int(params["page"]), int(params["per_page"])
        if (page + 1) * per_page > 2000:
            return HttpResponse(400, {"errors": [{"type": "bad_argument"}]}, {})
        reachable = rows[:2000]
        items = [{k: v for k, v in r.items() if k != "_ts"} for r in reachable[page * per_page:(page + 1) * per_page]]
        pages = (len(reachable) + per_page - 1) // per_page
        return HttpResponse(200, {"items": items, "found": len(rows), "pages": pages, "page": page}, {})


def hh_item(i: int, ts: int, **over):
    from datetime import datetime

    from src.core.timeutil import TZ

    item = {
        "id": str(100000 + i),
        "name": f"Developer {i}",
        "salary": {"from": 5_000_000, "to": 9_000_000, "currency": "UZS", "gross": False},
        "area": {"id": "2759", "name": "Ташкент"},
        "employer": {"id": "1", "name": "Synthetic LLC"},
        "published_at": datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%dT%H:%M:%S%z"),
        "alternate_url": f"https://hh.uz/vacancy/{100000 + i}",
        "snippet": {"requirement": "<highlighttext>Python</highlighttext> 3 years", "responsibility": "Build APIs"},
        "schedule": {"id": "remote", "name": "Удаленная работа"},
        "employment": {"id": "full", "name": "Полная занятость"},
        "experience": {"id": "between1And3", "name": "От 1 года до 3 лет"},
        "archived": False,
        "_ts": ts,
    }
    item.update(over)
    return item


async def _no_sleep(_s):
    return None


def make_client(fake, sleeps=None, **kw):
    async def sleep(s):
        if sleeps is not None:
            sleeps.append(s)

    return HHClient("synthetic-token", "BandlikUZ-tests/1.0", transport=fake,
                    rate=RateLimiter(0, sleep=_no_sleep), sleep=sleep, **kw)


async def collect(adapter, cursor, now):
    batches = []
    async for b in adapter.iter_new(cursor, now):
        batches.append(b)
    return batches


# ---------------------------------------------------------------- text


def test_html_to_text_drops_markup_scripts_and_keeps_structure():
    html = (
        "<p>Talablar:</p><ul><li>Python &amp; SQL</li><li>Ingliz tili</li></ul>"
        "<script>alert('x')</script><style>p{}</style><b onclick=\"evil()\">Bonus</b>"
        "<img src=x onerror=alert(1)>&lt;script&gt;alert(2)&lt;/script&gt;​"
    )
    text = html_to_text(html)
    assert "<" not in text and ">" not in text
    assert "alert('x')" not in text and "onclick" not in text and "onerror" not in text
    assert "• Python & SQL" in text and "• Ingliz tili" in text and "Bonus" in text
    assert "​" not in text


def test_html_to_text_handles_non_strings_and_truncates():
    assert html_to_text(None) == "" and html_to_text(123) == ""
    long = "<p>" + "so'z " * 1000 + "</p>"
    out = html_to_text(long, max_len=100)
    assert len(out) <= 100 and out.endswith("…")
    assert clean_line("Line one\n<br>line two") == "Line one line two"
    assert excerpt("a\n\nb   c", 10) == "a b c"


# ---------------------------------------------------------------- regions


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Ташкент", "1726"),
        ("Чирчик", "1727"),
        ("Самарканд", "1718"),
        ("Нукус", "1735"),
        ("Фергана", "1730"),
        ("Коканд", "1730"),
        ("Термез", "1722"),
        ("Ургенч", "1733"),
        ("г. Навои", "1712"),
        ("Самаркандская область", "1718"),
        ("Каршинский район (Кашкадарьинская обл.)", "1710"),
        ("Москва", None),
    ],
)
def test_hh_city_to_region(name, expected):
    assert hh_area_to_region({"id": "1", "name": name}) == expected


def test_hh_area_garbage_is_unknown():
    assert hh_area_to_region(None) is None
    assert hh_area_to_region({"name": ""}) is None


def test_osonish_region_codes_and_name_fallback():
    assert osonish_region({"soato_region": {"soato": 1726, "name_uz": "Toshkent shahri"},
                           "soato_district": {"soato": "1726266"}}) == ("1726", "1726266", "Toshkent shahri")
    # Only a district code: the region is its prefix.
    assert osonish_region({"soato_district": {"soato": "1703202"}})[0] == "1703"
    # No codes at all: name lookup in the regions table map.
    assert osonish_region({"soato_region": {"name_uz": "Buxoro viloyati"}}, {"buxoro viloyati": "1706"})[0] == "1706"
    # Codes outside Uzbekistan's SOATO are rejected.
    assert osonish_region({"soato_region": {"soato": "9999"}}) == (None, None, "")


# ---------------------------------------------------------------- hh normalizer


def test_hh_normalize_list_item():
    v = hh_mod.normalize(hh_item(1, NOW))
    assert v.uid == "hh_100001" and v.source == "hh"
    assert (v.salary_min, v.salary_max, v.currency, v.salary_gross) == (5_000_000, 9_000_000, "UZS", False)
    assert v.region_soato == "1726" and v.region_name == "Ташкент"
    assert v.published_at == NOW
    assert (v.experience, v.employment, v.schedule) == ("between1And3", "full", "remote")
    assert "<" not in v.description_text and "Python 3 years" in v.description_text
    assert v.url == "https://hh.uz/vacancy/100001" and v.is_open
    assert v.contacts == {}


def test_hh_normalize_salary_variants_and_archived():
    v = hh_mod.normalize(hh_item(2, NOW, salary={"from": None, "to": 1500, "currency": "USD", "gross": True},
                                 archived=True))
    assert (v.salary_min, v.salary_max, v.currency, v.salary_gross) == (None, 1500, "USD", True)
    assert v.is_open is False
    v = hh_mod.normalize(hh_item(3, NOW, salary=None))
    assert (v.salary_min, v.salary_max, v.currency) == (None, None, None)
    v = hh_mod.normalize(hh_item(4, NOW, salary={"from": 100, "currency": "RUR"}))
    assert v.currency == "RUB"


def test_hh_normalize_rejects_unusable_and_unsafe_links():
    assert hh_mod.normalize(hh_item(5, NOW, id="../../etc")) is None
    assert hh_mod.normalize(hh_item(6, NOW, published_at="soon")) is None
    assert hh_mod.normalize(hh_item(7, NOW, name="")) is None
    v = hh_mod.normalize(hh_item(8, NOW, alternate_url="javascript:alert(1)"))
    assert v.url == "https://hh.uz/vacancy/100008"
    v = hh_mod.normalize(hh_item(9, NOW, alternate_url="https://hh.uz.evil.example/vacancy/1"))
    assert v.url == "https://hh.uz/vacancy/100009"


def test_hh_normalize_detail_sanitizes_description_and_reads_skills_contacts():
    detail = hh_item(10, NOW, description="<p>Hello <b>world</b></p><script>steal()</script>",
                     key_skills=[{"name": "Python"}, {"name": "<i>SQL</i>"}],
                     contacts={"name": "HR", "email": "hr@example.test",
                               "phones": [{"country": "998", "city": "90", "number": "0000000"}]},
                     professional_roles=[{"id": "96", "name": "Программист, разработчик"}])
    v = hh_mod.normalize(detail, detail=True)
    assert v.description_text == "Hello world"
    assert v.skills == ["Python", "SQL"]
    assert v.contacts == {"name": "HR", "email": "hr@example.test", "phones": ["998900000000"]}
    assert v.category == "Программист, разработчик"


# ---------------------------------------------------------------- hh client


async def test_hh_client_sends_host_token_and_user_agent():
    fake = FakeHH([hh_item(1, NOW - 60)])
    client = make_client(fake)
    await client.search(NOW - 3600, NOW, 0)
    url, params, headers = fake.calls[0]
    assert url == "https://api.hh.ru/vacancies"
    assert params["host"] == "hh.uz" and params["area"] == "97" and params["per_page"] == 100
    assert params["order_by"] == "publication_time"
    assert headers["Authorization"] == "Bearer synthetic-token"
    assert headers["User-Agent"] == "BandlikUZ-tests/1.0"


async def test_hh_client_backs_off_on_429_then_succeeds():
    fake = FakeHH([hh_item(1, NOW - 60)])
    fake.script = [HttpResponse(429, None, {}), HttpResponse(429, None, {}), HttpResponse(503, None, {})]
    sleeps: list[float] = []
    client = make_client(fake, sleeps, base_delay=1.0)
    body = await client.search(NOW - 3600, NOW, 0)
    assert len(body["items"]) == 1
    assert sleeps == [1.0, 2.0, 4.0]  # exponential
    assert client.stats["requests"] == 4 and client.stats["retries"] == 3 and client.stats["errors"] == 0


async def test_hh_client_respects_retry_after_and_gives_up():
    fake = FakeHH()
    fake.script = [HttpResponse(429, None, {"Retry-After": "7"})] * 3
    sleeps: list[float] = []
    client = make_client(fake, sleeps, max_retries=2)
    with pytest.raises(SourceError) as err:
        await client.search(NOW - 3600, NOW, 0)
    assert err.value.status == 429 and "retries_exhausted" in err.value.reason
    assert sleeps == [7.0, 7.0]
    assert client.stats["errors"] == 1


@pytest.mark.parametrize("status,reason", [(403, "forbidden"), (401, "forbidden"), (400, "bad_request")])
async def test_hh_client_fails_fast_on_auth_and_bad_request(status, reason):
    fake = FakeHH()
    fake.script = [HttpResponse(status, {"errors": [{"type": "forbidden"}]}, {})]
    sleeps: list[float] = []
    client = make_client(fake, sleeps)
    with pytest.raises(SourceError) as err:
        await client.search(NOW - 3600, NOW, 0)
    assert err.value.reason == reason and sleeps == [] and len(fake.calls) == 1


async def test_hh_client_404_detail_is_none_and_transport_errors_retry():
    fake = FakeHH()
    client = make_client(fake)
    assert await client.vacancy("123") is None

    calls = {"n": 0}

    async def flaky(url, params, headers):
        calls["n"] += 1
        if calls["n"] == 1:
            raise asyncio.TimeoutError()
        return HttpResponse(200, {"id": "1"}, {})

    client = make_client(flaky)
    assert await client.vacancy("1") == {"id": "1"}
    assert client.stats["retries"] == 1


async def test_rate_limiter_spaces_requests():
    clock = {"t": 0.0}
    slept: list[float] = []

    async def sleep(s):
        slept.append(round(s, 3))
        clock["t"] += s

    rl = RateLimiter(2.0, clock=lambda: clock["t"], sleep=sleep)
    for _ in range(3):
        await rl.wait()
    assert slept == [0.5, 0.5]


# ---------------------------------------------------------------- hh adapter


def test_hh_disabled_without_token():
    assert HHAdapter(token="").enabled() is False
    assert HHAdapter().enabled() is False  # conftest forces HH_APP_TOKEN=""
    assert HHAdapter(token="x", client=make_client(FakeHH())).enabled() is True


async def test_hh_adapter_pages_through_a_window_and_sets_cursor():
    fake = FakeHH([hh_item(i, NOW - 60 * i) for i in range(1, 251)])
    adapter = HHAdapter(token="t", client=make_client(fake))
    batches = await collect(adapter, str(NOW - 86_400), NOW)
    uids = [v.uid for b in batches for v in b.items]
    assert len(uids) == 250 and len(set(uids)) == 250
    assert [b.cursor for b in batches] == [None, None, str(NOW)]  # 3 pages, cursor only when complete
    assert [c[1]["page"] for c in fake.calls] == [0, 1, 2]


async def test_hh_adapter_splits_windows_over_2000_results():
    # 2500 vacancies in the last 2 days: one query cannot reach them all.
    fake = FakeHH([hh_item(i, NOW - 60 * i) for i in range(1, 2501)])
    adapter = HHAdapter(token="t", client=make_client(fake), max_requests_per_run=1000)
    batches = await collect(adapter, str(NOW - 2 * 86_400), NOW)
    uids = {v.uid for b in batches for v in b.items}
    assert len(uids) == 2500
    assert all(c[1]["page"] < 20 for c in fake.calls)
    # Every sub-window that was paged had <= 2000 results; the cursor never moves backwards.
    cursors = [int(b.cursor) for b in batches if b.cursor]
    assert cursors == sorted(cursors) and cursors[-1] == NOW


async def test_hh_adapter_incremental_cursor_with_overlap():
    fake = FakeHH([hh_item(1, NOW - 100)])
    adapter = HHAdapter(token="t", client=make_client(fake))
    await collect(adapter, str(NOW - 600), NOW)
    params = fake.calls[0][1]
    assert parse_ts(params["date_from"]) == NOW - 600 - hh_mod.OVERLAP_SECONDS
    assert parse_ts(params["date_to"]) == NOW
    # First run (no cursor) looks back FIRST_RUN_LOOKBACK.
    fake.calls.clear()
    await collect(adapter, None, NOW)
    assert parse_ts(fake.calls[0][1]["date_from"]) == NOW - hh_mod.FIRST_RUN_LOOKBACK


async def test_hh_adapter_stops_at_request_budget_keeping_completed_cursor():
    fake = FakeHH([hh_item(i, NOW - 60 * i) for i in range(1, 2501)])
    adapter = HHAdapter(token="t", client=make_client(fake), max_requests_per_run=3)
    batches = await collect(adapter, str(NOW - 2 * 86_400), NOW)
    cursors = [b.cursor for b in batches if b.cursor]
    assert cursors and int(cursors[-1]) < NOW  # stopped early, before the newest window
    assert len(fake.calls) < 40


async def test_hh_adapter_detail_gone_and_present():
    fake = FakeHH()
    fake.details["100001"] = HttpResponse(200, {**{k: v for k, v in hh_item(1, NOW).items() if k != "_ts"},
                                                "description": "<p>Full</p>"}, {})
    adapter = HHAdapter(token="t", client=make_client(fake))
    v = await adapter.fetch_detail("100001")
    assert v.description_text == "Full"
    assert await adapter.fetch_detail("100002") is None
    assert await adapter.fetch_detail("../x") is None


# ---------------------------------------------------------------- osonish


def os_item(i: int, created: str, **over):
    item = {
        "id": 900000000000 + i,
        "title": f"Hamshira {i}",
        "company": {"name": "Synthetic MCHJ"},
        "min_salary": 3_000_000,
        "max_salary": 4_000_000,
        "soato_region": {"soato": "1703", "name_uz": "Andijon viloyati"},
        "soato_district": {"soato": "1703401", "name_uz": "Andijon"},
        "created_at": created,
        "work_experience": 2,
    }
    item.update(over)
    return item


@pytest.fixture
async def osonish_server(monkeypatch):
    routes: dict[str, object] = {}
    seen: list[dict] = []

    async def handler(request: web.Request):
        seen.append(dict(request.query))
        answer = routes.get(request.path)
        if answer is None:
            return web.json_response({"message": "Not found"}, status=404)
        status, body = answer(request) if callable(answer) else answer
        return web.json_response(body, status=status)

    app = web.Application()
    app.router.add_route("GET", "/{tail:.*}", handler)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setattr(scraping, "OSONISH_BASE", str(server.make_url("/api/v1")))
    try:
        yield routes, seen
    finally:
        await server.close()


async def test_osonish_raw_page_helper(osonish_server):
    routes, seen = osonish_server
    routes["/api/v1/vacancies"] = (200, {"data": {"data": [os_item(1, "2026-10-17T05:00:00Z"), "junk"],
                                                  "last_page": 4}})
    items, last = await scraping.fetch_osonish_raw_page(2, 50)
    assert last == 4 and len(items) == 1 and items[0]["soato_region"]["soato"] == "1703"
    assert seen[-1] == {"page": "2", "per_page": "50"}
    routes["/api/v1/vacancies"] = (503, {})
    with pytest.raises(scraping.UpstreamError):
        await scraping.fetch_osonish_raw_page(1)


def test_osonish_normalize():
    v = os_mod.normalize(os_item(1, "2026-10-17T05:00:00Z"))
    assert v.uid == "osonish_900000000001"
    assert v.published_at == NOW
    assert (v.region_soato, v.district_soato) == ("1703", "1703401")
    assert (v.salary_min, v.salary_max, v.currency) == (3_000_000, 4_000_000, "UZS")
    assert v.url == "https://osonish.uz/vacancies/900000000001"
    assert v.description_text == "" and v.contacts == {}
    assert os_mod.normalize(os_item(2, "x")) is None
    assert os_mod.normalize({"id": "1"}) is None
    d = os_mod.normalize(os_item(3, "2026-10-17T05:00:00Z", info="<p>Ish <b>tavsifi</b></p><script>x()</script>",
                                 hr={"name": "Ali", "phone": "+998900000000"}), detail=True)
    assert d.description_text == "Ish tavsifi"
    assert d.contacts == {"name": "Ali", "phones": ["+998900000000"]}


async def test_osonish_adapter_stops_at_old_pages_and_reports_cursor():
    pages = {
        1: [os_item(1, "2026-10-17T05:00:00Z"), os_item(2, "2026-10-17T04:00:00Z")],
        2: [os_item(3, "2026-10-16T05:00:00Z")],
        3: [os_item(4, "2026-10-01T05:00:00Z")],  # whole page older than cursor - overlap
        4: [os_item(5, "2026-09-01T05:00:00Z")],
    }
    asked: list[int] = []

    async def fetch_page(page, per_page):
        asked.append(page)
        return pages[page], 10

    adapter = OsonishAdapter(fetch_page, rate=RateLimiter(0))
    batches = await collect(adapter, str(NOW - 2 * 86_400), NOW)
    assert asked == [1, 2, 3]
    assert [b.cursor for b in batches] == [None, None, str(NOW)]
    assert adapter.stats["requests"] == 3


async def test_osonish_adapter_wraps_upstream_errors():
    async def broken(page, per_page):
        raise scraping.UpstreamError("http_status", 502)

    adapter = OsonishAdapter(broken, rate=RateLimiter(0))
    with pytest.raises(SourceError):
        await collect(adapter, None, NOW)
    assert adapter.stats["errors"] == 1
