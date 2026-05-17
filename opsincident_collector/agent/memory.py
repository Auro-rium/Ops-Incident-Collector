from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentMemory:
    inspected_sources: list[str] = field(default_factory=list)
    missing_data: list[str] = field(default_factory=list)
