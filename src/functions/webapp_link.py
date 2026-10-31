"""Personal signed Mini App links for the bot's keyboards (``?bt=``).

A ``web_app`` button on a REPLY keyboard opens the Mini App with EMPTY
initData, so the usual initData login cannot run there. The bot therefore puts
a per-user signed token into every such URL; the Mini App exchanges it for the
normal Bearer session at ``POST /api/auth/bot-link`` (directly, no confirmation
step, see ``webapp/routers/auth.py``) and removes it from the address bar.
Ported from SlaydX ``lib/server/bot-link.ts``.

Token (version 1), base64url without padding, exactly 39 characters::

    byte 0       version (1)
    bytes 1..8   Telegram user id, unsigned 64-bit big-endian (1 .. 2^53-1)
    bytes 9..12  issued-at, unix seconds, unsigned 32-bit big-endian
    bytes 13..28 HMAC-SHA256(key, bytes 0..12), first 16 bytes

The key is HKDF-SHA256(WEBAPP_SECRET, info=``vakant3/bot-link/v1``): it never
equals the session-signing key, and rotating ``WEBAPP_SECRET`` voids every
outstanding link. A link is valid for :data:`BOT_LINK_TTL_SECONDS` (7 days)
from issue.

Revocation is not inside the token (so signing stays a pure function the bot
can call while building a keyboard, without a database read): the column
``users.bot_links_before`` (migration m021) is a per-user revocation
watermark. A ban or an admin "revoke sessions" sets it to *now*, and the
exchange refuses every link issued at or before it (:func:`is_revoked`).

The token is a bearer credential: never log it, never put it in an error.

This module is shared: the bot signs (``webapp_url``), the API verifies
(``verify_bot_link``). It must not import ``webapp``; the bot reads
``WEBAPP_SECRET`` from the environment (``config.py`` loads ``.env``), the API
passes its own settings value.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re
import struct
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

logger = logging.getLogger(__name__)

#: The query parameter that carries the token (the frontend uses the same name).
BOT_LINK_PARAM = "bt"
BOT_LINK_VERSION = 1
BOT_LINK_TTL_SECONDS = 7 * 86_400
#: Issue dates this far ahead of the verifier's clock are tolerated (two processes).
BOT_LINK_SKEW_SECONDS = 60
#: Exact length of a version-1 token (29 bytes, base64url, no padding).
BOT_LINK_LENGTH = 39
#: Anything longer is refused before decoding.
BOT_LINK_MAX_LENGTH = 64

_PAYLOAD_BYTES = 13
_MAC_BYTES = 16
_KEY_INFO = b"vakant3/bot-link/v1"
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]+")
_MAX_USER_ID = 2**53 - 1
#: Same set the API refuses to start with (``webapp.core.config.INSECURE_SECRETS``).
_INSECURE_SECRETS = {"", "change-me"}

_key_cache: tuple[str, bytes] | None = None


def _derive_key(secret: str) -> bytes:
    """HKDF-SHA256 (RFC 5869) with an empty salt, 32 output bytes."""
    global _key_cache
    if _key_cache is not None and _key_cache[0] == secret:
        return _key_cache[1]
    prk = hmac.new(b"\x00" * 32, secret.encode("utf-8"), hashlib.sha256).digest()
    okm = hmac.new(prk, _KEY_INFO + b"\x01", hashlib.sha256).digest()
    _key_cache = (secret, okm)
    return okm


def _mac(secret: str, payload: bytes) -> bytes:
    return hmac.new(_derive_key(secret), payload, hashlib.sha256).digest()[:_MAC_BYTES]


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _valid_user_id(user_id: object) -> int | None:
    if isinstance(user_id, bool):
        return None
    try:
        value = int(user_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return value if 1 <= value <= _MAX_USER_ID else None


def _env_secret() -> str | None:
    """``WEBAPP_SECRET`` for signing in the bot, or None when it is unusable.

    The insecure default is accepted only with ``ALLOW_INSECURE_SECRET=1``
    (local development), exactly like the API: a link signed with a publicly
    known key could be forged by anyone.
    """
    secret = (os.getenv("WEBAPP_SECRET") or "").strip()
    if secret in _INSECURE_SECRETS:
        allowed = str(os.getenv("ALLOW_INSECURE_SECRET", "")).strip().lower() in {"1", "true", "yes"}
        if not secret or not allowed:
            return None
    return secret


def sign_bot_link(user_id: int, *, secret: str, now: float | None = None) -> str:
    """The version-1 token for ``user_id`` issued at ``now``. Raises ValueError on bad input."""
    uid = _valid_user_id(user_id)
    if uid is None:
        raise ValueError("bot link: invalid user id")
    if not secret:
        raise ValueError("bot link: empty secret")
    iat = int(time.time() if now is None else now)
    if not 0 < iat <= 0xFFFF_FFFF:
        raise ValueError("bot link: issue time out of range")
    payload = struct.pack(">BQI", BOT_LINK_VERSION, uid, iat)
    return _b64encode(payload + _mac(secret, payload))


@dataclass(frozen=True)
class BotLink:
    user_id: int
    issued_at: int
    expires_at: int


def verify_bot_link(token: object, *, secret: str, now: float | None = None) -> BotLink | None:
    """The verified link, or None for anything invalid, forged or expired.

    Order: shape (type, length, alphabet, canonical base64url) -> version ->
    MAC (constant time) -> dates. Revocation is checked by the caller against
    the database (:func:`is_revoked`).
    """
    if not secret or not isinstance(token, str):
        return None
    if len(token) != BOT_LINK_LENGTH or not _TOKEN_RE.fullmatch(token):
        return None
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (ValueError, TypeError):
        return None
    # Non-canonical spellings (stray trailing bits) decode to the same bytes: refuse them.
    if len(raw) != _PAYLOAD_BYTES + _MAC_BYTES or _b64encode(raw) != token:
        return None
    payload, tag = raw[:_PAYLOAD_BYTES], raw[_PAYLOAD_BYTES:]
    if payload[0] != BOT_LINK_VERSION:
        return None
    if not hmac.compare_digest(_mac(secret, payload), tag):
        return None
    _version, uid, iat = struct.unpack(">BQI", payload)
    if not 1 <= uid <= _MAX_USER_ID:
        return None
    now_s = int(time.time() if now is None else now)
    if iat > now_s + BOT_LINK_SKEW_SECONDS:
        return None
    expires_at = iat + BOT_LINK_TTL_SECONDS
    if now_s >= expires_at:
        return None
    return BotLink(user_id=uid, issued_at=iat, expires_at=expires_at)


def is_revoked(link: BotLink, links_before: object) -> bool:
    """True when the link was issued at or before the user's revocation watermark.

    ``links_before`` is ``users.bot_links_before`` (unix seconds, NULL = never
    revoked). "At or before": a link minted in the very second of a ban dies
    with it — the bot sends fresh links on the next /start anyway.
    """
    if links_before is None:
        return False
    try:
        watermark = int(links_before)
    except (TypeError, ValueError):
        return True  # an unreadable watermark fails closed
    return link.issued_at <= watermark


def webapp_url(user_id: int, path: str = "/app", **query: object) -> str:
    """``<WEBAPP_URL origin><path>?<query>&bt=<token>`` for a reply-keyboard ``web_app`` button.

    ``path`` is relative to the origin of ``WEBAPP_URL`` (``/app`` is the Mini
    App entry; ``/admin`` the admin panel). ``query`` values are stringified;
    ``None`` drops a key, and a ``bt`` in ``query`` is ignored. The token is
    bound to ``user_id`` and valid for 7 days.

    Without a usable ``WEBAPP_SECRET`` (or with an invalid id) the URL is
    returned WITHOUT ``bt``: the button still opens the app, the user just is
    not signed in by it. Raises ValueError for a path that would leave the
    WEBAPP_URL origin.
    """
    from config import WEBAPP_URL  # lazy: the API imports this module without the bot config

    base = urlsplit(WEBAPP_URL)
    rel = path if path.startswith("/") else f"/{path}"
    # ``//host`` or ``/\host`` would make a browser leave our origin.
    if rel.startswith("//") or rel.startswith("/\\"):
        raise ValueError("webapp_url: path must stay on the WEBAPP_URL origin")
    rel_parts = urlsplit(rel)
    if rel_parts.scheme or rel_parts.netloc:
        raise ValueError("webapp_url: path must stay on the WEBAPP_URL origin")

    params = [(k, v) for k, v in parse_qsl(rel_parts.query, keep_blank_values=True) if k != BOT_LINK_PARAM]
    params += [(str(k), str(v)) for k, v in query.items() if v is not None and k != BOT_LINK_PARAM]

    secret = _env_secret()
    uid = _valid_user_id(user_id)
    if secret is None:
        logger.warning("webapp_url: WEBAPP_SECRET unusable, sending a link without bt")
    elif uid is not None:
        params.append((BOT_LINK_PARAM, sign_bot_link(uid, secret=secret)))

    return urlunsplit(
        (base.scheme, base.netloc, rel_parts.path, urlencode(params), rel_parts.fragment)
    )
