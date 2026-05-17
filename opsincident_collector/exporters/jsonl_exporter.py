from __future__ import annotations

from pathlib import Path

from opsincident_collector.core.models import NormalizedDocument, NormalizedDocumentEnvelope, SyncSummary


class JSONLExporter:
    def __init__(self, output_path: Path, envelope: bool = True) -> None:
        self.output_path = output_path
        self.envelope = envelope
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def export_documents(self, documents: list[NormalizedDocument], summary: SyncSummary) -> int:
        bytes_written = 0
        with self.output_path.open("a", encoding="utf-8") as handle:
            for document in documents:
                if self.envelope:
                    line = NormalizedDocumentEnvelope(document=document).model_dump_json()
                else:
                    line = document.model_dump_json()
                handle.write(line + "\n")
                bytes_written += len((line + "\n").encode("utf-8"))
        return bytes_written
