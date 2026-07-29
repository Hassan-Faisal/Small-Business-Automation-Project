from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "WhatsApp AI Assistant"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "WhatsApp-first AI ordering assistant"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    DATABASE_URL: str = "sqlite:///./business.db"
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_API_VERSION: str = "v21.0"
    WHATSAPP_WEBHOOK_SECRET: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_SIGNATURE_VERIFICATION_ENABLED: bool = True
    TWILIO_TRUST_FORWARDED_HEADERS: bool = False

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str | None) -> str:
        if not value:
            return "sqlite:///./business.db"

        if not isinstance(value, str):
            return str(value)

        if value.startswith("sqlite:///./"):
            project_root = Path(__file__).resolve().parents[2]
            relative_path = value[len("sqlite:///./") :]
            resolved_path = (project_root / relative_path).resolve()
            return f"sqlite:///{resolved_path.as_posix()}"

        if value.startswith("sqlite:///") and value.count("://") == 1:
            return value

        return value


settings = Settings()
