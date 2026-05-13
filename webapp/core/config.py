from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    TOKEN: str = ""
    WEBAPP_SECRET: str = "change-me"
    BOT_USERNAME: str = ""
    WEBAPP_ORIGIN: str = "http://localhost:5173"
    SESSION_TTL_SECONDS: int = 30 * 24 * 60 * 60


BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "src" / "database" / "database.sqlite3"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
