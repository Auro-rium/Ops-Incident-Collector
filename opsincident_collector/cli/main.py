from __future__ import annotations

import typer

from opsincident_collector.cli.commands.agent import agent_app
from opsincident_collector.cli.commands.benchmark import benchmark
from opsincident_collector.cli.commands.coverage import coverage
from opsincident_collector.cli.commands.daemon import daemon_app
from opsincident_collector.cli.commands.doctor import doctor
from opsincident_collector.cli.commands.eval_seed import eval_seed
from opsincident_collector.cli.commands.init import init
from opsincident_collector.cli.commands.inspect import inspect
from opsincident_collector.cli.commands.queue import queue_app
from opsincident_collector.cli.commands.rag_report import rag_report
from opsincident_collector.cli.commands.sync import sync
from opsincident_collector.cli.commands.validate import validate
from opsincident_collector.cli.commands.validate_core_contract import validate_core_contract
from opsincident_collector.cli.commands.validate_rag_pipeline import validate_rag_pipeline
from opsincident_collector.cli.commands.watch import watch

app = typer.Typer(help="OpsIncident-Collector edge runtime CLI.")

app.command()(init)
app.command()(doctor)
app.command()(inspect)
app.command()(sync)
app.command()(benchmark)
app.command()(watch)
app.command()(validate)
app.command()(coverage)
app.command()(rag_report)
app.command()(eval_seed)
app.command()(validate_core_contract)
app.command()(validate_rag_pipeline)
app.add_typer(agent_app, name="agent")
app.add_typer(daemon_app, name="daemon")
app.add_typer(queue_app, name="queue")


if __name__ == "__main__":
    app()
