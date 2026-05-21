# Architecture

This document explains the **deterministic collector architecture** used in OpsIncident-Collector and how it fits with IncidentOps Core.

## Design goals

- Keep collection deterministic and reproducible for the same repository state and config.
- Keep `NormalizedDocument` as the canonical collector output.
- Enforce allowlist/denylist path policy at discovery time.
- Redact secrets before preview, export, or sync.
- Keep collector responsibilities separate from IncidentOps Core responsibilities.

---

## System context diagram

```mermaid
flowchart LR
    Repo[(Target Repository)] --> Disc[Discovery Engine]
    Cfg[(Collector Config)] --> Disc

    Disc --> Filter[Path Policy + Filters]
    Filter --> Read[Safe File Reader]
    Read --> Meta[Metadata Extractor]
    Meta --> Redact[Secret Redaction]
    Redact --> ND[(NormalizedDocument)]

    ND --> LocalExport[Local Export]
    ND --> CoreSync[IncidentOps Core Sync Adapter]
    ND --> MCP[MCP Surface]

    CoreSync --> Core[(IncidentOps Core)]

    classDef core fill:#f8f8ff,stroke:#666,stroke-width:1px;
    classDef data fill:#f0fff4,stroke:#2f855a,stroke-width:1px;
    class ND data;
    class Core core;
```

### How to read this diagram

1. **Discovery** scans only configured roots and candidate paths.
2. **Path policy and filters** remove disallowed paths before file reads.
3. **Safe reader + metadata extractor** build deterministic document state.
4. **Redaction** sanitizes sensitive values prior to any outward boundary.
5. The resulting **`NormalizedDocument`** fans out to local export, Core sync, and MCP-facing responses.

---

## Responsibility boundary graph

```mermaid
flowchart TB
    subgraph Collector[OpsIncident-Collector]
      C1[Discovery]
      C2[Path Policy / Filters]
      C3[Secret Redaction]
      C4[Metadata Extraction]
      C5[NormalizedDocument Export + Sync Envelope]
      C6[Existing MCP Surface]
    end

    subgraph Core[IncidentOps Core]
      K1[Canonical Chunking]
      K2[Embeddings + Indexing]
      K3[Retrieval + Reranking]
      K4[Investigation + Answer Generation]
      K5[Citations + Workflow Runs + Eval Scoring]
    end

    C5 --> K1

    style Collector fill:#eef8ff,stroke:#2b6cb0,stroke-width:1px
    style Core fill:#fffaf0,stroke:#b7791f,stroke-width:1px
```

### Why this split matters

- Collector outputs remain portable and deterministic across environments.
- Core can evolve retrieval and reasoning independently without changing collection semantics.
- Security boundaries are cleaner: collector sanitizes inputs before any transfer.

---

## Deterministic collector pipeline (execution graph)

```mermaid
flowchart TD
    A[Start Collection Run] --> B[Load Config + Project Context]
    B --> C[Enumerate Candidate Paths]
    C --> D{Path Allowed?}
    D -- No --> D1[Skip + Audit Reason]
    D -- Yes --> E{File Matches Filters?}
    E -- No --> E1[Skip + Audit Reason]
    E -- Yes --> F[Read File]
    F --> G[Extract Metadata]
    G --> H[Normalize Structure]
    H --> I[Redact Secrets]
    I --> J[Build NormalizedDocument]
    J --> K[Emit to Boundary
(Local export / Core sync / MCP)]

    D1 --> L[Continue]
    E1 --> L
    K --> L
    L --> M{More Files?}
    M -- Yes --> D
    M -- No --> N[Finalize Run Summary]
```

### Determinism guarantees

- Input set is constrained by explicit roots and policies.
- Processing order is stable (path-based iteration).
- Transform stages are pure and reproducible for the same inputs.
- Secret handling happens before boundary emission.

---

## Data model map

```mermaid
classDiagram
    class NormalizedDocument {
      +source_path
      +content_type
      +normalized_text_or_structured_payload
      +metadata
      +redaction_summary
      +processing_flags
    }

    class ExportEnvelope {
      +protocol_metadata
      +transport_headers
      +sync_context
    }

    ExportEnvelope --> NormalizedDocument : wraps-at-boundary-only
```

### Data model notes

- `NormalizedDocument` is the canonical in-process and output model.
- Envelopes exist only at API/export boundaries and must not redefine canonical content.
- Metadata may include advisory hints for downstream systems, but not Core-owned canonical retrieval state.

---

## Security and policy path

```mermaid
sequenceDiagram
    participant Run as Collector Run
    participant Policy as Path Policy
    participant Reader as File Reader
    participant Redactor as Secret Redaction
    participant Boundary as Export/Preview/Sync

    Run->>Policy: Candidate path
    Policy-->>Run: allow / deny + reason
    alt denied
      Run->>Run: skip path, record safe audit
    else allowed
      Run->>Reader: read file
      Reader-->>Run: raw content + metadata
      Run->>Redactor: sanitize content
      Redactor-->>Run: redacted content + redaction summary
      Run->>Boundary: emit sanitized document only
    end
```

### Security invariants

- No raw secret value may pass boundary interfaces.
- No raw file content or token values should be logged.
- Denied paths remain unread and are tracked via safe audit metadata.

---

## Related docs

- `docs/config-reference.md` for collector configuration controls.
- `docs/security-model.md` for threat model and controls.
- `docs/core-integration.md` for Core sync contract and boundaries.
- `docs/mcp-server.md` for MCP-exposed operations.
- `docs/langgraph-agent.md` for local graph workflow behavior.
