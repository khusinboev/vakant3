from webapp.core.telegram_auth import verify_webapp_init_data


def resolve_user_id_from_init_data(init_data: str, bot_token: str) -> int | None:
    user_data = verify_webapp_init_data(init_data, bot_token)
    if not user_data or not user_data.get("id"):
        return None
    try:
        return int(user_data["id"])
    except (TypeError, ValueError):
        return None
