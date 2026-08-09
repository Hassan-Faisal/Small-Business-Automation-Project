from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "WhatsApp AI Assistant"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "WhatsApp-first AI ordering assistant"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    DATABASE_URL: str
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_API_VERSION: str = "v21.0"
    META_TEST_RECIPIENT_PHONE: str = ""
    META_APP_SECRET: str = ""
    META_SIGNATURE_VERIFICATION_ENABLED: bool = True
    META_WABA_ID: str = ""
    META_WEBHOOK_PUBLIC_URL: str = ""
    WHATSAPP_WEBHOOK_SECRET: str = ""
    WHATSAPP_OUTBOUND_PROVIDER: Literal["twilio", "meta"] = "twilio"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_SIGNATURE_VERIFICATION_ENABLED: bool = True
    TWILIO_TRUST_FORWARDED_HEADERS: bool = False
    ADMIN_AUTH_SECRET: str = ""
    ADMIN_TOKEN_EXPIRE_MINUTES: int = 60
    ADMIN_COOKIE_SECURE: bool = True
    ADMIN_COOKIE_NAME: str = "tiffinai_admin"
    ADMIN_COOKIE_SAMESITE: str = "lax"
    BUSINESS_TIMEZONE: str = "Asia/Karachi"
    CART_INACTIVITY_MINUTES: int = 1440
    ADMIN_FRONTEND_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("ADMIN_TOKEN_EXPIRE_MINUTES")
    @classmethod
    def validate_admin_token_expiration(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ADMIN_TOKEN_EXPIRE_MINUTES must be greater than zero.")
        return value

    @field_validator("ADMIN_FRONTEND_ORIGINS")
    @classmethod
    def validate_admin_frontend_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        if any("*" in origin for origin in origins):
            raise ValueError("ADMIN_FRONTEND_ORIGINS must contain explicit origins, not '*'.")
        return ",".join(origins)

    @field_validator("ADMIN_COOKIE_SAMESITE")
    @classmethod
    def validate_admin_cookie_samesite(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("ADMIN_COOKIE_SAMESITE must be lax, strict, or none.")
        return normalized

    @property
    def admin_frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ADMIN_FRONTEND_ORIGINS.split(",") if origin.strip()]

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("DATABASE_URL is required.")

        database_url = str(value).strip()
        if not database_url:
            raise ValueError("DATABASE_URL is required.")

        if database_url.startswith("postgres://"):
            database_url = f"postgresql://{database_url[len('postgres://') :]}"

        if not database_url.startswith(("postgresql://", "postgresql+")):
            raise ValueError("DATABASE_URL must be a PostgreSQL SQLAlchemy URL.")

        return database_url


settings = Settings()
