from __future__ import annotations

from pydantic import BaseModel, Field


class CoreCapabilities(BaseModel):
    version: str | None = None
    features: dict[str, bool] = Field(default_factory=dict)
    limits: dict[str, int] = Field(default_factory=dict)
    endpoints: dict[str, str] = Field(default_factory=dict)


class SourceRegistrationResult(BaseModel):
    source_id: str
    raw: dict
