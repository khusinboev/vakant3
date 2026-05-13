import hashlib
import json
import logging
import os
import time
from typing import Any, Optional

try:
    import redis.asyncio as aioredis
except Exception:  # pragma: no cover
    aioredis = None

logger = logging.getLogger(__name__)

CACHE_TTL = 1800  # 30 minutes
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_redis_client = None
_mem_cache: dict[str, tuple[Any, float]] = {}


def _mem_get(key: str) -> Any | None:
    entry = _mem_cache.get(key)
    if entry is None:
        return None

    value, expires_at = entry
    if time.monotonic() > expires_at:
        del _mem_cache[key]
        return None

    return value


def _mem_set(key: str, value: Any, ttl: int) -> None:
    _mem_cache[key] = (value, time.monotonic() + ttl)


async def get_redis() -> Optional[Any]:
    global _redis_client
    if aioredis is None:
        return None

    if _redis_client is not None:
        return _redis_client

    try:
        _redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await _redis_client.ping()
        return _redis_client
    except Exception as e:
        logger.warning("redis_unavailable error=%s", e)
        _redis_client = None
        return None


async def cache_get(key: str) -> Any | None:
    redis_client = await get_redis()
    if redis_client is not None:
        try:
            raw = await redis_client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.warning("cache_get_redis_error key=%s error=%s", key, e)

    return _mem_get(key)


async def cache_set(key: str, value: Any, ttl: int = CACHE_TTL) -> None:
    redis_client = await get_redis()
    if redis_client is not None:
        try:
            await redis_client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
            return
        except Exception as e:
            logger.warning("cache_set_redis_error key=%s error=%s", key, e)

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
