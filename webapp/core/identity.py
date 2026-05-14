from typing import Any

from fastapi import Header

from webapp.core.telegram_auth import verify_webapp_init_data


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    return token or None


def resolve_user_id_from_init_data(init_data: str, bot_token: str) -> int | None:
    user_data = verify_webapp_init_data(init_data, bot_token)
    if not user_data or not user_data.get("id"):
        return None
    try:
        return int(user_data["id"])
    except (TypeError, ValueError):
        return None


def get_init_data_from_header(x_telegram_init_data: str | None = Header(default=None)) -> str:
    return (x_telegram_init_data or "").strip()
