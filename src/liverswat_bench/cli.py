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
EXIT_PARTIAL_FAILURE = 3


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
    model: Annotated[
        str,
        typer.Option(
            "--model",
            help="Model config: a YAML path, or a config ID found in --configs-dir (e.g. 'mock').",
        ),
    ],
    dataset: Annotated[Path, typer.Option("--dataset", help="Benchmark items JSONL file.")],
    data_dir: Annotated[
        Path,
        typer.Option(
            help="Directory searched for the evidence registry (*sources.jsonl, "
            "*passages.jsonl) used to validate the dataset before running."
        ),
    ] = Path("data"),
    configs_dir: Annotated[Path, typer.Option(help="Where model config IDs are looked up.")] = Path(
        "configs/models"
    ),
    output_dir: Annotated[Path, typer.Option(help="Parent directory for run outputs.")] = Path(
        "results"
    ),
    experiment_id: Annotated[
        str | None,
        typer.Option(help="Run name. Default: <UTC timestamp>_<config_id>_<dataset>."),
    ] = None,
    trials: Annotated[
        int, typer.Option(min=1, help="Repeated generations per item (seed + trial).")
    ] = 1,
    limit: Annotated[
        int | None, typer.Option(min=1, help="Only evaluate the first N active items.")
    ] = None,
) -> None:
    """Run a model on a benchmark dataset and store its responses as JSONL.

    The dataset is validated against the evidence registry first. Writes
    responses.jsonl and manifest.json to OUTPUT_DIR/EXPERIMENT_ID. Responses
    are collected, not scored; scoring arrives in Milestone 3.

    Exit codes: 0 all generations succeeded; 1 setup or validation error;
    3 run completed but some generations failed (see the error field).
    """
    import sys

    from liverswat_bench.evaluation.runner import EvaluationError, run_evaluation
    from liverswat_bench.models import AdapterError, ConfigError, resolve_model_config

    if not dataset.is_file():
        typer.echo(f"error: dataset not found: {dataset}", err=True)
        raise typer.Exit(EXIT_INVALID)
    if not data_dir.is_dir():
        typer.echo(f"error: data directory not found: {data_dir}", err=True)
        raise typer.Exit(EXIT_INVALID)
    _, source_files, passage_files = discover_files(data_dir)

    try:
        config_path = resolve_model_config(model, configs_dir)
        result = run_evaluation(
            model_config_path=config_path,
            dataset_path=dataset,
            source_files=source_files,
            passage_files=passage_files,
            output_dir=output_dir,
            experiment_id=experiment_id,
            trials=trials,
            limit=limit,
            command=["liverswat", *sys.argv[1:]],
        )
    except (ConfigError, EvaluationError, AdapterError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_INVALID) from exc

    m = result.manifest
    for label in m.status_labels:
        typer.echo(f"*** {label} ***")
    typer.echo(f"Experiment:  {m.experiment_id}")
    typer.echo(
        f"Model:       {m.model_settings['model_name']} "
        f"(revision {m.model_settings['model_revision'] or 'n/a'}, "
        f"backend {m.model_settings['backend']})"
    )
    typer.echo(
        f"Items:       {m.n_items} ({m.n_synthetic_items} synthetic, "
        f"{m.n_primary_eligible_items} primary-eligible) x {m.trials} trial(s)"
    )
    typer.echo(f"Generations: {m.n_ok} ok, {m.n_error} failed")
    typer.echo(f"Responses:   {result.responses_path}")
    typer.echo(f"Manifest:    {result.output_dir / 'manifest.json'}")
    if m.n_error:
        raise typer.Exit(EXIT_PARTIAL_FAILURE)


@app.command()
def judge(
    results: Annotated[Path, typer.Option("--results", help="Model responses file.")],
) -> None:
    """Score stored model responses with automated judges. [Milestone 4]"""
    _not_implemented("judge", 4)


@app.command()
def score(
    results: Annotated[
        Path, typer.Option("--results", help="Run directory (contains responses.jsonl).")
    ],
    data_dir: Annotated[
        Path, typer.Option(help="Directory searched for the evidence registry.")
    ] = Path("data"),
    dataset: Annotated[
        Path | None,
        typer.Option(
            help="Dataset file. Default: the path recorded in the run manifest. "
            "Its sha256 must match the run."
        ),
    ] = None,
    overwrite: Annotated[bool, typer.Option(help="Replace an existing scores.jsonl.")] = False,
) -> None:
    """Score a run with deterministic, rule-based checks (scorer det-1).

    Writes scores.jsonl (one JSON evaluation record per response) and
    scoring_manifest.json. Primary eligibility is re-checked against the current
    evidence registry. Dimensions that cannot be scored by rule are recorded as
    abstained, never as zero.
    """
    from liverswat_bench.evaluation.score_run import ScoringError, score_run

    if not data_dir.is_dir():
        typer.echo(f"error: data directory not found: {data_dir}", err=True)
        raise typer.Exit(EXIT_INVALID)
    _, source_files, passage_files = discover_files(data_dir)
    try:
        result = score_run(
            results,
            source_files=source_files,
            passage_files=passage_files,
            dataset_path=dataset,
            overwrite=overwrite,
        )
    except ScoringError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_INVALID) from exc
    m = result.manifest
    for label in m.status_labels:
        typer.echo(f"*** {label} ***")
    typer.echo(f"Scorer:   {m.scorer}")
    typer.echo(f"Records:  {m.n_records} ({m.n_primary_eligible_records} primary-eligible)")
    typer.echo(f"Scores:   {result.scores_path}")


def _scored_run_dirs(results: Path) -> list[Path]:
    if (results / "scores.jsonl").is_file():
        return [results]
    return sorted(p.parent for p in results.glob("*/scores.jsonl"))


@app.command()
def report(
    results: Annotated[Path, typer.Option("--results", help="Scored run directory.")],
    output_dir: Annotated[
        Path | None, typer.Option(help="Where to write the report. Default: RESULTS/report.")
    ] = None,
) -> None:
    """Write summary.json, item_scores.csv, dimension_summary.csv and report.md for a run.

    Primary-eligible and non-primary records are always reported separately.
    Critical flags, abstentions and missing scores are counted explicitly.
    """
    from liverswat_bench.reporting import ReportError, load_scored_run, write_report

    try:
        run = load_scored_run(results)
        paths = write_report(run, output_dir or results / "report")
    except ReportError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_INVALID) from exc
    for name, path in paths.items():
        typer.echo(f"{name}: {path}")


@app.command()
def compare(
    results: Annotated[
        list[Path],
        typer.Option(
            "--results",
            help="Scored run directories, or one parent directory containing them. "
            "Repeat --results to list several runs.",
        ),
    ],
    output_dir: Annotated[
        Path, typer.Option(help="Where to write comparison.{json,csv,md}.")
    ] = Path("results/comparison"),
) -> None:
    """Descriptive side-by-side comparison of scored runs.

    Reports case-level means per dimension, separately for primary and
    non-primary records, and warns when runs used different datasets or
    scorers. Paired statistical comparison is planned for Milestone 7.
    """
    from liverswat_bench.reporting import ReportError, load_scored_run, write_comparison

    run_dirs: list[Path] = []
    for path in results:
        run_dirs.extend(_scored_run_dirs(path))
    if not run_dirs:
        typer.echo("error: no scored runs found (run 'liverswat score' first)", err=True)
        raise typer.Exit(EXIT_INVALID)
    try:
        runs = [load_scored_run(d) for d in run_dirs]
        paths = write_comparison(runs, output_dir)
    except ReportError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_INVALID) from exc
    typer.echo(f"Compared {len(runs)} run(s).")
    for name, path in paths.items():
        typer.echo(f"{name}: {path}")


if __name__ == "__main__":
    app()
