from __future__ import annotations

from opsincident_collector.core.models import NormalizedDocument, SyncSummary


class ConsoleExporter:
    def export_documents(self, documents: list[NormalizedDocument], summary: SyncSummary) -> int:
        for document in documents[:10]:
            print(
                f"{document.relative_path} [{document.content_type}] "
                f"redacted={document.redaction.redacted_count}"
            )
        return 0
