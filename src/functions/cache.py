import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from typing import Any, Optional

try:
    import redis.asyncio as aioredis
except Exception:  # pragma: no cover
    aioredis = None

logger = logging.getLogger(__name__)

CACHE_TTL = 1800  # 30 minutes
#: Empty string disables Redis entirely (the in-memory fallback is used).
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
#: After a failed connect or command, Redis is not tried again for this long:
#: a down Redis must not cost every request a connect attempt and a log line.
REDIS_RETRY_SECONDS = 30.0
REDIS_SOCKET_TIMEOUT_SECONDS = 1.0
#: In-memory fallback bound (per worker). Search keys are user-controlled
#: (query text, page, filters), so an unbounded dict is a memory leak.
MEM_CACHE_MAX_ENTRIES = max(16, int(os.getenv("CACHE_MAX_ENTRIES", "2048")))

_redis_client = None
_redis_retry_at = 0.0
_redis_down_logged = False
#: key -> (value, expires_at monotonic); order = least recently used first.
_mem_cache: "OrderedDict[str, tuple[Any, float]]" = OrderedDict()


def _mem_get(key: str) -> Any | None:
    entry = _mem_cache.get(key)
    if entry is None:
        return None

    value, expires_at = entry
    if time.monotonic() > expires_at:
        del _mem_cache[key]
        return None

    _mem_cache.move_to_end(key)
    return value


def _mem_set(key: str, value: Any, ttl: int) -> None:
    now = time.monotonic()
    _mem_cache[key] = (value, now + ttl)
    _mem_cache.move_to_end(key)
    if len(_mem_cache) > MEM_CACHE_MAX_ENTRIES:
        _mem_evict(now)


def _mem_evict(now: float) -> None:
    """Drop expired entries, then the least recently used, down to 90 % of the bound.

    Shrinking below the bound keeps the O(n) expiry scan off the hot path: it
    runs at most once per ~10 % of the capacity in inserts.
    """
    for key in [k for k, (_, expires_at) in _mem_cache.items() if expires_at <= now]:
        del _mem_cache[key]
    target = int(MEM_CACHE_MAX_ENTRIES * 0.9)
    while len(_mem_cache) > target:
        _mem_cache.popitem(last=False)


async def _redis_failed(error: Exception, where: str, client: Any = None) -> None:
    """Close and forget the client, back off; log the outage once, not per request."""
    global _redis_client, _redis_retry_at, _redis_down_logged
    if _redis_client is client:
        _redis_client = None
    _redis_retry_at = time.monotonic() + REDIS_RETRY_SECONDS
    if not _redis_down_logged:
        _redis_down_logged = True
        logger.warning(
            "redis_unavailable where=%s error=%s (in-memory cache, retry every %ss)",
            where, error, int(REDIS_RETRY_SECONDS),
        )
    else:
        logger.debug("redis_still_unavailable where=%s error=%s", where, error)
    if client is not None:
        try:
            await client.aclose()  # its connection pool and sockets
        except Exception as close_exc:  # pragma: no cover - best effort
            logger.debug("redis_close_failed error=%s", close_exc)


async def get_redis() -> Optional[Any]:
    global _redis_client, _redis_down_logged
    if aioredis is None or not REDIS_URL:
        return None

    if _redis_client is not None:
        return _redis_client

    if time.monotonic() < _redis_retry_at:
        return None

    client = None
    try:
        client = aioredis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
            socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
        )
        await client.ping()
    except Exception as e:
        await _redis_failed(e, "connect", client)
        return None

    _redis_client = client
    if _redis_down_logged:
        _redis_down_logged = False
        logger.info("redis_available_again")
    return client


async def cache_get(key: str) -> Any | None:
    redis_client = await get_redis()
    if redis_client is not None:
        try:
            raw = await redis_client.get(key)
        except Exception as e:
            await _redis_failed(e, "get", redis_client)
        else:
            if raw is None:
                return None
            try:
                return json.loads(raw)
            except ValueError:
                logger.warning("cache_get_bad_json key=%s", key)
                return None

    return _mem_get(key)


async def cache_set(key: str, value: Any, ttl: int = CACHE_TTL) -> None:
    redis_client = await get_redis()
    if redis_client is not None:
        try:
            await redis_client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
            return
        except Exception as e:
            await _redis_failed(e, "set", redis_client)

    _mem_set(key, value, ttl)


def make_cache_key(prefix: str, **kwargs: Any) -> str:
    if not kwargs:
        return prefix

    parts = [f"{k}={kwargs[k]}" for k in sorted(kwargs)]
    raw = f"{prefix}:{':'.join(parts)}"

    if len(raw) <= 240:
        return raw

    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"{prefix}:sha1={digest}"
