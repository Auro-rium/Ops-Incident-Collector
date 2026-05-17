from __future__ import annotations

from opsincident_collector.langgraph_agent.nodes.common import (
    approval_gate_node,
    compute_coverage_node,
    compute_rag_readiness_node,
    inspect_sources_node,
    load_config_node,
    plan_sync_node,
    preview_redaction_summary_node,
    sync_source_node,
    validate_path_policy_node,
    verify_sync_node,
)
from opsincident_collector.langgraph_agent.nodes.summarize_result import (
    summarize_source_onboarding_node,
)
from opsincident_collector.langgraph_agent.state import SourceOnboardingState


NODES = [
    ("load_config", load_config_node),
    ("validate_path_policy", validate_path_policy_node),
    ("inspect_sources", inspect_sources_node),
    ("preview_redaction", preview_redaction_summary_node),
    ("compute_coverage", compute_coverage_node),
    ("compute_rag_readiness", compute_rag_readiness_node),
    ("plan_sync", plan_sync_node),
    ("approval_gate", approval_gate_node),
    ("sync_source", sync_source_node),
    ("verify_sync", verify_sync_node),
    ("final_report", summarize_source_onboarding_node),
]


def build_graph():
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(SourceOnboardingState)
    for name, node in NODES:
        graph.add_node(name, node)
    graph.add_edge(START, NODES[0][0])
    for current, following in zip(NODES, NODES[1:]):
        graph.add_edge(current[0], following[0])
    graph.add_edge(NODES[-1][0], END)
    return graph.compile()

