import hashlib
import hmac
import time
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
