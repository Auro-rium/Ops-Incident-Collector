from __future__ import annotations

from opsincident_collector.langgraph_agent.nodes.common import (
    compute_coverage_node,
    compute_rag_readiness_node,
    load_config_node,
    validate_path_policy_node,
    verify_sync_node,
)
from opsincident_collector.langgraph_agent.nodes.summarize_result import (
    summarize_sync_quality_node,
)
from opsincident_collector.langgraph_agent.state import SyncQualityState


NODES = [
    ("load_config", load_config_node),
    ("validate_path_policy", validate_path_policy_node),
    ("load_failed_upload_queue", verify_sync_node),
    ("compute_coverage", compute_coverage_node),
    ("compute_rag_readiness", compute_rag_readiness_node),
    ("final_report", summarize_sync_quality_node),
]


def build_graph():
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(SyncQualityState)
    for name, node in NODES:
        graph.add_node(name, node)
    graph.add_edge(START, NODES[0][0])
    for current, following in zip(NODES, NODES[1:]):
        graph.add_edge(current[0], following[0])
    graph.add_edge(NODES[-1][0], END)
    return graph.compile()

