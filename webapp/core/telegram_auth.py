import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any


def verify_webapp_init_data(init_data: str, bot_token: str) -> dict[str, Any] | None:
    """
    Verify Telegram.WebApp.initData and return parsed user dict if valid.

    Algorithm (per Telegram docs):
        secret_key = HMAC-SHA256(bot_token, "WebAppData")
        data_check_string = sorted key=value pairs (excl. hash), joined by \\n
        computed = hex(HMAC-SHA256(data_check_string, secret_key))
        valid if computed == hash
    """
    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    hash_value = parsed.pop("hash", "")
    if not hash_value:
        return None

    # 1. Verify signature FIRST — don't reveal anything until the signature is confirmed.
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, hash_value):
        return None

    # 2. Only after signature passes — check auth_date to prevent replay attacks.
    try:
        auth_date = int(parsed.get("auth_date", 0))
    except (TypeError, ValueError):
        return None

    # initData is generated fresh on each Mini App launch. 1 hour is generous
    # enough for any session re-auth while still blocking replayed credentials.
    if time.time() - auth_date > 3600:
        return None

    user_str = parsed.get("user", "{}")
    try:
        return json.loads(user_str)
    except (json.JSONDecodeError, TypeError):
        return None
