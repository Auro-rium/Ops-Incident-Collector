from __future__ import annotations

import json
from pathlib import Path

from opsincident_collector.config.settings import AppSettings
from opsincident_collector.core.limits import DEFAULT_MAX_FILE_SIZE_MB
from opsincident_collector.core.models import (
    EvalSeedCase,
    NormalizedDocument,
    RAGReadinessReport,
    SourceCoverageReport,
)
from opsincident_collector.core.pipeline import _read_raw_document, inspect_source
from opsincident_collector.processors.file_filter import is_binary_file, is_supported_extension
from opsincident_collector.processors.normalizer import normalize_document
from opsincident_collector.processors.path_policy import ensure_path_allowed, is_denied_path
from opsincident_collector.receivers.filesystem import discover_files


def collect_normalized_documents(
    path: Path,
    settings: AppSettings,
    *,
    source_name: str | None = None,
    source_type: str = "filesystem",
    max_depth: int = 8,
) -> list[NormalizedDocument]:
    ensure_path_allowed(path.resolve(), settings.security.allow_paths)
    max_bytes = (settings.sync.max_file_size_mb or DEFAULT_MAX_FILE_SIZE_MB) * 1024 * 1024
    documents: list[NormalizedDocument] = []
    for item in discover_files(path, max_depth=max_depth):
        if is_denied_path(item.relative_path, settings.security.deny_patterns):
            continue
        if item.size_bytes == 0 or item.size_bytes > max_bytes:
            continue
        if is_binary_file(item.path) or not is_supported_extension(item.extension):
            continue
        raw = _read_raw_document(item)
        documents.append(
            normalize_document(
                raw_document=raw,
                source_name=source_name or path.name,
                source_type=source_type,
                redact_secrets=settings.security.redact_secrets,
            )
        )
    return documents


def build_source_coverage_report(
    path: Path,
    settings: AppSettings,
    *,
    max_depth: int = 8,
) -> SourceCoverageReport:
    inspection = inspect_source(path=path, settings=settings, max_depth=max_depth)
    counts = dict(inspection.likely_source_types)
    has_logs = counts.get("logs", 0) > 0
    has_code = counts.get("code", 0) > 0
    has_deploys = counts.get("deploy_history", 0) > 0 or counts.get("deploy", 0) > 0
    has_incidents = counts.get("incident_report", 0) > 0 or counts.get("incident", 0) > 0
    has_runbooks = counts.get("runbook", 0) > 0
    has_api_docs = counts.get("api_doc", 0) > 0

    warnings: list[str] = list(inspection.warnings)
    missing: list[str] = []
    if not has_logs:
        warnings.append("No logs found. Runtime incident investigation may be weak.")
        missing.append("logs")
    if not has_code:
        warnings.append("No code found. Root-cause mapping to implementation may be weak.")
        missing.append("code")
    if not has_deploys:
        warnings.append("No deploy history found. Deploy-regression investigation may be weak.")
        missing.append("deploy_history")
    if not has_incidents:
        warnings.append("No incident reports found. Previous-incident lookup unavailable.")
        missing.append("incidents")
    if not has_runbooks:
        warnings.append("No runbooks found. Suggested remediation may be generic.")
        missing.append("runbooks")
    if not has_api_docs:
        warnings.append("No API docs found. Endpoint-aware investigation may be limited.")
        missing.append("api_docs")

    return SourceCoverageReport(
        has_logs=has_logs,
        has_code=has_code,
        has_deploys=has_deploys,
        has_incidents=has_incidents,
        has_runbooks=has_runbooks,
        has_api_docs=has_api_docs,
        source_type_counts=counts,
        document_count=inspection.supported_files,
        warning_count=len(warnings),
        warnings=warnings,
        missing_recommended_sources=missing,
    )


def build_rag_readiness_report(
    path: Path,
    settings: AppSettings,
    *,
    max_depth: int = 8,
) -> RAGReadinessReport:
    coverage = build_source_coverage_report(path, settings, max_depth=max_depth)
    documents = collect_normalized_documents(path, settings, max_depth=max_depth)
    score = 0.0
    score += 0.20 if coverage.has_logs else 0.0
    score += 0.20 if coverage.has_code else 0.0
    score += 0.15 if coverage.has_deploys else 0.0
    score += 0.15 if coverage.has_incidents else 0.0
    score += 0.10 if coverage.has_runbooks else 0.0
    score += 0.05 if coverage.has_api_docs else 0.0
    useful_hints = any(
        document.metadata.get("citation_hints") or document.metadata.get("chunking_hints")
        for document in documents
    )
    score += 0.15 if useful_hints else 0.0
    score = min(round(score, 2), 1.0)

    if score >= 0.8:
        grade = "strong"
    elif score >= 0.6:
        grade = "usable"
    elif score >= 0.35:
        grade = "weak"
    else:
        grade = "poor"

    strengths = []
    for label, present in {
        "logs": coverage.has_logs,
        "code": coverage.has_code,
        "deploy history": coverage.has_deploys,
        "incident reports": coverage.has_incidents,
        "runbooks": coverage.has_runbooks,
        "API docs": coverage.has_api_docs,
        "metadata and hints": useful_hints,
    }.items():
        if present:
            strengths.append(f"{label} available")

    weaknesses = list(coverage.warnings)
    metadata_rich_documents = sum(
        1
        for document in documents
        if len(document.metadata.keys()) >= 5
        and (document.metadata.get("citation_hints") or document.metadata.get("chunking_hints"))
    )
    if metadata_rich_documents >= max(len(documents) // 2, 1):
        metadata_quality = "strong"
    elif metadata_rich_documents:
        metadata_quality = "usable"
    else:
        metadata_quality = "weak"

    return RAGReadinessReport(
        score=score,
        grade=grade,
        ready_for_core_sync=coverage.document_count > 0,
        ready_for_investigation=score >= 0.6,
        strengths=strengths,
        weaknesses=weaknesses,
        recommended_next_sources=coverage.missing_recommended_sources,
        coverage=coverage,
        estimated_document_count=coverage.document_count,
        estimated_metadata_quality=metadata_quality,
    )


def generate_eval_seed_cases(
    path: Path,
    settings: AppSettings,
    *,
    max_depth: int = 8,
) -> list[EvalSeedCase]:
    documents = collect_normalized_documents(path, settings, max_depth=max_depth)
    by_type: dict[str, list[NormalizedDocument]] = {}
    for document in documents:
        by_type.setdefault(document.content_type, []).append(document)

    cases: list[EvalSeedCase] = []
    _add_case(
        cases,
        by_type,
        source_type="logs",
        question="What errors or warnings appear in the logs?",
        terms=_terms_for_logs(by_type.get("logs", [])),
    )
    _add_case(
        cases,
        by_type,
        source_type="deploy_history",
        question="What deploys or commit hashes are present?",
        terms=_terms_from_metadata(by_type.get("deploy_history", []), ["deploy_hashes", "commit_shas", "commit_sha"]),
    )
    _add_case(
        cases,
        by_type,
        source_type="incident_report",
        question="What previous incidents are documented?",
        terms=_incident_terms(by_type.get("incident_report", [])),
    )
    _add_case(
        cases,
        by_type,
        source_type="runbook",
        question="What remediation steps are documented?",
        terms=_heading_terms(by_type.get("runbook", [])),
    )
    _add_case(
        cases,
        by_type,
        source_type="api_doc",
        question="What API endpoints are documented?",
        terms=_terms_from_metadata(by_type.get("api_doc", []), ["api_paths", "endpoints"]),
    )
    return cases


def write_eval_seed_jsonl(cases: list[EvalSeedCase], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(case.model_dump_json() + "\n")


def _add_case(
    cases: list[EvalSeedCase],
    grouped: dict[str, list[NormalizedDocument]],
    *,
    source_type: str,
    question: str,
    terms: list[str],
) -> None:
    docs = grouped.get(source_type, [])
    if not docs:
        return
    case_id = f"seed_{source_type}_{len(cases) + 1}"
    cases.append(
        EvalSeedCase(
            id=case_id,
            question=question,
            expected_documents=sorted(document.relative_path or document.path for document in docs),
            expected_terms=terms[:20],
            forbidden_terms=["[REDACTED_SECRET]"],
            source_type=source_type,
            difficulty="easy",
            notes="deterministic seed generated from local normalized documents",
        )
    )


def _terms_for_logs(documents: list[NormalizedDocument]) -> list[str]:
    terms: set[str] = set()
    for document in documents:
        terms.update(str(level) for level in document.metadata.get("log_levels", []))
        if "timeout" in document.content.lower():
            terms.add("timeout")
    return sorted(terms)


def _terms_from_metadata(documents: list[NormalizedDocument], keys: list[str]) -> list[str]:
    terms: set[str] = set()
    for document in documents:
        for key in keys:
            value = document.metadata.get(key)
            if isinstance(value, list):
                terms.update(str(item) for item in value)
            elif value:
                terms.add(str(value))
    return sorted(terms)


def _incident_terms(documents: list[NormalizedDocument]) -> list[str]:
    terms = set(_heading_terms(documents))
    for document in documents:
        lowered = document.content.lower()
        for token in ("root cause", "resolution", "summary", "timeline", "severity"):
            if token in lowered:
                terms.add(token)
    return sorted(terms)


def _heading_terms(documents: list[NormalizedDocument]) -> list[str]:
    terms: set[str] = set()
    for document in documents:
        for heading in document.metadata.get("headings", []):
            terms.add(str(heading))
    return sorted(terms)


def report_to_pretty_json(value) -> str:
    return json.dumps(value.model_dump(mode="json"), indent=2)
