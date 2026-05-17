from __future__ import annotations

import json
from pathlib import Path

import typer

from opsincident_collector.mcp_server.resources import get_resource_map
from opsincident_collector.mcp_server.server import create_fastmcp_server

mcp_app = typer.Typer(help="MCP commands.")


@mcp_app.command("serve")
def serve(
    config: Path | None = typer.Option(None, "--config"),
    transport: str = typer.Option("stdio", "--transport"),
    dump_schema: bool = typer.Option(False, "--dump-schema"),
) -> None:
    if dump_schema:
        typer.echo(json.dumps(get_resource_map(config), indent=2, default=str))
        return
    if transport != "stdio":
        typer.echo("Only stdio transport is implemented in v1.")
        raise typer.Exit(code=1)
    try:
        server = create_fastmcp_server(config)
    except ModuleNotFoundError:
        typer.echo("MCP dependency not installed. Install with `pip install 'opsincident-collector[mcp]'`.")
        raise typer.Exit(code=1)
    server.run()
