"""Rate-limit key resolution.

A bucket may only ever be keyed on an identity the *server* has verified.
Keying on the raw ``Authorization``/``X-Telegram-Init-Data`` header — as this
module used to — hands the limiter to the caller: every junk token is a fresh,
empty bucket, so any limit can be walked around by changing one character of a
string nobody checked.

So the order is:

1. ``request.state.user_id`` — set by ``webapp.core.auth`` once a request has
   been authenticated. Present whenever a dependency already resolved the user
   (slowapi evaluates the key *before* dependencies run, so this is mostly a
   free fast path for the second and later limits on one request).
2. a Bearer token whose **JWS signature verifies** against ``WEBAPP_SECRET``
   (``decode_session_token``, which also rejects an expired payload): the
   session id inside is then a server-issued value. No database is touched —
   the key function runs on every request and must stay cheap.
3. initData whose **HMAC verifies** against the bot token: its user id.
4. otherwise the client IP (``webapp.core.request_ip``), never a header the
   caller can pick.

An unverifiable credential falls through to the IP bucket, so minting junk
tokens buys nothing. The resolved key is memoised on ``request.state`` because
a route with several limits calls this once per limit.
"""

import logging
import os

from slowapi import Limiter
from starlette.requests import Request

from webapp.core.request_ip import client_ip as _resolve_client_ip

_KEY_STATE = "_rate_limit_key"


def _client_ip(request: Request) -> str:
    return _resolve_client_ip(request) or "unknown"


def _verified_session_key(authorization: str) -> str | None:
    """``sess:<sid>`` for a Bearer token with a valid, unexpired signature."""
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    # Imported lazily: ``webapp.core.session`` pulls in config/users, and this
    # module is imported by every router.
    from webapp.core.session import decode_session_token

    try:
        payload = decode_session_token(token)
    except Exception:
        return None
    sid = str(payload.get("sid") or "").strip()
    return f"sess:{sid}" if sid else None


def _verified_init_data_key(init_data: str) -> str | None:
    """``tg:<user_id>`` for initData whose HMAC checks out against the bot token."""
    if not init_data:
        return None
    from webapp.core.config import get_settings
    from webapp.core.telegram_auth import verify_webapp_init_data

    try:
        settings = get_settings()
        if not settings.TOKEN:
            return None
        tg_user = verify_webapp_init_data(init_data, settings.TOKEN)
        if not tg_user:
            return None
        user_id = int(tg_user.get("id") or 0)
    except Exception:
        return None
    return f"tg:{user_id}" if user_id else None


def _identity_key(request: Request) -> str | None:
    """The caller's VERIFIED identity, or None (never an unchecked string)."""
    state_user_id = getattr(request.state, "user_id", None)
    if state_user_id:
        try:
            return f"u:{int(state_user_id)}"
        except (TypeError, ValueError):
            pass

    return _verified_session_key(
        request.headers.get("authorization") or ""
    ) or _verified_init_data_key((request.headers.get("x-telegram-init-data") or "").strip())


def rate_limit_key(request: Request) -> str:
    cached = getattr(request.state, _KEY_STATE, None)
    if cached is not None:
        return cached
    key = _identity_key(request) or f"ip:{_client_ip(request)}"
    try:
        setattr(request.state, _KEY_STATE, key)
    except Exception:  # pragma: no cover - a stateless stub request
        pass
    return key


_log = logging.getLogger(__name__)


def _reachable_redis_uri() -> str | None:
    """REDIS_URL if a PING succeeds right now, else None.

    Checked once at import: with several uvicorn workers an in-memory limiter
    counts per worker, so Redis is what makes the configured limits real.
    """
    url = (os.getenv("REDIS_URL") or "").strip()
    if not url:
        return None
    try:
        import redis  # imported lazily: the package is optional

        client = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        try:
            client.ping()
        finally:
            client.close()
        return url
    except Exception as exc:
        _log.warning("rate limiter: Redis at %s unreachable (%s)", url, exc)
        return None


def _build_limiter() -> Limiter:
    storage_uri = _reachable_redis_uri()
    if storage_uri:
        _log.info("rate limiter backend: redis (shared across workers)")
        return Limiter(
            key_func=rate_limit_key,
            storage_uri=storage_uri,
            # If Redis dies later, slowapi retries the same limits against
            # in-process storage instead of failing the request.
            in_memory_fallback_enabled=True,
            swallow_errors=True,
        )
    _log.info("rate limiter backend: in-memory (per worker)")
    return Limiter(key_func=rate_limit_key)


limiter = _build_limiter()
