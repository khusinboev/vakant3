"""osonish.uz client: a genuine empty result vs. an outage.

A local aiohttp server stands in for osonish.uz (``OSONISH_BASE`` is pointed
at it), so the real ``request_json`` / aiohttp code path runs end to end and no
call leaves the machine.
"""

import asyncio
import socket

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from src.functions import scraping
from src.functions.scraping import (
    MAX_OSONISH_ID,
    UpstreamError,
    fetch_osonish_detail,
    fetch_osonish_list,
    get_osonish_detail,
    parse_osonish_uid,
)


def _list_body(items, last_page=3):
    return {"data": {"data": items, "last_page": last_page}}


VACANCY = {
    "id": 900000000001,
    "title": "Synthetic vacancy",
    "company": {"name": "ACME"},
    "min_salary": 1000,
    "max_salary": 2000,
    "soato_region": {"name_uz": "Toshkent"},
    "soato_district": {"name_uz": "Chilonzor"},
    "created_at": "2026-10-01T10:00:00Z",
}


@pytest.fixture
async def osonish(monkeypatch):
    """A fake osonish whose answer per path is set by the test."""
    routes: dict[str, object] = {}

    async def handler(request: web.Request):
        answer = routes.get(request.path)
        if answer is None:
            return web.json_response({"message": "Not found"}, status=404)
        if callable(answer):
            return await answer(request)
        status, body = answer
        if isinstance(body, str):
            return web.Response(status=status, text=body, content_type="text/html")
        return web.json_response(body, status=status)

    app = web.Application()
    app.router.add_route("GET", "/{tail:.*}", handler)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setattr(scraping, "OSONISH_BASE", str(server.make_url("/api/v1")))
    try:
        yield routes
    finally:
        await server.close()


async def _list():
    return await fetch_osonish_list(page=1, salary=0, soato_region="")


async def test_list_parses_a_normal_answer(osonish):
    osonish["/api/v1/vacancies"] = (200, _list_body([VACANCY], last_page=7))
    items, last_page = await _list()
    assert last_page == 7
    assert [v.uid for v in items] == ["osonish_900000000001"]
    assert items[0].company == "ACME"


async def test_list_genuine_empty_result_is_not_an_error(osonish):
    osonish["/api/v1/vacancies"] = (200, _list_body([], last_page=1))
    assert await _list() == ([], 1)


@pytest.mark.parametrize("status", [500, 502, 503, 404, 429])
async def test_list_non_200_raises(osonish, status):
    osonish["/api/v1/vacancies"] = (status, {"error": "x"})
    with pytest.raises(UpstreamError) as exc_info:
        await _list()
    assert exc_info.value.status == status


@pytest.mark.parametrize(
    "body",
    [{"data": None}, {"data": {"last_page": 1}}, {"data": {"data": "oops"}}, [1, 2], "<html>maintenance</html>"],
)
async def test_list_malformed_200_raises(osonish, body):
    osonish["/api/v1/vacancies"] = (200, body)
    with pytest.raises(UpstreamError):
        await _list()


async def test_list_timeout_raises(osonish, monkeypatch):
    async def slow(request):
        await asyncio.sleep(2)
        return web.json_response(_list_body([]))

    osonish["/api/v1/vacancies"] = slow
    monkeypatch.setattr(scraping, "OSONISH_TIMEOUT_SECONDS", 0.2)
    with pytest.raises(UpstreamError) as exc_info:
        await _list()
    assert "transport" in exc_info.value.reason


async def test_list_connection_refused_raises(monkeypatch):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()  # nothing listens on this port any more
    monkeypatch.setattr(scraping, "OSONISH_BASE", f"http://127.0.0.1:{port}/api/v1")
    with pytest.raises(UpstreamError):
        await _list()


async def test_detail_not_found_vs_outage(osonish):
    osonish["/api/v1/vacancies/5"] = (200, {"data": {"id": 5, "title": "ok"}})
    assert (await get_osonish_detail(5))["title"] == "ok"

    # No route -> the fake answers 404: "no such vacancy", not an outage.
    assert await get_osonish_detail(6) is None

    osonish["/api/v1/vacancies/7"] = (200, {"data": None})
    assert await get_osonish_detail(7) is None

    osonish["/api/v1/vacancies/8"] = (503, {"error": "down"})
    with pytest.raises(UpstreamError):
        await get_osonish_detail(8)


async def test_lenient_detail_for_the_bot_never_raises(osonish):
    osonish["/api/v1/vacancies/8"] = (500, {"error": "down"})
    assert await fetch_osonish_detail(8) is None
    osonish["/api/v1/vacancies/9"] = (200, {"data": {"id": 9}})
    assert await fetch_osonish_detail(9) == {"id": 9}


async def test_lenient_fetch_json_keeps_returning_none(osonish):
    osonish["/api/v1/regions"] = (500, {"error": "down"})
    assert await scraping.fetch_json(scraping.OSONISH_BASE + "/regions") is None
    osonish["/api/v1/regions"] = (200, {"data": [1]})
    assert await scraping.fetch_json(scraping.OSONISH_BASE + "/regions") == {"data": [1]}


@pytest.mark.parametrize(
    "uid, expected",
    [
        ("osonish_1", 1),
        ("osonish_123456", 123456),
        (f"osonish_{MAX_OSONISH_ID}", MAX_OSONISH_ID),
        (f"osonish_{MAX_OSONISH_ID + 1}", None),
        ("osonish_" + "9" * 30, None),
        ("osonish_0", None),
        ("osonish_-5", None),
        ("osonish_+5", None),
        ("osonish_007", None),
        ("osonish_1_000", None),
        ("osonish_ 5", None),
        ("osonish_٥", None),  # Arabic-Indic digit: isdigit() but not ASCII
        ("osonish_", None),
        ("ishapi_5", None),
        ("5", None),
    ],
)
def test_parse_osonish_uid(uid, expected):
    assert parse_osonish_uid(uid) == expected
