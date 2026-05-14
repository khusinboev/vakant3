import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any


def verify_telegram_login(data: dict[str, Any], bot_token: str) -> bool:
    """Telegram Login Widget HMAC-SHA256 verification."""
    incoming = dict(data)
    check_hash = incoming.pop("hash", "")
    if not check_hash:
        return False

    try:
        auth_date = int(incoming.get("auth_date", 0))
    except (TypeError, ValueError):
        return False

    # Telegram data should be used shortly after sign-in.
    if time.time() - auth_date > 3600:
        return False

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(incoming.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed_hash, check_hash)


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

    try:
        auth_date = int(parsed.get("auth_date", 0))
    except (TypeError, ValueError):
        return None

    # Reject data older than 24 hours.
    if time.time() - auth_date > 86400:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, hash_value):
        return None

    user_str = parsed.get("user", "{}")
    try:
        return json.loads(user_str)
    except (json.JSONDecodeError, TypeError):
        return None
