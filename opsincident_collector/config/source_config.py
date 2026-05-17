from __future__ import annotations

from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    name: str
    type: str = "filesystem"
    path: str
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
