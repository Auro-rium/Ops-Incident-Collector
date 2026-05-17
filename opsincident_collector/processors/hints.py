from __future__ import annotations

import ast
import re
from pathlib import Path

from opsincident_collector.core.models import ChunkingHint, CitationHint

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
IMPORTANT_LOG_RE = re.compile(r"\b(ERROR|WARN|WARNING|CRITICAL)\b")


def build_document_hints(
    *,
    path: Path,
    relative_path: str,
    content: str,
    detected_type: str,
) -> tuple[list[dict], list[dict]]:
    if detected_type in {"runbook", "unknown_text"} and path.suffix.lower() in {".md", ".txt"}:
        return _markdown_hints(relative_path, content, hint_type="markdown_section")
    if detected_type == "incident_report":
        return _markdown_hints(relative_path, content, hint_type="incident_section")
    if detected_type == "logs":
        return _log_hints(relative_path, content)
    if detected_type == "code":
        return _code_hints(relative_path, content, path.suffix.lower())
    if detected_type == "deploy_history":
        return _whole_file_hint(relative_path, content, "deploy record", "deploy_record", "high")
    if detected_type == "patch":
        return _whole_file_hint(relative_path, content, "patch file change", "patch_file_change", "medium")
    if detected_type == "api_doc":
        return _api_hints(relative_path, content)
    if detected_type == "config":
        return _whole_file_hint(relative_path, content, "configuration block", "config_block", "low")
    return _whole_file_hint(relative_path, content, "document", "text_block", "low")


def _line_count(content: str) -> int:
    return max(len(content.splitlines()), 1)


def _whole_file_hint(
    relative_path: str,
    content: str,
    label: str,
    hint_type: str,
    priority: str,
) -> tuple[list[dict], list[dict]]:
    end_line = _line_count(content)
    citation = CitationHint(
        path=relative_path,
        relative_path=relative_path,
        start_line=1,
        end_line=end_line,
        label=label,
        reason="fallback whole-file citation hint",
        confidence=0.5,
    )
    chunk = ChunkingHint(
        type=hint_type,
        start_line=1,
        end_line=end_line,
        priority=priority,
        reason="fallback whole-file chunking hint",
        metadata={},
    )
    return [citation.model_dump(mode="json")], [chunk.model_dump(mode="json")]


def _markdown_hints(
    relative_path: str,
    content: str,
    hint_type: str,
) -> tuple[list[dict], list[dict]]:
    lines = content.splitlines()
    headings: list[tuple[int, str]] = []
    for index, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if match:
            headings.append((index, match.group(2).strip()))
    if not headings:
        return _whole_file_hint(relative_path, content, "markdown document", hint_type, "medium")

    citations: list[dict] = []
    chunks: list[dict] = []
    for idx, (start_line, title) in enumerate(headings):
        end_line = headings[idx + 1][0] - 1 if idx + 1 < len(headings) else max(len(lines), start_line)
        priority = "high" if title.lower() in {"summary", "timeline", "root cause", "resolution"} else "medium"
        citations.append(
            CitationHint(
                path=relative_path,
                relative_path=relative_path,
                start_line=start_line,
                end_line=end_line,
                label=title,
                reason="markdown heading section",
                confidence=0.85,
            ).model_dump(mode="json")
        )
        chunks.append(
            ChunkingHint(
                type=hint_type,
                start_line=start_line,
                end_line=end_line,
                priority=priority,
                reason="heading-delimited section",
                metadata={"heading": title},
            ).model_dump(mode="json")
        )
    return citations, chunks


def _log_hints(relative_path: str, content: str) -> tuple[list[dict], list[dict]]:
    lines = content.splitlines()
    citations: list[dict] = []
    chunks: list[dict] = []
    for index, line in enumerate(lines, start=1):
        match = IMPORTANT_LOG_RE.search(line)
        if not match:
            continue
        start_line = max(index - 2, 1)
        end_line = min(index + 2, len(lines))
        level = match.group(1)
        citations.append(
            CitationHint(
                path=relative_path,
                relative_path=relative_path,
                start_line=start_line,
                end_line=end_line,
                label=f"{level} near line {index}",
                reason="important log line window",
                confidence=0.8,
            ).model_dump(mode="json")
        )
        chunks.append(
            ChunkingHint(
                type="log_window",
                start_line=start_line,
                end_line=end_line,
                priority="high",
                reason="window around error or warning log line",
                metadata={"log_level": level, "center_line": index},
            ).model_dump(mode="json")
        )
    if citations:
        return citations, chunks
    return _whole_file_hint(relative_path, content, "log file", "log_window", "medium")


def _code_hints(relative_path: str, content: str, suffix: str) -> tuple[list[dict], list[dict]]:
    if suffix != ".py":
        return _whole_file_hint(relative_path, content, "code file", "code_function", "medium")
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return _whole_file_hint(relative_path, content, "code file", "code_function", "medium")

    citations: list[dict] = []
    chunks: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start_line = getattr(node, "lineno", None)
        end_line = getattr(node, "end_lineno", start_line)
        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        citations.append(
            CitationHint(
                path=relative_path,
                relative_path=relative_path,
                start_line=start_line,
                end_line=end_line,
                label=f"{kind} {node.name}",
                reason="python AST definition range",
                confidence=0.9,
            ).model_dump(mode="json")
        )
        chunks.append(
            ChunkingHint(
                type="code_function",
                start_line=start_line,
                end_line=end_line,
                priority="high",
                reason="python AST definition range",
                metadata={"symbol": node.name, "kind": kind},
            ).model_dump(mode="json")
        )
    if citations:
        return citations, chunks
    return _whole_file_hint(relative_path, content, "code file", "code_function", "medium")


def _api_hints(relative_path: str, content: str) -> tuple[list[dict], list[dict]]:
    lines = content.splitlines()
    citations: list[dict] = []
    chunks: list[dict] = []
    for index, line in enumerate(lines, start=1):
        match = re.match(r"\s{0,8}(/[A-Za-z0-9_\-/.{}]+):", line)
        if not match:
            continue
        endpoint = match.group(1)
        end_line = min(index + 8, len(lines))
        citations.append(
            CitationHint(
                path=relative_path,
                relative_path=relative_path,
                start_line=index,
                end_line=end_line,
                label=endpoint,
                reason="API path definition",
                confidence=0.8,
            ).model_dump(mode="json")
        )
        chunks.append(
            ChunkingHint(
                type="api_endpoint",
                start_line=index,
                end_line=end_line,
                priority="medium",
                reason="API endpoint block",
                metadata={"endpoint": endpoint},
            ).model_dump(mode="json")
        )
    if citations:
        return citations, chunks
    return _whole_file_hint(relative_path, content, "api document", "api_endpoint", "medium")
