"""The caller's IP address, resolved the only way a proxied deployment can.

``X-Forwarded-For`` is a *client-appendable* header: a request that arrives at
nginx already carrying ``X-Forwarded-For: 1.2.3.4`` leaves it with
``1.2.3.4, <real client>``. Reading the **first** hop therefore reads a value
the client wrote — which is fine for logging a friendly hint and fatal for
anything that buckets (rate limits) or attributes (audit rows) by IP.

So the order here is:

1. ``X-Real-IP`` — nginx sets it with ``proxy_set_header X-Real-IP
   $remote_addr`` (see ``deploy.txt``), i.e. the socket peer as *nginx* saw it.
   The client cannot influence it because nginx overwrites whatever arrived.
2. the **last** hop of ``X-Forwarded-For`` — appended by the closest trusted
   proxy, so it is the only hop in that list a client cannot forge.
3. ``request.client.host`` — the socket peer, for a direct (unproxied) run.

Everything is truncated to 64 characters so a crafted header can neither blow
up an audit row nor create unbounded rate-limit buckets.
"""

from __future__ import annotations

from typing import Any

MAX_IP_CHARS = 64


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    # A header value with control characters is not an address; drop it rather
    # than letting it into a log line or a bucket key.
    if any(ch in text for ch in "\r\n\t\x00"):
        return None
    return text[:MAX_IP_CHARS]


def client_ip(request: Any) -> str | None:
    """Resolve the caller's IP. Returns None when nothing usable is available."""
    if request is None:
        return None

    headers = getattr(request, "headers", None)
    if headers is not None:
        real_ip = _clean(headers.get("x-real-ip"))
        if real_ip:
            return real_ip

        forwarded = str(headers.get("x-forwarded-for") or "")
        if forwarded:
            hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
            if hops:
                last_hop = _clean(hops[-1])
                if last_hop:
                    return last_hop

    client = getattr(request, "client", None)
    return _clean(getattr(client, "host", None))
