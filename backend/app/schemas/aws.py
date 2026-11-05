from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AWSConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: UUID
    account_name: str = Field(min_length=1, max_length=160)
    access_key: str = Field(min_length=16, max_length=128, repr=False)
    secret_key: str = Field(min_length=32, max_length=256, repr=False)
    region: str = Field(min_length=3, max_length=64)

    @field_validator("region")
    @classmethod
    def normalize_region(cls, value: str) -> str:
        return value.strip().lower()


class ScanStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: UUID
    account_id: UUID | None = None
    region: str | None = Field(default=None, min_length=3, max_length=64)

    @field_validator("region")
    @classmethod
    def normalize_region(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else None

