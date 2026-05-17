from __future__ import annotations

from pathlib import Path

from opsincident_collector.mcp_server.prompts import PROMPTS
from opsincident_collector.mcp_server.resources import get_resource_map
from opsincident_collector.mcp_server import tools as tool_impl


def create_fastmcp_server(config_path: Path | None = None):
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("OpsIncident-Collector", json_response=True)

    @server.tool()
    def inspect_folder(path: str, max_depth: int = 8) -> dict:
        return tool_impl.inspect_folder(path=path, max_depth=max_depth, config_path=str(config_path) if config_path else None)

    @server.tool()
    def validate_source_config(config_path_input: str) -> dict:
        return tool_impl.validate_source_config(config_path_input)

    @server.tool()
    def preview_redaction(path: str, max_lines: int = 100) -> dict:
        return tool_impl.preview_redaction(path=path, max_lines=max_lines, config_path=str(config_path) if config_path else None)

    @server.tool()
    def sync_source(path: str, project_id: str | None = None, source_name: str | None = None, export_target: str = "api", dry_run: bool = False, approved: bool = False, output: str | None = None) -> dict:
        return tool_impl.sync_source(
            path=path,
            project_id=project_id,
            source_name=source_name,
            export_target=export_target,
            dry_run=dry_run,
            approved=approved,
            output=output,
            config_path=str(config_path) if config_path else None,
        )

    @server.tool()
    def get_source_coverage(project_id: str) -> dict:
        return tool_impl.get_source_coverage(project_id=project_id, config_path=str(config_path) if config_path else None)

    @server.tool()
    def search_evidence(project_id: str, query: str, top_k: int = 10) -> dict:
        return tool_impl.search_evidence(project_id=project_id, query=query, top_k=top_k, config_path=str(config_path) if config_path else None)

    @server.tool()
    def investigate_incident(project_id: str, query: str, debug: bool = False) -> dict:
        return tool_impl.investigate_incident(project_id=project_id, query=query, debug=debug, config_path=str(config_path) if config_path else None)

    @server.tool()
    def create_workflow_run(project_id: str, query: str) -> dict:
        return tool_impl.create_workflow_run(project_id=project_id, query=query, config_path=str(config_path) if config_path else None)

    @server.tool()
    def get_run_status(run_id: str) -> dict:
        return tool_impl.get_run_status(run_id=run_id, config_path=str(config_path) if config_path else None)

    @server.tool()
    def get_run_events(run_id: str) -> dict:
        return tool_impl.get_run_events(run_id=run_id, config_path=str(config_path) if config_path else None)

    @server.tool()
    def export_report(run_id: str, format: str = "markdown") -> dict:
        return tool_impl.export_report(run_id=run_id, format=format, config_path=str(config_path) if config_path else None)

    def _make_resource(value):
        def _resource():
            return value
        return _resource

    for uri, value in get_resource_map(config_path).items():
        server.resource(uri)(_make_resource(value))

    def _make_prompt(prompt_text):
        def _prompt():
            return prompt_text
        return _prompt

    for prompt_name, prompt_text in PROMPTS.items():
        server.prompt(name=prompt_name)(_make_prompt(prompt_text))

    return server
