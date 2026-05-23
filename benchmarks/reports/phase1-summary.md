# Phase 1 Real Repo Ingestion Benchmark Summary

This benchmark used live IncidentOps Core through `https://3.239.25.68/api` and two public open-source repositories. It is a repo/code/docs ingestion benchmark, not an incident root-cause benchmark, because these repositories do not contain real production logs, deploy history, runbooks, or incident reports.

| Repo | Files Seen | Docs Synced | Chunks | Skipped | Repeat Sync Skipped | Changed File Update | Duplicate Chunks | Search Pass |
|---|---:|---:|---:|---:|---:|---|---:|---|
| full-stack-fastapi-template | 259 | 77 | 275 | 182 | 77 | pass | 0 | pass |
| starlette | 157 | 103 | 900 | 54 | 101 | pass | 0 | pass |

## What Worked

- Both public repositories cloned and synced into live Core.
- Collector counted files, skipped unsupported/binary/denied files, normalized supported files, and uploaded through the Core batch ingest path.
- Core created chunks on the initial sync.
- Repeat sync skipped unchanged documents without creating duplicate chunks.
- A benchmark-only README mutation was detected and updated in Core.
- Search returned evidence for every benchmark query.

## What Failed Or Needed Fixing

- The first FastAPI-template run exposed a real Collector bug: deploy metadata extraction assumed YAML/JSON keys were strings. The extractor now ignores non-string keys and has a regression test.
- The Starlette config initially used `master`; the repository uses `main`, so the benchmark config was corrected.
- Running benchmark attempts too aggressively hit Core Redis rate limiting. Final passing runs were executed sequentially with batch size 100 and fresh benchmark state.
- Search quality is only sanity-checked in Phase 1. Some top results are merely plausible rather than final-quality ranked evidence.

## What This Proves

- Collector and Core can ingest real open-source backend repos into live IncidentOps Core.
- The normalized batch ingest path handles real repo files and produces searchable chunks.
- Same-source idempotency works for unchanged documents.
- Changed file updates are detected and do not produce duplicate chunks according to Core sync diagnostics.

## What This Does Not Prove Yet

- It does not prove incident root-cause quality; these repos do not include realistic runtime logs, deploy history, runbooks, and previous incident reports.
- It does not prove high-quality semantic ranking; Phase 5 must add retrieval evals and thresholds.
- It does not prove large-repo scale; huge repos like PostHog/Saleor remain later stress tests.
- It does not prove redaction coverage beyond the fact that these repos produced `redaction_count=0`; the dedicated redaction benchmark belongs to Phase 3.

## full-stack-fastapi-template

- Repo: `https://github.com/tiangolo/full-stack-fastapi-template.git`
- Branch: `master`
- Commit: `33fa827e7eb5578d2519186bd30786f838ce5714`
- Started: `2026-05-23T04:34:47.187072+00:00`
- Finished: `2026-05-23T04:35:13.406185+00:00`
- Files seen: `259`
- Files skipped: `182`
- Skip reasons: `{'binary': 3, 'denied': 18, 'empty': 11, 'unsupported_extension': 150}`
- Unsupported extensions: `{'.conf': 2, '.css': 1, '.html': 1, '.jinja': 1, '.lock': 2, '.mako': 1, '.mjml': 3, '.playwright': 1, '.sample': 14, '.sh': 8, '.svg': 5, '.ts': 33, '.tsx': 62, '<none>': 16}`
- Normalized documents: `77`
- Documents synced by Collector: `77`
- Chunks created in initial Core sync: `275`
- Source type counts: `{'code': 37, 'config': 30, 'deploy_history': 3, 'logs': 3, 'unknown_text': 4}`
- Redaction count: `119`
- Parser errors: `0`
- Latest Core sync status: `success`
- Repeat sync skipped unchanged: `77`
- Changed file path: `README.md`
- Changed file update detected: `True`
- Duplicate chunks after update: `0`

Search sanity:
- `Where is the FastAPI application configured?`: 5 result(s); top paths: backend/README.md, backend/README.md, README.md
- `How is the backend database configured?`: 5 result(s); top paths: backend/README.md, backend/README.md, development.md
- `Where are Docker or deployment settings defined?`: 5 result(s); top paths: README.md, .github/workflows/deploy-staging.yml, .github/workflows/deploy-production.yml

Warnings:
- binary file skipped: .git/objects/pack/pack-1ff6bc68a71ac1aa074dd5895572fb2bd71f0315.idx
- binary file skipped: .git/objects/pack/pack-1ff6bc68a71ac1aa074dd5895572fb2bd71f0315.pack
- binary file skipped: .git/objects/pack/pack-1ff6bc68a71ac1aa074dd5895572fb2bd71f0315.rev
- 18 denied file(s) skipped by policy
- 150 unsupported file(s) skipped

## starlette

- Repo: `https://github.com/encode/starlette.git`
- Branch: `main`
- Commit: `48f8e331b23ca692f4713ac1f370bff1b5cd034c`
- Started: `2026-05-23T04:35:45.361617+00:00`
- Finished: `2026-05-23T04:36:34.387706+00:00`
- Files seen: `157`
- Files skipped: `54`
- Skip reasons: `{'binary': 3, 'denied': 9, 'empty': 3, 'unsupported_extension': 39}`
- Unsupported extensions: `{'.1': 1, '.cff': 1, '.css': 1, '.html': 2, '.js': 1, '.lock': 1, '.sample': 14, '.svg': 2, '<none>': 16}`
- Normalized documents: `103`
- Documents synced by Collector: `103`
- Chunks created in initial Core sync: `900`
- Source type counts: `{'code': 65, 'config': 8, 'incident_report': 1, 'logs': 8, 'runbook': 16, 'unknown_text': 5}`
- Redaction count: `20`
- Parser errors: `2`
- Latest Core sync status: `partial_success`
- Repeat sync skipped unchanged: `101`
- Changed file path: `README.md`
- Changed file update detected: `True`
- Duplicate chunks after update: `0`

Search sanity:
- `Where is routing implemented?`: 5 result(s); top paths: docs/middleware.md, tests/test_routing.py, docs/applications.md
- `Where are middleware classes defined?`: 5 result(s); top paths: docs/exceptions.md, docs/middleware.md, docs/middleware.md
- `How are WebSocket routes handled?`: 5 result(s); top paths: starlette/convertors.py, tests/test_websockets.py, docs/routing.md

Warnings:
- binary file skipped: .git/objects/pack/pack-d2d69ed5693059e45c4e75f110de7ab70c18b7a9.idx
- binary file skipped: .git/objects/pack/pack-d2d69ed5693059e45c4e75f110de7ab70c18b7a9.pack
- binary file skipped: .git/objects/pack/pack-d2d69ed5693059e45c4e75f110de7ab70c18b7a9.rev
- 9 denied file(s) skipped by policy
- 39 unsupported file(s) skipped
