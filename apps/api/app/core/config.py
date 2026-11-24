from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
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
    # Fernet (base64 de 32 bytes) e HMAC do sorteio. Gere com: make keys
    draw_encryption_key: str = "ZGV2LWluc2VjdXJlLWRyYXcta2V5LTAxMjM0NTY3ODk="
    draw_hmac_key: str = "dev-insecure-draw-hmac-key-0123456789"
    cookie_secure: bool = True
    cookie_domain: str | None = None

    google_client_id: str | None = None
    google_client_secret: str | None = None
    # Passa pelo proxy do front (mesma origem), para os cookies de sessão funcionarem.
    google_redirect_uri: str = "http://localhost:5173/api/v1/auth/google/callback"

    email_provider: Literal["console", "resend"] = "console"
    email_from: str = "Tirei Você! <nao-responda@tireivoce.com.br>"
    resend_api_key: str | None = None
    # SÓ PARA TESTE: contas nascem com e-mail confirmado (proibido em produção).
    auto_verify_emails: bool = False
    verify_email_ttl_hours: int = 24
    reset_password_ttl_minutes: int = 60

    # Web Push (VAPID). Gere com: make keys. Sem elas, o push fica desligado.
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_subject: str = "mailto:contato@tireivoce.com.br"

    # WhatsApp: sem provedor real por enquanto. "console" só registra no log (dev).
    whatsapp_provider: Literal["none", "console"] = "none"

    # LGPD: dados de grupos sem atividade são apagados depois deste prazo.
    retention_months: int = Field(default=12, ge=1)
    unverified_account_days: int = Field(default=30, ge=1)

    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.0

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg(cls, value: str) -> str:
        """Render/Railway entregam postgres:// ou postgresql://; o SQLAlchemy async quer asyncpg."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+asyncpg://" + value.removeprefix(prefix)
        return value

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.is_production:
            if self.jwt_secret.startswith("dev-insecure") or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET precisa ter pelo menos 32 caracteres em produção")
            if self.draw_encryption_key.startswith("ZGV2LWluc2VjdXJl"):
                raise ValueError("DRAW_ENCRYPTION_KEY precisa ser definido em produção")
            if self.draw_hmac_key.startswith("dev-insecure") or len(self.draw_hmac_key) < 32:
                raise ValueError("DRAW_HMAC_KEY precisa ter pelo menos 32 caracteres em produção")
            if self.email_provider == "resend" and not self.resend_api_key:
                raise ValueError("RESEND_API_KEY é obrigatório com EMAIL_PROVIDER=resend")
            if self.auto_verify_emails:
                raise ValueError("AUTO_VERIFY_EMAILS não pode ser usado em produção")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE precisa ser true em produção")
        return self

    @property
    def whatsapp_enabled(self) -> bool:
        return self.whatsapp_provider != "none"

    @property
    def push_enabled(self) -> bool:
        return bool(self.vapid_public_key and self.vapid_private_key)

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
