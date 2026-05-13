import time
from unittest.mock import patch

import pytest


# DISABLED: ishapi geo-blocked on current VPS
# @pytest.mark.asyncio
# async def test_ishapi_returns_results():
#     from src.functions.scraping import fetch_ishapi_list
#
#     items, last_page = await fetch_ishapi_list(page=1, salary=0, soato="", nskz="")
#     assert len(items) > 0
#     assert last_page > 0
#     v = items[0]
#     assert v.uid.startswith("ishapi_")
#     assert v.title
#     assert v.source == "ishapi"


@pytest.mark.asyncio
async def test_osonish_returns_results():
    from src.functions.scraping import fetch_osonish_list

    items, last_page = await fetch_osonish_list(page=1, salary=0, region_soato="")
    assert len(items) > 0
    assert last_page > 0
    v = items[0]
    assert v.uid.startswith("osonish_")
    assert v.title
    assert v.source == "osonish"


@pytest.mark.asyncio
async def test_merged_search_interleaved():
    from src.functions.functions import search_vakant

    items, last_page = await search_vakant(page=1, money=0, yurt="", specs="")
    assert len(items) >= 2
    assert last_page > 0
    assert all(i.source == "osonish" for i in items)


@pytest.mark.asyncio
async def test_normalize_uid_backward_compat():
    from src.handlers.search import normalize_uid

    assert normalize_uid("12345") == "osonish_12345"
    assert normalize_uid("ishapi_12345") == "osonish_12345"
    assert normalize_uid("osonish_99") == "osonish_99"


def test_cache_mem_ttl_expiry():
    with patch("src.functions.cache.get_redis", return_value=None):
        from src.functions.cache import _mem_get, _mem_set
        import src.functions.cache as cache_module

        _mem_set("test_key", "test_value", ttl=1)
        assert _mem_get("test_key") == "test_value"

        cache_module._mem_cache["test_key"] = ("test_value", time.monotonic() - 1)
        assert _mem_get("test_key") is None
