from __future__ import annotations

import json
from typing import Any


def graph_report_to_markdown(state: dict[str, Any]) -> str:
    report = state.get("final_report") or {}
    title = str(report.get("type") or "graph_report").replace("_", " ").title()
    lines = [
        f"# {title}",
        "",
        f"Status: `{state.get('status', 'unknown')}`",
        "",
        "Collector did not diagnose locally. Core remains the investigation brain.",
        "",
    ]
    if report.get("path"):
        lines.append(f"Path: `{report['path']}`")
    if report.get("project_id"):
        lines.append(f"Project: `{report['project_id']}`")
    if report.get("readiness_score") is not None:
        lines.append(f"Readiness score: `{report['readiness_score']}`")
    if report.get("sync_decision"):
        lines.append(f"Sync decision: `{report['sync_decision'].get('decision')}`")
    if report.get("missing_data"):
        lines.append("")
        lines.append("Missing data:")
        for item in report["missing_data"]:
            lines.append(f"- {item}")
    if report.get("next_steps"):
        lines.append("")
        lines.append("Next steps:")
        for item in report["next_steps"]:
            lines.append(f"- {item}")
    lines.extend(["", "```json", json.dumps(report, indent=2, default=str), "```"])
    return "\n".join(lines)
