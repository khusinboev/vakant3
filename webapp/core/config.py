from functools import lru_cache
import warnings
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    TOKEN: str = ""
    WEBAPP_SECRET: str = "change-me"
    BOT_USERNAME: str = ""
    ADMIN_IDS: str = ""
    WEBAPP_ORIGIN: str = "http://localhost:5173"
    SESSION_TTL_SECONDS: int = 30 * 24 * 60 * 60

    @property
    def admin_ids_set(self) -> set[int]:
        ids: set[int] = set()
        for item in self.ADMIN_IDS.split(","):
            item = item.strip()
            if item.isdigit():
                ids.add(int(item))
        return ids

    @field_validator("WEBAPP_SECRET")
    @classmethod
    def secret_must_be_set(cls, v: str) -> str:
        if v == "change-me":
            warnings.warn(
                "WEBAPP_SECRET is set to the default 'change-me' value. "
                "Set a strong random secret in .env to secure all JWT sessions.",
                stacklevel=2,
            )
        return v


BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "src" / "database" / "database.sqlite3"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
