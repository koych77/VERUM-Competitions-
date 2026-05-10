from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "VERUM Competitions"
    bot_token: str = Field("", alias="BOT_TOKEN")
    database_url: str = Field("sqlite:///./verum.db", alias="DATABASE_URL")
    webapp_url: str = Field("http://localhost:8000", alias="WEBAPP_URL")
    admin_ids: str = Field("", alias="ADMIN_IDS")
    telegram_init_data_ttl_seconds: int = Field(86400, alias="TELEGRAM_INIT_DATA_TTL_SECONDS")

    @property
    def admin_id_set(self) -> set[int]:
        ids: set[int] = set()
        for raw in self.admin_ids.split(","):
            raw = raw.strip()
            if raw.isdigit():
                ids.add(int(raw))
        return ids

    @property
    def frontend_dist(self) -> Path:
        return Path(__file__).resolve().parents[2] / "frontend" / "dist"

    @property
    def normalized_webapp_url(self) -> str:
        if self.webapp_url.startswith(("http://", "https://")):
            return self.webapp_url
        return f"https://{self.webapp_url}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
