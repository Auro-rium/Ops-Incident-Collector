from __future__ import annotations

from typing import Protocol

from opsincident_collector.core.models import NormalizedDocument, SyncSummary


class Exporter(Protocol):
    def export_documents(self, documents: list[NormalizedDocument], summary: SyncSummary) -> int:
        ...
