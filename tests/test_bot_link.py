"""Signed bot keyboard links (``?bt=``): the token, the URL builder and the exchange.

``src/functions/webapp_link.py`` signs/verifies; ``POST /api/auth/bot-link``
turns a valid link into a Bearer session directly (no confirm step); a ban or
an admin "revoke sessions" kills every link issued so far (m021 watermark).
The endpoint tests run the real app through the b3 harness. Ids are synthetic.
"""

from __future__ import annotations

import base64
import struct
import time
from urllib.parse import parse_qs, urlsplit

import aiosqlite
import pytest

from src.functions import webapp_link
from src.functions.webapp_link import (
    BOT_LINK_LENGTH,
    BOT_LINK_TTL_SECONDS,
    BotLink,
    is_revoked,
    sign_bot_link,
    verify_bot_link,
    webapp_url,
)
from tests import b3_support
from tests.b3_support import ADMIN, MODERATOR, USER, USER2, confirm_header
from webapp.core.config import get_settings
from webapp.main import app

harness = b3_support.harness

SECRET = "unit-test-secret-for-bot-links"
UID = 900_000_000_123
NOW = 1_800_000_000
GATED = "/api/notifications/settings"
ME = "/api/auth/me"


def _raw(token: str) -> bytes:
    return base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))


def _enc(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


# ---------------------------------------------------------------------------
# token
# ---------------------------------------------------------------------------
def test_sign_and_verify_round_trip():
    token = sign_bot_link(UID, secret=SECRET, now=NOW)
    assert len(token) == BOT_LINK_LENGTH
    link = verify_bot_link(token, secret=SECRET, now=NOW + 10)
    assert link == BotLink(user_id=UID, issued_at=NOW, expires_at=NOW + BOT_LINK_TTL_SECONDS)


def test_layout_is_version_id_iat_mac():
    raw = _raw(sign_bot_link(UID, secret=SECRET, now=NOW))
    assert struct.unpack(">BQI", raw[:13]) == (1, UID, NOW)
    assert len(raw) == 29


def test_expiry_boundary():
    token = sign_bot_link(UID, secret=SECRET, now=NOW)
    assert verify_bot_link(token, secret=SECRET, now=NOW + BOT_LINK_TTL_SECONDS - 1) is not None
    assert verify_bot_link(token, secret=SECRET, now=NOW + BOT_LINK_TTL_SECONDS) is None


def test_future_issue_date_beyond_skew_is_refused():
    token = sign_bot_link(UID, secret=SECRET, now=NOW + 61)
    assert verify_bot_link(token, secret=SECRET, now=NOW) is None
    assert verify_bot_link(sign_bot_link(UID, secret=SECRET, now=NOW + 60), secret=SECRET, now=NOW)


def test_other_secret_is_refused():
    token = sign_bot_link(UID, secret=SECRET, now=NOW)
    assert verify_bot_link(token, secret=SECRET + "x", now=NOW) is None
    assert verify_bot_link(token, secret="", now=NOW) is None


def test_key_is_domain_separated_from_a_plain_hmac():
    """The MAC key is HKDF-derived, not WEBAPP_SECRET itself."""
    import hashlib
    import hmac

    raw = _raw(sign_bot_link(UID, secret=SECRET, now=NOW))
    plain = hmac.new(SECRET.encode(), raw[:13], hashlib.sha256).digest()[:16]
    assert raw[13:] != plain


def test_key_matches_an_independent_hkdf_with_the_vakant3_label():
    """Pins the derivation: HKDF-SHA256(secret, salt=empty, info=vakant3/bot-link/v1)."""
    import hashlib
    import hmac

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"vakant3/bot-link/v1").derive(
        SECRET.encode()
    )
    raw = _raw(sign_bot_link(UID, secret=SECRET, now=NOW))
    assert raw[13:] == hmac.new(key, raw[:13], hashlib.sha256).digest()[:16]


def test_retargeting_to_another_user_breaks_the_mac():
    raw = bytearray(_raw(sign_bot_link(UID, secret=SECRET, now=NOW)))
    raw[1:9] = struct.pack(">Q", UID + 1)
    assert verify_bot_link(_enc(bytes(raw)), secret=SECRET, now=NOW) is None


def test_extending_the_issue_date_breaks_the_mac():
    raw = bytearray(_raw(sign_bot_link(UID, secret=SECRET, now=NOW)))
    raw[9:13] = struct.pack(">I", NOW + 86_400)
    assert verify_bot_link(_enc(bytes(raw)), secret=SECRET, now=NOW + 86_400) is None


@pytest.mark.parametrize("position", [0, 5, 12, 13, 20, 28])
def test_any_flipped_byte_is_refused(position):
    raw = bytearray(_raw(sign_bot_link(UID, secret=SECRET, now=NOW)))
    raw[position] ^= 0x01
    assert verify_bot_link(_enc(bytes(raw)), secret=SECRET, now=NOW) is None


def test_malformed_tokens_are_refused():
    good = sign_bot_link(UID, secret=SECRET, now=NOW)
    for bad in (None, 123, b"x", "", good[:-1], good + "A", good + "=", "!" * 39, good.replace(good[5], "+", 1)):
        assert verify_bot_link(bad, secret=SECRET, now=NOW) is None, bad


def test_non_canonical_trailing_bits_are_refused():
    good = sign_bot_link(UID, secret=SECRET, now=NOW)
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    last = alphabet.index(good[-1])
    # 29 bytes -> 39 chars: the last char carries 2 data bits + 4 padding bits.
    twin = good[:-1] + alphabet[last ^ 0x01]
    assert _raw(twin) == _raw(good)
    assert verify_bot_link(twin, secret=SECRET, now=NOW) is None


def test_sign_rejects_bad_input():
    for bad in (0, -1, 2**53, "abc", None, True):
        with pytest.raises(ValueError):
            sign_bot_link(bad, secret=SECRET, now=NOW)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        sign_bot_link(UID, secret="", now=NOW)


def test_is_revoked_watermark():
    link = BotLink(user_id=UID, issued_at=NOW, expires_at=NOW + BOT_LINK_TTL_SECONDS)
    assert is_revoked(link, None) is False
    assert is_revoked(link, NOW - 1) is False
    assert is_revoked(link, NOW) is True
    assert is_revoked(link, NOW + 1) is True
    assert is_revoked(link, "junk") is True


# ---------------------------------------------------------------------------
# webapp_url
# ---------------------------------------------------------------------------
def test_webapp_url_builds_a_signed_link():
    url = webapp_url(UID, "/app", go="profile")
    parts = urlsplit(url)
    assert (parts.scheme, parts.netloc, parts.path) == ("https", "abitur24.uz", "/app")
    query = parse_qs(parts.query)
    assert query["go"] == ["profile"]
    link = verify_bot_link(query["bt"][0], secret=get_settings().WEBAPP_SECRET)
    assert link is not None and link.user_id == UID


def test_webapp_url_default_path_and_query_handling():
    url = webapp_url(UID, bt="attacker", skip=None)
    parts = urlsplit(url)
    assert parts.path == "/app"
    query = parse_qs(parts.query)
    assert list(query) == ["bt"] and query["bt"][0] != "attacker"
    url = webapp_url(UID, "admin?x=1&bt=old")
    query = parse_qs(urlsplit(url).query)
    assert urlsplit(url).path == "/admin"
    assert query["x"] == ["1"] and len(query["bt"]) == 1 and query["bt"][0] != "old"


@pytest.mark.parametrize("path", ["//evil.example/app", "/\\evil.example"])
def test_webapp_url_refuses_to_leave_the_origin(path):
    with pytest.raises(ValueError):
        webapp_url(UID, path)


def test_webapp_url_absolute_url_stays_a_path_on_our_origin():
    assert urlsplit(webapp_url(UID, "https://evil.example/app")).netloc == "abitur24.uz"


def test_webapp_url_without_a_usable_secret_has_no_token(monkeypatch):
    monkeypatch.setenv("WEBAPP_SECRET", "change-me")
    monkeypatch.setenv("ALLOW_INSECURE_SECRET", "")
    assert "bt=" not in webapp_url(UID, go="saves")
    monkeypatch.setenv("WEBAPP_SECRET", "")
    assert "bt=" not in webapp_url(UID, go="saves")
    assert webapp_url(UID, go="saves").endswith("/app?go=saves")


def test_webapp_url_with_invalid_user_has_no_token():
    assert "bt=" not in webapp_url(0)


# ---------------------------------------------------------------------------
# POST /api/auth/bot-link
# ---------------------------------------------------------------------------
def _token(user_id: int = USER, now: float | None = None) -> str:
    return sign_bot_link(user_id, secret=get_settings().WEBAPP_SECRET, now=now)


_NO_CONFIRM = object()


async def _exchange(h, token: str, confirm=_NO_CONFIRM, headers: dict | None = None):
    body: dict = {"token": token}
    if confirm is not _NO_CONFIRM:
        body["confirm"] = confirm
    return await h.http.post("/api/auth/bot-link", json=body, headers=headers or {})


async def test_exchange_signs_in_directly_without_any_confirm_step(harness):
    """Owner rule: a valid link logs in at once — no 409 «X sifatida kirasizmi?»."""
    await harness.execute("UPDATE users SET first_name = 'Ali' WHERE user_id = ?", (USER,))
    response = await _exchange(harness, _token())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["user_id"] == USER and body["session_token"]
    assert await harness.sessions_of(USER) == 1


@pytest.mark.parametrize("confirm", [False, True, None])
async def test_exchange_accepts_the_legacy_confirm_field(harness, confirm):
    """Old builds still send ``confirm``: any value is ignored, the link signs in."""
    response = await _exchange(harness, _token(), confirm=confirm)
    assert response.status_code == 200, response.text
    assert response.json()["user"]["user_id"] == USER
    assert await harness.sessions_of(USER) == 1


async def test_exchange_happy_path_issues_a_working_session(harness):
    response = await _exchange(harness, _token())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["user_id"] == USER
    assert await harness.sessions_of(USER) == 1
    headers = {"Authorization": f"Bearer {body['session_token']}"}
    me = await harness.http.get(ME, headers=headers)
    assert me.status_code == 200 and me.json()["user_id"] == USER
    assert (await harness.http.get(GATED, headers=headers)).status_code == 200
    # A normal login is not audited.
    assert await harness.query("SELECT 1 FROM admin_audit_log WHERE target_id = ?", (str(USER),)) == []


async def test_exchange_binds_to_the_link_owner_not_the_caller(harness):
    caller = await harness.session(USER2)
    response = await _exchange(harness, _token(USER), headers=caller)
    assert response.status_code == 200
    assert response.json()["user"]["user_id"] == USER


@pytest.mark.parametrize(
    "token",
    [
        "",
        "x" * 39,
        "A" * 200,
        "forged",
    ],
)
async def test_exchange_rejects_garbage(harness, token):
    response = await _exchange(harness, token)
    assert response.status_code == 401
    assert response.json()["detail"] == {"code": "BOT_LINK_INVALID"}


async def test_exchange_rejects_other_secret_expired_and_unknown_user(harness):
    cases = [
        sign_bot_link(USER, secret="some-other-secret"),
        _token(now=time.time() - BOT_LINK_TTL_SECONDS - 5),
        _token(900_000_000_999),  # never started the bot
    ]
    for token in cases:
        for confirm in (_NO_CONFIRM, False, True):
            response = await _exchange(harness, token, confirm=confirm)
            assert response.status_code == 401, response.text
            assert response.json()["detail"] == {"code": "BOT_LINK_INVALID"}
    assert await harness.sessions_of(USER) == 0


async def test_exchange_for_a_banned_user_matches_init_data_login(harness):
    """Like ``/auth/tg-webapp``: a session is issued, the entry gate refuses it."""
    await harness.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (USER,))
    response = await _exchange(harness, _token())
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['session_token']}"}
    gated = await harness.http.get(GATED, headers=headers)
    assert gated.status_code == 403
    assert gated.json()["detail"]["code"] == "USER_BANNED"


async def test_ban_revokes_links_issued_before_it(harness):
    old = _token(now=time.time() - 5)
    response = await harness.http.post(
        f"/api/admin/users/{USER}/ban",
        json={"banned": True, "reason": "spam"},
        headers=await harness.session(MODERATOR),
    )
    assert response.status_code == 200, response.text
    watermark = await harness.scalar("SELECT bot_links_before FROM users WHERE user_id = ?", (USER,))
    assert watermark is not None and abs(int(watermark) - time.time()) < 5
    answer = await _exchange(harness, old)
    assert answer.status_code == 401
    assert answer.json()["detail"] == {"code": "BOT_LINK_INVALID"}
    # Other users' links are untouched.
    assert (await _exchange(harness, _token(USER2))).status_code == 200


async def test_unban_does_not_move_the_watermark(harness):
    await harness.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (USER,))
    response = await harness.http.post(
        f"/api/admin/users/{USER}/ban",
        json={"banned": False},
        headers=await harness.session(MODERATOR),
    )
    assert response.status_code == 200
    assert await harness.scalar("SELECT bot_links_before FROM users WHERE user_id = ?", (USER,)) is None


async def test_admin_session_revoke_kills_links_and_a_newer_link_works(harness):
    old = _token(now=time.time() - 5)
    headers = await harness.session(ADMIN)
    headers |= confirm_header(ADMIN, "users.sessions_revoke", {"user_id": USER})
    response = await harness.http.post(
        f"/api/admin/users/{USER}/sessions/revoke", json={"user_id": USER}, headers=headers
    )
    assert response.status_code == 200, response.text
    assert (await _exchange(harness, old)).status_code == 401
    # The bot's next /start mints a link after the watermark: it works.
    fresh = _token(now=time.time() + 2)
    assert (await _exchange(harness, fresh)).status_code == 200


async def test_exchange_is_rate_limited(harness):
    limiter = app.state.limiter
    limiter.reset()
    limiter.enabled = True
    try:
        codes = [(await _exchange(harness, "forged")).status_code for _ in range(21)]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes[:20] == [401] * 20
    assert codes[20] == 429


async def test_m021_is_idempotent(tmp_path):
    from src.db.migrations import m021_bot_link_revocation

    path = tmp_path / "m021.sqlite3"
    async with aiosqlite.connect(path) as conn:
        await conn.execute("CREATE TABLE users (user_id INTEGER PRIMARY KEY)")
        await m021_bot_link_revocation.apply(conn)
        await m021_bot_link_revocation.apply(conn)  # re-applied: no-op
        cursor = await conn.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in await cursor.fetchall()]
    assert columns.count("bot_links_before") == 1


def test_module_does_not_import_webapp():
    source = open(webapp_link.__file__, encoding="utf-8").read()
    assert "import webapp" not in source and "from webapp" not in source
