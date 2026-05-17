from __future__ import annotations

PROMPTS = {
    "incidentops_investigate_latency": "Investigate latency using only evidence, cite sources, mention missing data, and avoid overstating confidence.",
    "incidentops_investigate_error_rate": "Investigate rising error rate using only evidence, cite sources, and call out missing data.",
    "incidentops_deploy_regression": "Check for deploy regressions and only conclude if evidence is strong.",
    "incidentops_missing_data_review": "Review available evidence and explicitly identify missing data before further conclusions.",
    "incidentops_generate_postmortem": "Generate a draft postmortem using only cited evidence and include unknowns.",
    "incidentops_prepare_source_sync": "Prepare a safe sync recommendation and ask approval before upload or external writes.",
}
