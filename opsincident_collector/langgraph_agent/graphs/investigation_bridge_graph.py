from __future__ import annotations

from opsincident_collector.langgraph_agent.nodes.common import (
    approval_gate_node,
    call_core_investigate_node,
    check_core_health_node,
    compute_coverage_node,
    compute_rag_readiness_node,
    decide_if_sync_needed_node,
    get_core_capabilities_node,
    inspect_sources_node,
    load_config_node,
    sync_source_if_needed_node,
)
from opsincident_collector.langgraph_agent.nodes.summarize_result import (
    summarize_investigation_bridge_node,
)
from opsincident_collector.langgraph_agent.state import InvestigationBridgeState


NODES = [
    ("load_config", load_config_node),
    ("check_core_health", check_core_health_node),
    ("get_core_capabilities", get_core_capabilities_node),
    ("inspect_local_sources", inspect_sources_node),
    ("compute_coverage", compute_coverage_node),
    ("compute_rag_readiness", compute_rag_readiness_node),
    ("decide_if_sync_needed", decide_if_sync_needed_node),
    ("approval_gate", approval_gate_node),
    ("sync_source_if_needed", sync_source_if_needed_node),
    ("call_core_investigate", call_core_investigate_node),
    ("final_report", summarize_investigation_bridge_node),
]


def build_graph():
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(InvestigationBridgeState)
    for name, node in NODES:
        graph.add_node(name, node)
    graph.add_edge(START, NODES[0][0])
    for current, following in zip(NODES, NODES[1:]):
        graph.add_edge(current[0], following[0])
    graph.add_edge(NODES[-1][0], END)
    return graph.compile()
