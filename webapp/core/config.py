import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_SECRETS = {"", "change-me"}

SECRET_ERROR_MESSAGE = (
    "WEBAPP_SECRET is missing or still set to the default 'change-me'. "
    "Every Mini App session token is signed with it, so the API refuses to start.\n"
    "Fix: add a strong random value to the .env file next to main.py, e.g.\n"
    "    WEBAPP_SECRET=$(python -c \"import secrets; print(secrets.token_urlsafe(48))\")\n"
    "On the server the .env is NOT synced by deploy_safe.sh — add the line by hand to "
    "/home/vakant/.env and restart vakant-api.\n"
    "For local development or tests you may instead export ALLOW_INSECURE_SECRET=1."
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    TOKEN: str = ""
    WEBAPP_SECRET: str = "change-me"
    BOT_USERNAME: str = ""
    ADMIN_IDS: str = ""
    WEBAPP_ORIGIN: str = "http://localhost:5173"
    SESSION_TTL_SECONDS: int = 30 * 24 * 60 * 60
    # Telegram initData replay window. It is minted fresh on every Mini App
    # launch, so 5 minutes is plenty for the one /auth/launch exchange.
    INIT_DATA_MAX_AGE: int = 300
    # Lifetime of an admin confirmation token (POST /api/admin/confirm).
    ADMIN_CONFIRM_TTL_SECONDS: int = 60

    @property
    def admin_ids_set(self) -> set[int]:
        ids: set[int] = set()
        for item in self.ADMIN_IDS.split(","):
            item = item.strip()
            if item.isdigit():
                ids.add(int(item))
        return ids


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = BASE_DIR / "src" / "database" / "database.sqlite3"
DB_PATH = Path(os.getenv("DB_PATH", str(DEFAULT_DB_PATH)))


def allow_insecure_secret() -> bool:
    return str(os.getenv("ALLOW_INSECURE_SECRET", "")).strip().lower() in {"1", "true", "yes"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    if settings.WEBAPP_SECRET.strip() in INSECURE_SECRETS and not allow_insecure_secret():
        raise RuntimeError(SECRET_ERROR_MESSAGE)
    return settings
