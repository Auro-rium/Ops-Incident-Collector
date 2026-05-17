# Security Model

- Only allowlisted paths may be inspected.
- Default deny patterns block secrets, binaries, and build artifacts.
- Inspect mode never uploads data.
- Secret detection reports counts only and never logs raw values.
- Secret redaction runs before JSONL, SQLite, API upload, and redaction preview output.
- API tokens are read from environment variables and are reported only as present or missing.
- Failed upload queue payloads contain already-redacted `NormalizedDocument` data.
- API watch mode requires `--yes` before the first upload attempt unless it is a dry run.
