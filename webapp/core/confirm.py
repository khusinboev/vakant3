"""Confirmation tokens for destructive admin actions.

Flow: the panel asks ``POST /api/admin/confirm`` for a token naming the exact
action and parameters it is about to perform, then repeats the call it really
wants with ``X-Confirm-Token: <token>``. ``require_confirmation`` recomputes
the MAC from the *actual* request body, so a token minted for
``{"user_id": 7, "amount": 1000}`` cannot be replayed against
``{"user_id": 7, "amount": 1000000}``: the parameters are inside the MAC.

Token format: ``<exp>.<hex-hmac-sha256>`` over
``actor_id|action|canonical_json(params)|exp``, keyed with ``WEBAPP_SECRET``.
The MAC covers ``exp``, so the client cannot extend its own token, and the
comparison is constant time.

Single use is deliberately NOT enforced. Enforcing it needs a shared store
(the API runs several workers, so an in-memory set would reject valid tokens
on the wrong worker) and it would buy little: the token is already bound to
one actor, one action and one exact parameter set, and it dies after 60 s.
Replaying it can only repeat the same call the actor just authorised, which
the endpoints' own idempotency/rate limits already govern. Re-use across a
retry (flaky Telegram WebView network) is in fact the behaviour we want.
"""

import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import Depends
from starlette.requests import Request

from webapp.core import errors
from webapp.core.auth import require_admin
from webapp.core.config import get_settings


def canonical_params(params: dict[str, Any] | None) -> str:
    """Stable JSON for MAC input: sorted keys, no whitespace, unicode kept."""
    return json.dumps(
        params or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )


def _sign(actor_id: int, action: str, params: dict[str, Any] | None, exp: int) -> str:
    message = f"{int(actor_id)}|{action}|{canonical_params(params)}|{int(exp)}".encode()
    secret = get_settings().WEBAPP_SECRET.encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def confirm_ttl() -> int:
    return int(get_settings().ADMIN_CONFIRM_TTL_SECONDS or 60)


def issue_confirm_token(actor_id: int, action: str, params: dict[str, Any] | None = None) -> str:
    exp = int(time.time()) + confirm_ttl()
    return f"{exp}.{_sign(actor_id, action, params, exp)}"


def verify_confirm_token(
    token: str, actor_id: int, action: str, params: dict[str, Any] | None = None
) -> bool:
    raw = str(token or "").strip()
    if not raw or "." not in raw:
        return False
    exp_str, _, signature = raw.partition(".")
    try:
        exp = int(exp_str)
    except (TypeError, ValueError):
        return False
    if exp <= int(time.time()):
        return False
    # Reject an absurd expiry even though the MAC covers it — cheap belt and braces.
    if exp > int(time.time()) + confirm_ttl() + 5:
        return False
    return hmac.compare_digest(_sign(actor_id, action, params, exp), signature)


def require_confirmation(action: str, param_keys: list[str]):
    """Dependency factory: the admin actor, once ``X-Confirm-Token`` checks out.

    ``param_keys`` names the body fields the token must be bound to. Reading
    the body here is safe: Starlette caches it, so the endpoint's own pydantic
    model still parses normally.
    """

    async def dependency(request: Request, actor=Depends(require_admin)) -> dict[str, Any]:
        token = (request.headers.get("x-confirm-token") or "").strip()
        if not token:
            raise errors.api_error(403, errors.CONFIRMATION_REQUIRED, action=action)
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        params = {key: body.get(key) for key in param_keys}
        if not verify_confirm_token(token, int(actor["user_id"]), action, params):
            raise errors.api_error(403, errors.CONFIRMATION_REQUIRED, action=action)
        return actor

    dependency.__name__ = f"require_confirmation_{action.replace('.', '_')}"
    dependency.__confirm_action__ = action  # type: ignore[attr-defined]
    return dependency
