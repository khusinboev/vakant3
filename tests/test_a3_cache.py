"""src/functions/cache.py: bounded in-memory fallback and Redis negative backoff."""

import logging
import socket
import time

import pytest

from src.functions import cache


@pytest.fixture(autouse=True)
def clean_cache(monkeypatch):
    cache._mem_cache.clear()
    monkeypatch.setattr(cache, "_redis_client", None)
    monkeypatch.setattr(cache, "_redis_retry_at", 0.0)
    monkeypatch.setattr(cache, "_redis_down_logged", False)
    yield
    cache._mem_cache.clear()


async def test_memory_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(cache, "REDIS_URL", "")
    monkeypatch.setattr(cache, "MEM_CACHE_MAX_ENTRIES", 100)
    for i in range(1000):
        await cache.cache_set(f"k{i}", i, ttl=600)
        assert len(cache._mem_cache) <= 100
    # The newest entries survive, the oldest were evicted.
    assert await cache.cache_get("k999") == 999
    assert await cache.cache_get("k0") is None


async def test_eviction_prefers_expired_then_least_recently_used(monkeypatch):
    monkeypatch.setattr(cache, "REDIS_URL", "")
    monkeypatch.setattr(cache, "MEM_CACHE_MAX_ENTRIES", 20)
    await cache.cache_set("hot", "h", ttl=600)
    for i in range(10):
        await cache.cache_set(f"stale{i}", i, ttl=600)
    for i in range(10):
        cache._mem_cache[f"stale{i}"] = (i, time.monotonic() - 1)  # expired
    for i in range(9):
        await cache.cache_set(f"fresh{i}", i, ttl=600)
    assert await cache.cache_get("hot") == "h"  # touch: now most recently used

    await cache.cache_set("overflow", 1, ttl=600)  # 21 entries -> evict
    assert not any(k.startswith("stale") for k in cache._mem_cache)
    assert await cache.cache_get("hot") == "h"
    assert [await cache.cache_get(f"fresh{i}") for i in range(9)] == list(range(9))


async def test_eviction_drops_least_recently_used_first(monkeypatch):
    monkeypatch.setattr(cache, "REDIS_URL", "")
    monkeypatch.setattr(cache, "MEM_CACHE_MAX_ENTRIES", 20)
    for i in range(20):
        await cache.cache_set(f"a{i}", i, ttl=600)
    assert await cache.cache_get("a0") == 0  # the oldest insert, but just used
    await cache.cache_set("new", 1, ttl=600)  # 21 > 20 -> shrink to 18
    assert len(cache._mem_cache) == 18
    assert await cache.cache_get("a0") == 0
    assert [k for k in ("a1", "a2", "a3") if k in cache._mem_cache] == []
    assert await cache.cache_get("a4") == 4


async def test_empty_redis_url_never_tries_redis(monkeypatch):
    monkeypatch.setattr(cache, "REDIS_URL", "")

    def boom(*args, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError("redis client created")

    monkeypatch.setattr(cache.aioredis, "from_url", boom)
    assert await cache.get_redis() is None
    await cache.cache_set("a", 1)
    assert await cache.cache_get("a") == 1


def _dead_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


async def test_redis_down_backs_off_and_logs_once(monkeypatch, caplog):
    monkeypatch.setattr(cache, "REDIS_URL", f"redis://127.0.0.1:{_dead_port()}/0")
    attempts = {"n": 0}
    real_from_url = cache.aioredis.from_url

    def counting_from_url(*args, **kwargs):
        attempts["n"] += 1
        return real_from_url(*args, **kwargs)

    monkeypatch.setattr(cache.aioredis, "from_url", counting_from_url)

    with caplog.at_level(logging.DEBUG, logger=cache.logger.name):
        for i in range(20):
            await cache.cache_set(f"k{i}", i)
            assert await cache.cache_get(f"k{i}") == i  # in-memory fallback serves it

    assert attempts["n"] == 1  # one connect attempt, then the backoff window
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert "redis_unavailable" in warnings[0].getMessage()

    # After the window it tries again (still down): another attempt, no new warning.
    monkeypatch.setattr(cache, "_redis_retry_at", time.monotonic() - 1)
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=cache.logger.name):
        assert await cache.get_redis() is None
    assert attempts["n"] == 2
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


async def test_command_failure_on_a_live_client_backs_off(monkeypatch):
    monkeypatch.setattr(cache, "REDIS_URL", "redis://example.invalid:6379/0")

    class FlakyRedis:
        async def get(self, key):
            raise ConnectionError("connection reset")

    monkeypatch.setattr(cache, "_redis_client", FlakyRedis())
    cache._mem_set("k", "from-memory", 60)
    assert await cache.cache_get("k") == "from-memory"
    assert cache._redis_client is None
    assert cache._redis_retry_at > time.monotonic()
