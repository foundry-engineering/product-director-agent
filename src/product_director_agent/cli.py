from __future__ import annotations

import typer

app = typer.Typer(add_completion=False)

@app.command()
def health() -> None:
    typer.echo("ok")

def main() -> None:
    app()
