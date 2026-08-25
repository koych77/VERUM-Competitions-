from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "VERUM Competitions"
    app_env: str = Field("development", alias="APP_ENV")
    bot_token: str = Field("", alias="BOT_TOKEN")
    database_url: str = Field("sqlite:///./verum.db", alias="DATABASE_URL")
    webapp_url: str = Field("http://localhost:8000", alias="WEBAPP_URL")
    admin_ids: str = Field("", alias="ADMIN_IDS")
    telegram_init_data_ttl_seconds: int = Field(86400, alias="TELEGRAM_INIT_DATA_TTL_SECONDS")
    session_secret: str = Field("", alias="SESSION_SECRET")
    session_ttl_seconds: int = Field(43200, alias="SESSION_TTL_SECONDS")
    allow_dev_auth: bool = Field(False, alias="ALLOW_DEV_AUTH")
    allowed_origins: str = Field("", alias="ALLOWED_ORIGINS")
    railway_environment: str = Field("", alias="RAILWAY_ENVIRONMENT")

    @property
    def admin_id_set(self) -> set[int]:
        ids: set[int] = set()
        for raw in self.admin_ids.split(","):
            raw = raw.strip()
            if raw.isdigit():
                ids.add(int(raw))
        return ids

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production" or bool(self.railway_environment.strip())

    @property
    def session_signing_key(self) -> str:
        if self.session_secret:
            return self.session_secret
        if not self.is_production:
            return "verum-local-development-session-key"
        raise RuntimeError("SESSION_SECRET must be configured in production")

    @property
    def allowed_origin_list(self) -> list[str]:
        configured = [item.strip().rstrip("/") for item in self.allowed_origins.split(",") if item.strip()]
        if configured:
            return configured
        if self.is_production:
            return [self.normalized_webapp_url.rstrip("/")]
        return [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]

    def validate_runtime(self) -> None:
        if self.is_production and self.allow_dev_auth:
            raise RuntimeError("ALLOW_DEV_AUTH cannot be enabled in production")
        if self.is_production and len(self.session_signing_key) < 32:
            raise RuntimeError("SESSION_SECRET must contain at least 32 characters in production")

    @property
    def frontend_dist(self) -> Path:
        return Path(__file__).resolve().parents[2] / "frontend" / "dist"

    @property
    def upload_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "uploads"

    @property
    def normalized_webapp_url(self) -> str:
        value = self.webapp_url.strip()
        if value.startswith(("http://", "https://")):
            return value
        return f"https://{value}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
