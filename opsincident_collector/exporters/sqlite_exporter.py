from __future__ import annotations

from pathlib import Path

from opsincident_collector.core.models import NormalizedDocument, SyncSummary
from opsincident_collector.state.sqlite_store import SQLiteStore


class SQLiteExporter:
    def __init__(self, output_path: Path) -> None:
        self.store = SQLiteStore(output_path)

    def export_documents(self, documents: list[NormalizedDocument], summary: SyncSummary) -> int:
        for document in documents:
            self.store.save_normalized_document(document)
        self.store.record_sync_run(summary, status="completed")
        return sum(document.size_bytes for document in documents)
