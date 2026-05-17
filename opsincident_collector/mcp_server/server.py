from __future__ import annotations

from pathlib import Path

from opsincident_collector.mcp_server.prompt_loader import load_all_prompts
from opsincident_collector.mcp_server import resources as resource_impl
from opsincident_collector.mcp_server import tools as tool_impl


def create_fastmcp_server(config_path: Path | None = None):
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("OpsIncident-Collector", json_response=True)
    config_str = str(config_path) if config_path else None

    @server.tool()
    def inspect_folder(path: str, max_depth: int = 8, format: str = "json") -> dict:
        return tool_impl.inspect_folder(
            path=path,
            max_depth=max_depth,
            format=format,
            config_path=config_str,
        )

    @server.tool()
    def validate_source_config(config_path_input: str) -> dict:
        return tool_impl.validate_source_config(config_path_input)

    @server.tool()
    def preview_redaction(path: str, max_lines: int = 100) -> dict:
        return tool_impl.preview_redaction(path=path, max_lines=max_lines, config_path=config_str)

    @server.tool()
    def sync_source(
        path: str,
        project_id: str | None = None,
        source_name: str | None = None,
        export_target: str = "api",
        dry_run: bool = False,
        yes: bool = False,
        approved: bool = False,
        output: str | None = None,
    ) -> dict:
        return tool_impl.sync_source(
            path=path,
            project_id=project_id,
            source_name=source_name,
            export_target=export_target,
            dry_run=dry_run,
            yes=yes,
            approved=approved,
            output=output,
            config_path=config_str,
        )

    @server.tool()
    def get_source_coverage(path: str | None = None, project_id: str | None = None) -> dict:
        return tool_impl.get_source_coverage(
            path=path,
            project_id=project_id,
            config_path=config_str,
        )

    @server.tool()
    def get_rag_readiness(path: str) -> dict:
        return tool_impl.get_rag_readiness(path=path, config_path=config_str)

    @server.tool()
    def search_evidence(
        project_id: str,
        query: str,
        top_k: int = 10,
        filters: dict | None = None,
        debug: bool = False,
    ) -> dict:
        return tool_impl.search_evidence(
            project_id=project_id,
            query=query,
            top_k=top_k,
            filters=filters,
            debug=debug,
            config_path=config_str,
        )

    @server.tool()
    def investigate_incident(
        project_id: str,
        query: str,
        top_k: int | None = None,
        debug: bool = False,
    ) -> dict:
        return tool_impl.investigate_incident(
            project_id=project_id,
            query=query,
            top_k=top_k,
            debug=debug,
            config_path=config_str,
        )

    @server.tool()
    def create_workflow_run(
        project_id: str,
        query: str,
        top_k: int | None = None,
        approved: bool = False,
    ) -> dict:
        return tool_impl.create_workflow_run(
            project_id=project_id,
            query=query,
            top_k=top_k,
            approved=approved,
            config_path=config_str,
        )

    @server.tool()
    def get_run_status(run_id: str) -> dict:
        return tool_impl.get_run_status(run_id=run_id, config_path=config_str)

    @server.tool()
    def get_run_events(run_id: str) -> dict:
        return tool_impl.get_run_events(run_id=run_id, config_path=config_str)

    @server.tool()
    def export_report(
        run_id: str | None = None,
        path: str | None = None,
        format: str = "markdown",
        output: str | None = None,
        approved: bool = False,
    ) -> dict:
        return tool_impl.export_report(
            run_id=run_id,
            path=path,
            format=format,
            output=output,
            approved=approved,
            config_path=config_str,
        )

    @server.tool()
    def generate_eval_seed(path: str, output: str | None = None, approved: bool = False) -> dict:
        return tool_impl.generate_eval_seed(
            path=path,
            output=output,
            approved=approved,
            config_path=config_str,
        )

    @server.tool()
    def validate_core_contract(
        api_url: str | None = None,
        project_id: str | None = None,
        with_sample: bool = False,
        approved: bool = False,
    ) -> dict:
        return tool_impl.validate_core_contract(
            api_url=api_url,
            project_id=project_id,
            with_sample=with_sample,
            approved=approved,
            config_path=config_str,
        )

    @server.resource("incidentops://local/config")
    def local_config() -> dict:
        return resource_impl.get_local_config(config_path)

    @server.resource("incidentops://local/last-inspection")
    def local_last_inspection() -> dict:
        return resource_impl.get_last_inspection(config_path)

    @server.resource("incidentops://local/last-sync")
    def local_last_sync() -> dict:
        return resource_impl.get_last_sync(config_path)

    @server.resource("incidentops://local/rag-readiness")
    def local_rag_readiness() -> dict:
        return resource_impl.get_local_rag_readiness(config_path)

    @server.resource("incidentops://local/failed-uploads")
    def local_failed_uploads() -> dict:
        return resource_impl.get_failed_uploads(config_path)

    @server.resource("incidentops://project/{project_id}/sources")
    def project_sources(project_id: str) -> dict:
        return resource_impl.get_project_sources(project_id=project_id, config_path=config_path)

    @server.resource("incidentops://project/{project_id}/coverage")
    def project_coverage(project_id: str) -> dict:
        return resource_impl.get_project_coverage(project_id=project_id, config_path=config_path)

    @server.resource("incidentops://project/{project_id}/core-capabilities")
    def project_core_capabilities(project_id: str) -> dict:
        return resource_impl.get_project_core_capabilities(
            project_id=project_id,
            config_path=config_path,
        )

    def _make_prompt(prompt_text: str):
        def _prompt() -> str:
            return prompt_text

        return _prompt

    for prompt_name, prompt in load_all_prompts().items():
        server.prompt(name=prompt_name)(_make_prompt(prompt.raw_xml))

    return server


def describe_mcp_surface(config_path: Path | None = None) -> dict:
    _ = config_path
    return {
        "tools": [
            "inspect_folder",
            "validate_source_config",
            "preview_redaction",
            "sync_source",
            "get_source_coverage",
            "get_rag_readiness",
            "search_evidence",
            "investigate_incident",
            "create_workflow_run",
            "get_run_status",
            "get_run_events",
            "export_report",
            "generate_eval_seed",
            "validate_core_contract",
        ],
        "resources": {
            "incidentops://local/config": {
                "description": "Redacted Collector config summary.",
            },
            "incidentops://local/last-inspection": {
                "description": "Last local inspection checkpoint if available.",
            },
            "incidentops://local/last-sync": {
                "description": "Last sync summary from local SQLite state.",
            },
            "incidentops://local/rag-readiness": {
                "description": "Readiness for the first configured local source.",
            },
            "incidentops://local/failed-uploads": {
                "description": "Failed upload queue depth and safe summaries.",
            },
            "incidentops://project/{project_id}/sources": {
                "description": "Core project source registry.",
            },
            "incidentops://project/{project_id}/coverage": {
                "description": "Core source coverage or local fallback.",
            },
            "incidentops://project/{project_id}/core-capabilities": {
                "description": "Core contract compatibility report.",
            },
        },
        "prompts": {
            name: {
                "version": prompt.version,
                "description": prompt.description,
                "path": str(prompt.path),
            }
            for name, prompt in load_all_prompts().items()
        },
        "permission_model": {
            "READ_ONLY": "allowed by default",
            "LOCAL_SENSITIVE_READ": "requires allowlisted path",
            "DATA_EXPORT": "requires explicit approval or dry_run where supported",
            "EXTERNAL_WRITE": "disabled",
        },
    }
