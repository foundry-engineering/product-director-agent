from __future__ import annotations

import json
from pathlib import Path

import typer

from .contracts import ProductBrief
from .planner import build_delivery_plan

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def health() -> None:
    typer.echo("ok")


@app.command("plan")
def plan_command(
    brief: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Validate a customer brief and emit a deterministic cross-department delivery plan."""
    try:
        raw = json.loads(brief.read_text(encoding="utf-8"))
        parsed = ProductBrief.model_validate(raw)
        plan = build_delivery_plan(parsed)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    rendered = json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2)
    if output is None:
        typer.echo(rendered)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered + "\n", encoding="utf-8")


def main() -> None:
    app()
