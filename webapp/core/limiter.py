"""Rate-limit key resolution.

Buckets are keyed on the caller's identity when the request carries one
(so several users behind one NAT/nginx IP do not share a bucket), and on the
first X-Forwarded-For hop otherwise.

The parsing here is intentionally cheap and unverified: it only picks a bucket,
it never grants access. Authentication happens in ``webapp.core.auth``.
"""

import json
import urllib.parse

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    first_hop = forwarded.split(",")[0].strip()
    if first_hop:
        return first_hop
    return get_remote_address(request) or "unknown"


def _identity_key(request: Request) -> str | None:
    authorization = request.headers.get("authorization") or ""
    if authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            # The signature part alone identifies the session without verifying it.
            return f"sess:{token[-32:]}"

    init_data = request.headers.get("x-telegram-init-data") or ""
    if init_data:
        try:
            parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
            user_id = json.loads(parsed.get("user") or "{}").get("id")
            if user_id:
                return f"tg:{int(user_id)}"
        except Exception:
            return None
    return None


def rate_limit_key(request: Request) -> str:
    return _identity_key(request) or f"ip:{_client_ip(request)}"


limiter = Limiter(key_func=rate_limit_key)
