from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    frontend_url: str = "http://localhost:5173"

    database_url: str = "postgresql+asyncpg://tirei:tirei@localhost:5432/tirei_voce"
    db_pool_size: int = Field(default=10, ge=1)
    db_max_overflow: int = Field(default=10, ge=0)
    redis_url: str = "redis://localhost:6379/0"

    # Segredos: os defaults só servem para dev/test; em produção é obrigatório definir.
    jwt_secret: str = "dev-insecure-jwt-secret-change-me-0123456789"  # noqa: S105
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    cookie_secure: bool = True
    cookie_domain: str | None = None

    email_provider: Literal["console", "resend"] = "console"
    email_from: str = "Tirei Você! <nao-responda@tireivoce.com.br>"
    resend_api_key: str | None = None
    verify_email_ttl_hours: int = 24
    reset_password_ttl_minutes: int = 60

    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.0

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.is_production:
            if self.jwt_secret.startswith("dev-insecure") or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET precisa ter pelo menos 32 caracteres em produção")
            if self.email_provider == "resend" and not self.resend_api_key:
                raise ValueError("RESEND_API_KEY é obrigatório com EMAIL_PROVIDER=resend")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE precisa ser true em produção")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
