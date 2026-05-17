from __future__ import annotations

import json
from pathlib import Path

import typer

from opsincident_collector.config.loader import load_settings_optional
from opsincident_collector.mcp_server.server import create_fastmcp_server, describe_mcp_surface

mcp_app = typer.Typer(
    help=(
        "MCP commands. Exposes permissioned Collector tools, Core API bridge tools, "
        "safe resources, and disk-loaded XML prompts over stdio."
    )
)


@mcp_app.command("serve")
def serve(
    config: Path | None = typer.Option(None, "--config", help="Collector YAML config path."),
    transport: str = typer.Option("stdio", "--transport", help="MCP transport. Phase 3 supports stdio."),
    dump_schema: bool = typer.Option(False, "--dump-schema", help="Print tools/resources/prompts and exit."),
) -> None:
    if dump_schema:
        typer.echo(json.dumps(describe_mcp_surface(config), indent=2, default=str))
        return
    if transport != "stdio":
        typer.echo("Only stdio transport is implemented in Phase 3.")
        raise typer.Exit(code=1)
    settings = load_settings_optional(config)
    if not settings.mcp.enabled:
        typer.echo("MCP is disabled by config: mcp.enabled=false")
        raise typer.Exit(code=1)
    try:
        server = create_fastmcp_server(config)
    except ModuleNotFoundError:
        typer.echo("MCP dependency not installed. Install with `pip install 'opsincident-collector[mcp]'`.")
        raise typer.Exit(code=1)
    server.run()
