"""Opaque public vacancy token used ONLY inside links.

A link such as ``https://t.me/<bot>?start=vacancy_hh_138492163`` shows the vacancy
source to anyone who looks at it. The token hides it: ``"v" + <source letter> +
<id in base36>`` (``hh_138492163`` -> ``vh2a3f9k``). It is reversible, carries
no secret and fits Telegram's ``start`` / ``startapp`` alphabet
(``[A-Za-z0-9_-]``, at most 64 chars).

The frontend mirrors this in ``webapp/frontend/src/lib/deepLink.ts``; keep the
letters in sync. The old ``vacancy_<uid>`` form is still accepted on input so
links in already-posted channel messages keep working.
"""
from __future__ import annotations

import re
from typing import Any

#: source name -> one-letter code (never reuse or change a letter: links live forever).
SOURCE_CODES: dict[str, str] = {"hh": "h", "osonish": "o", "vacancy_gov": "g"}
_CODE_SOURCES = {code: source for source, code in SOURCE_CODES.items()}

MAX_TOKEN_LEN = 64
_ID_RE = re.compile(r"[1-9][0-9]{0,17}")
_TOKEN_RE = re.compile(r"v([hog])([0-9a-z]{1,14})")
_UID_RE = re.compile(r"(osonish|hh|vacancy_gov)_([1-9][0-9]{0,17})")
_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def _to_base36(number: int) -> str:
    out = ""
    while number:
        number, rem = divmod(number, 36)
        out = _DIGITS[rem] + out
    return out or "0"


def encode_vacancy_token(uid: Any) -> str | None:
    """``"hh_138492163"`` -> ``"vh2a3f9k"``; ``None`` for an unknown uid shape."""
    match = _UID_RE.fullmatch(uid) if isinstance(uid, str) else None
    if match is None:
        return None
    return f"v{SOURCE_CODES[match.group(1)]}{_to_base36(int(match.group(2)))}"


def decode_vacancy_token(token: Any) -> str | None:
    """``"vh2a3f9k"`` -> ``"hh_138492163"``; ``None`` for anything that is not a token."""
    match = _TOKEN_RE.fullmatch(token) if isinstance(token, str) else None
    if match is None or len(token) > MAX_TOKEN_LEN:
        return None
    number = int(match.group(2), 36)
    if not _ID_RE.fullmatch(str(number)):
        return None
    return f"{_CODE_SOURCES[match.group(1)]}_{number}"


def uid_from_start_param(param: Any) -> str | None:
    """uid of a ``/start`` / ``?go=`` / ``startapp`` value, new token or old ``vacancy_<uid>``.

    ``None`` when the value is neither form (the caller decides what to answer).
    """
    if not isinstance(param, str) or not param or len(param) > MAX_TOKEN_LEN:
        return None
    if param.startswith("vacancy_"):
        uid = param[len("vacancy_"):]
        return uid if _UID_RE.fullmatch(uid) else None
    return decode_vacancy_token(param)

