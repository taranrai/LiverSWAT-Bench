"""Command-line interface for LiverSWAT-Bench."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from liverswat_bench import BENCHMARK_VERSION, __version__
from liverswat_bench.datasets.validation import discover_files, validate_dataset

app = typer.Typer(
    name="liverswat",
    help=(
        "LiverSWAT-Bench: evidence-grounded (not clinically validated) evaluation "
        "of LLMs on UK liver health advice."
    ),
    no_args_is_help=True,
    add_completion=False,
)

EXIT_INVALID = 1
EXIT_NOT_IMPLEMENTED = 2


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"liverswat-bench {__version__} (benchmark format {BENCHMARK_VERSION})")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
        ),
    ] = False,
) -> None:
    """Top-level options."""


@app.command()
def validate(
    data_dir: Annotated[
        Path,
        typer.Option(
            help="Directory searched for *items.jsonl, *sources.jsonl and "
            "*passages.jsonl (data/private is always skipped)."
        ),
    ] = Path("data"),
    items: Annotated[
        list[Path] | None,
        typer.Option("--items", help="Item file(s) to validate. Overrides discovery."),
    ] = None,
    sources: Annotated[
        list[Path] | None,
        typer.Option("--sources", help="Source registry file(s). Overrides discovery."),
    ] = None,
    passages: Annotated[
        list[Path] | None,
        typer.Option("--passages", help="Evidence passage file(s). Overrides discovery."),
    ] = None,
) -> None:
    """Validate benchmark items and the evidence registry.

    Checks the schema, duplicate IDs, the rules for each track and verification
    status, and that every source and passage an item cites exists.
    """
    if not (items and sources and passages) and not data_dir.is_dir():
        typer.echo(f"error: data directory not found: {data_dir}", err=True)
        raise typer.Exit(EXIT_INVALID)

    found_items, found_sources, found_passages = (
        discover_files(data_dir) if data_dir.is_dir() else ([], [], [])
    )
    item_files = items or found_items
    source_files = sources or found_sources
    passage_files = passages or found_passages

    for path in [*item_files, *source_files, *passage_files]:
        if not path.is_file():
            typer.echo(f"error: file not found: {path}", err=True)
            raise typer.Exit(EXIT_INVALID)
    if not item_files:
        typer.echo("error: no item files found (expected *items.jsonl)", err=True)
        raise typer.Exit(EXIT_INVALID)

    report = validate_dataset(item_files, source_files, passage_files)

    typer.echo(f"Evidence registry: {report.n_sources} sources, {report.n_passages} passages")
    for path, count in report.items_per_file.items():
        typer.echo(f"  {path}: {count} item(s) parsed")
    if report.ok:
        typer.echo("Validation passed.")
        return
    typer.echo(f"Validation failed with {len(report.issues)} issue(s):", err=True)
    for issue in report.issues:
        typer.echo(f"  - {issue}", err=True)
    raise typer.Exit(EXIT_INVALID)


def _not_implemented(command: str, milestone: int) -> None:
    typer.echo(
        f"error: '{command}' is not implemented yet (planned for Milestone {milestone}).",
        err=True,
    )
    raise typer.Exit(EXIT_NOT_IMPLEMENTED)


@app.command()
def evaluate(
    model: Annotated[str, typer.Option("--model", help="Model config ID or path.")],
    dataset: Annotated[Path, typer.Option("--dataset", help="Benchmark items JSONL.")],
) -> None:
    """Run a model on a benchmark dataset. [Milestone 2]"""
    _not_implemented("evaluate", 2)


@app.command()
def judge(
    results: Annotated[Path, typer.Option("--results", help="Model responses file.")],
) -> None:
    """Score stored model responses with automated judges. [Milestone 4]"""
    _not_implemented("judge", 4)


@app.command()
def compare(
    results: Annotated[Path, typer.Option("--results", help="Results directory.")],
) -> None:
    """Compare models with paired, case-level statistics. [Milestone 7]"""
    _not_implemented("compare", 7)


@app.command()
def report(
    results: Annotated[Path, typer.Option("--results", help="Results directory.")],
) -> None:
    """Generate Markdown/CSV/JSON research reports. [Milestone 3]"""
    _not_implemented("report", 3)


if __name__ == "__main__":
    app()
