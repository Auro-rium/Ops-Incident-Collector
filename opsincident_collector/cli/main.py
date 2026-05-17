from __future__ import annotations

import typer

from opsincident_collector.cli.commands.agent import agent_app
from opsincident_collector.cli.commands.doctor import doctor
from opsincident_collector.cli.commands.init import init
from opsincident_collector.cli.commands.inspect import inspect
from opsincident_collector.cli.commands.mcp import mcp_app
from opsincident_collector.cli.commands.sync import sync
from opsincident_collector.cli.commands.validate import validate
from opsincident_collector.cli.commands.watch import watch

app = typer.Typer(help="OpsIncident-Collector edge runtime CLI.")

app.command()(init)
app.command()(doctor)
app.command()(inspect)
app.command()(sync)
app.command()(watch)
app.command()(validate)
app.add_typer(mcp_app, name="mcp")
app.add_typer(agent_app, name="agent")


if __name__ == "__main__":
    app()
