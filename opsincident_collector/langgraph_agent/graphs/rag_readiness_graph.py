from __future__ import annotations

from opsincident_collector.langgraph_agent.nodes.common import (
    compute_coverage_node,
    compute_rag_readiness_node,
    generate_eval_seed_preview_node,
    inspect_sources_node,
    load_config_node,
    validate_path_policy_node,
)
from opsincident_collector.langgraph_agent.nodes.summarize_result import (
    summarize_rag_readiness_node,
)
from opsincident_collector.langgraph_agent.state import RAGReadinessState


NODES = [
    ("load_config", load_config_node),
    ("validate_path_policy", validate_path_policy_node),
    ("inspect_sources", inspect_sources_node),
    ("compute_coverage", compute_coverage_node),
    ("compute_rag_readiness", compute_rag_readiness_node),
    ("generate_eval_seed_preview", generate_eval_seed_preview_node),
    ("final_report", summarize_rag_readiness_node),
]


def build_graph():
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(RAGReadinessState)
    for name, node in NODES:
        graph.add_node(name, node)
    graph.add_edge(START, NODES[0][0])
    for current, following in zip(NODES, NODES[1:]):
        graph.add_edge(current[0], following[0])
    graph.add_edge(NODES[-1][0], END)
    return graph.compile()

