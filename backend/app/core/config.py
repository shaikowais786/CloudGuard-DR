from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CloudGuard DR API"
    environment: str = "development"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://cloudguard:change-me@localhost:5432/cloudguard"
    jwt_secret_key: str = Field(default="", repr=False)
    jwt_access_token_minutes: int = Field(default=60, ge=1, le=1440)
    aws_credential_encryption_key: str = Field(default="", repr=False)
    aws_report_bucket_name: str = ""
    aws_region: str = "us-east-1"
    aws_report_presign_expires_seconds: int = Field(default=900, ge=60, le=3600)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    aws_connect_timeout_seconds: int = Field(default=5, ge=1, le=60)
    aws_read_timeout_seconds: int = Field(default=20, ge=1, le=120)

    @field_validator("api_prefix")
    @classmethod
    def normalize_prefix(cls, value: str) -> str:
        return "/" + value.strip("/")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def validate_secrets(self) -> None:
        if len(self.jwt_secret_key) < 32 or "replace-with" in self.jwt_secret_key.lower():
            raise RuntimeError("JWT_SECRET_KEY must be configured with at least 32 characters")
        if not self.aws_credential_encryption_key:
            raise RuntimeError("AWS_CREDENTIAL_ENCRYPTION_KEY must be configured before starting the API")
        try:
            Fernet(self.aws_credential_encryption_key.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise RuntimeError("AWS_CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key") from exc


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

