# Collector Philosophy

OpsIncident Collector is not an AI investigator.

It is a policy-enforced edge runtime that turns private engineering data into safe, versioned, Core-compatible evidence for production RAG and incident investigation.

## First principle

```text
raw private engineering data
  -> explicit path policy
  -> file safety filters
  -> secret redaction
  -> metadata extraction
  -> NormalizedDocument
  -> local export / Core sync
  -> Core RAG and investigation
```

The Collector exists because most RAG systems fail before retrieval begins. They ingest the wrong files, leak secrets, lose source context, duplicate stale content, or pretend weak evidence is strong.

Collector fixes the input boundary.

## The trust boundary

The Collector runs near sensitive data:

- repositories
- logs
- runbooks
- deploy history
- incident reports
- API specs
- patches and diffs
- config files

That makes it a trust boundary, not a crawler. It must never roam arbitrary paths or upload raw private data because an agent thought it looked useful. Tiny detail, occasionally important to security teams.

## What Collector owns

Collector owns deterministic evidence preparation:

- source discovery
- path allowlist and denylist enforcement
- file type, size, binary, and emptiness checks
- secret redaction before every outward boundary
- metadata extraction
- stable `NormalizedDocument` creation
- local JSONL/SQLite/console export
- IncidentOps Core sync
- failed upload queue and retry/backoff
- source coverage and RAG readiness reporting
- LangGraph orchestration for onboarding, readiness, sync approval, and Core bridging
- daemon health, metrics, and server operations

## What Core owns

IncidentOps Core owns intelligence and canonical RAG behavior:

- document chunking
- embeddings
- vector and lexical indexing
- retrieval
- reranking
- investigation logic
- root-cause hypotheses
- answer generation
- citations
- workflow runs
- eval scoring

Collector must call Core for investigation. If Core is unavailable, Collector may report readiness and missing data, but it must not invent root cause.

## Determinism before agents

The deterministic pipeline is the foundation.

Agents may ask the Collector to inspect, preview redaction, plan sync, or call Core through LangGraph workflows. They do not get unrestricted file access. LangGraph workflows call deterministic Collector functions and Core adapters; they do not replace the pipeline.

Correct:

```text
LangGraph node -> deterministic inspect/sync/readiness function
CLI/agent command -> path policy -> Collector pipeline or Core adapter
```

Wrong:

```text
Agent reads arbitrary files
Agent diagnoses from raw logs locally
Agent uploads without approval
Agent bypasses Core because it feels confident
```

Confidence is not a security model. Annoying, but true.

## `NormalizedDocument` is the canonical contract

`NormalizedDocument` is the stable boundary object between Collector and Core.

It carries:

- source identity
- source type
- external ID
- path and relative path
- redacted content
- content type
- checksum/content hash
- size and modified time
- metadata
- redaction summary
- protocol/schema version envelope

Collector may add citation hints, chunking hints, endpoint candidates, deploy hashes, timestamps, trace IDs, headings, and other metadata. These are advisory. Core may use, refine, or ignore them.

## Redaction before serialization

Secrets must be redacted before:

- JSONL export
- SQLite export
- Core API upload
- failed upload queue payload storage
- graph checkpoint state
- audit events containing summaries

The failed upload queue must never become a secret graveyard with better retry logic.

## Honest failure is a product feature

Collector should fail clearly when:

- a path is not allowlisted
- a file is denied
- a token is missing
- Core is unavailable
- Core lacks compatible ingestion
- no useful files are found
- evidence coverage is weak

Fake success poisons downstream trust. A good Collector says what it saw, what it skipped, what it redacted, what it exported, what failed, and what should happen next.

## Design laws

1. Never trust raw data.
2. Never leak secrets.
3. Never diagnose locally.
4. Never bypass Core for investigation.
5. Never pretend weak evidence is strong.
6. Never let agents roam arbitrary paths.
7. Always normalize.
8. Always version.
9. Always audit.
10. Always fail honestly.

That is the system philosophy. Everything else is YAML with consequences.
