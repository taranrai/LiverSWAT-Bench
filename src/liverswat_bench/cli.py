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
    evidence_condition: Annotated[
        str,
        typer.Option(
            help="baseline (question only), retrieved (lexical retrieval over the registry) "
            "or oracle (the item's own cited passages)."
        ),
    ] = "baseline",
    retrieval_top_k: Annotated[
        int, typer.Option(min=1, help="Passages supplied in the retrieved condition.")
    ] = 3,
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
            evidence_condition=evidence_condition,
            retrieval_top_k=retrieval_top_k,
        )
    except (ConfigError, EvaluationError, AdapterError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_INVALID) from exc

    m = result.manifest
    for label in m.status_labels:
        typer.echo(f"*** {label} ***")
    typer.echo(f"Experiment:  {m.experiment_id}")
    typer.echo(f"Evidence:    {m.evidence_condition}")
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
    results: Annotated[
        Path, typer.Option("--results", help="Run directory (contains responses.jsonl).")
    ],
    judge_configs: Annotated[
        list[Path],
        typer.Option(
            "--judge",
            help="Judge config: a YAML path, or an ID in --judges-dir. Repeat for several judges.",
        ),
    ],
    data_dir: Annotated[
        Path, typer.Option(help="Directory searched for the evidence registry.")
    ] = Path("data"),
    judges_dir: Annotated[Path, typer.Option(help="Where judge config IDs are looked up.")] = Path(
        "configs/judges"
    ),
    prompt_variants: Annotated[
        list[str] | None,
        typer.Option(
            "--prompt-variant",
            help="Prompt version(s) to run (e.g. v1, v1-alt). Default: the config's version. "
            "Running several measures sensitivity to prompt wording.",
        ),
    ] = None,
    repeats: Annotated[
        int, typer.Option(min=1, help="Repeated judgements per response (stability).")
    ] = 1,
    overwrite: Annotated[bool, typer.Option(help="Replace existing judgements.")] = False,
) -> None:
    """Assess stored responses with LLM judges (automated, not clinical experts).

    Each judge sees only the question, the response, the evidence passages its
    evidence policy allows, and the rubric. Outputs are validated (schema,
    evidence references, claim text); invalid outputs are retried, then
    abstained. Writes RESULTS/judgements/<judge_id>.jsonl and a manifest.
    """
    from liverswat_bench.judges.runner import JudgeRunError, judge_run
    from liverswat_bench.models import AdapterError, ConfigError

    if not data_dir.is_dir():
        typer.echo(f"error: data directory not found: {data_dir}", err=True)
        raise typer.Exit(EXIT_INVALID)
    _, source_files, passage_files = discover_files(data_dir)
    for cfg in judge_configs:
        path = cfg if cfg.suffix in {".yaml", ".yml"} else judges_dir / f"{cfg}.yaml"
        try:
            result = judge_run(
                results,
                path,
                source_files=source_files,
                passage_files=passage_files,
                prompt_versions=prompt_variants,
                repeats=repeats,
                overwrite=overwrite,
            )
        except (JudgeRunError, ConfigError, AdapterError) as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(EXIT_INVALID) from exc
        m = result.manifest
        typer.echo(f"Judge {m.judge_id}: {m.n_judgements} judgement(s) {m.n_by_status}")
        typer.echo(f"  -> {result.path}")
    typer.echo("*** AUTOMATED LLM-JUDGE ASSESSMENTS - NOT CLINICAL EXPERT REVIEW ***")


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


def _combine_settings(policy: str, min_judges: int):
    from liverswat_bench.evaluation.combine import CombinePolicy, CombineSettings

    try:
        return CombineSettings(policy=CombinePolicy(policy), min_judges=min_judges)
    except ValueError as exc:
        typer.echo(f"error: unknown policy {policy!r}", err=True)
        raise typer.Exit(EXIT_INVALID) from exc


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
    policy: Annotated[
        str,
        typer.Option(
            help="Rule/judge combination policy: rules_first_review_on_disagreement "
            "(default) or rules_first. Rule scores are never overridden."
        ),
    ] = "rules_first_review_on_disagreement",
    min_judges: Annotated[
        int, typer.Option(min=1, help="Judges that must score a dimension for consensus.")
    ] = 2,
) -> None:
    """Write summary.json, item_scores.csv, dimension_summary.csv and report.md for a run.

    Primary-eligible and non-primary records are always reported separately.
    Critical flags, abstentions and missing scores are counted explicitly. If
    judgements exist, also writes combined_scores.{jsonl,csv} and oversight.json
    and adds judge, disagreement and oversight sections.
    """
    from liverswat_bench.reporting import ReportError, load_scored_run, write_report

    try:
        run = load_scored_run(results)
        paths = write_report(
            run, output_dir or results / "report", _combine_settings(policy, min_judges)
        )
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
    policy: Annotated[
        str,
        typer.Option(
            help="Rule/judge combination policy: rules_first_review_on_disagreement "
            "(default) or rules_first. Rule scores are never overridden."
        ),
    ] = "rules_first_review_on_disagreement",
    min_judges: Annotated[
        int, typer.Option(min=1, help="Judges that must score a dimension for consensus.")
    ] = 2,
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
        paths = write_comparison(runs, output_dir, _combine_settings(policy, min_judges))
    except ReportError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_INVALID) from exc
    typer.echo(f"Compared {len(runs)} run(s).")
    for name, path in paths.items():
        typer.echo(f"{name}: {path}")


@app.command("check-docs")
def check_docs(
    paths: Annotated[
        list[Path] | None,
        typer.Argument(help="Markdown files to check. Default: README, dataset card and docs/."),
    ] = None,
    max_words: Annotated[
        int, typer.Option(min=5, help="Advisory sentence length limit in words.")
    ] = 25,
    strict: Annotated[
        bool,
        typer.Option(help="Exit with code 1 if a deterministic rule (discouraged term) fails."),
    ] = False,
) -> None:
    """Run the advisory documentation style check (ASD-STE100 principles).

    The check reports undefined abbreviations, discouraged terms, long sentences and
    ambiguous wording. Only discouraged terms are deterministic. The check does not
    certify ASD-STE100 compliance.
    """
    from liverswat_bench.docs_check import check_files, default_paths

    files = paths or default_paths(Path.cwd())
    missing = [f for f in files if not f.is_file()]
    if missing:
        typer.echo(f"error: file not found: {missing[0]}", err=True)
        raise typer.Exit(EXIT_INVALID)
    findings = check_files(files, max_words)
    for finding in findings:
        typer.echo(str(finding))
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.rule] = counts.get(f.rule, 0) + 1
    errors = sum(f.enforceable for f in findings)
    typer.echo(f"Checked {len(files)} file(s). Findings by rule: {counts or 'none'}.")
    typer.echo("This check is advisory. It does not certify ASD-STE100 compliance.")
    if strict and errors:
        typer.echo(f"error: {errors} deterministic finding(s) (discouraged terms).", err=True)
        raise typer.Exit(EXIT_INVALID)


@app.command()
def pilot(
    config: Annotated[Path, typer.Option("--config", help="Pilot configuration YAML file.")],
    summarise_only: Annotated[
        bool, typer.Option(help="Rebuild the pilot summary from existing run outputs only.")
    ] = False,
) -> None:
    """Run a pilot: models x evidence conditions, then score, judge, report and summarise.

    Steps with existing outputs are skipped, so an interrupted pilot can resume. Real
    model backends run real inference. Check the configuration before you run it.
    """
    from liverswat_bench.evaluation.combine import CombineSettings
    from liverswat_bench.experiments.pilot import (
        load_pilot_config,
        render_pilot_markdown,
        run_dir_name,
        run_pilot,
        summarise_pilot,
    )
    from liverswat_bench.models import AdapterError, ConfigError
    from liverswat_bench.models.config import load_model_config

    try:
        cfg = load_pilot_config(config)
    except (OSError, ValueError) as exc:
        typer.echo(f"error: invalid pilot configuration {config}: {exc}", err=True)
        raise typer.Exit(EXIT_INVALID) from exc
    _, source_files, passage_files = discover_files(cfg.data_dir)
    try:
        if summarise_only:
            run_dirs = [
                cfg.output_dir / run_dir_name(load_model_config(m).config_id, c)
                for m in cfg.models
                for c in cfg.conditions
            ]
            settings = CombineSettings(policy=cfg.combine_policy, min_judges=cfg.min_judges)
            summary = summarise_pilot(cfg, run_dirs, settings)
            import json

            (cfg.output_dir / "pilot_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            (cfg.output_dir / "pilot_summary.md").write_text(render_pilot_markdown(summary))
            typer.echo(f"Summary: {cfg.output_dir / 'pilot_summary.md'}")
            return
        run_pilot(cfg, source_files=source_files, passage_files=passage_files, log=typer.echo)
    except (ConfigError, AdapterError, RuntimeError, OSError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(EXIT_INVALID) from exc


evidence_app = typer.Typer(
    help="Source-verification workflow: snapshots, machine text checks and human review log.",
    no_args_is_help=True,
)
app.add_typer(evidence_app, name="evidence")


def _registry(data_dir: Path):
    from liverswat_bench.evidence.registry import EvidenceRegistry

    if not data_dir.is_dir():
        typer.echo(f"error: data directory not found: {data_dir}", err=True)
        raise typer.Exit(EXIT_INVALID)
    _, source_files, passage_files = discover_files(data_dir)
    registry, _ = EvidenceRegistry.load(source_files, passage_files)
    return registry, source_files


def _log_path(data_dir: Path) -> Path:
    from liverswat_bench.evidence.verification import LOG_FILENAME

    return (
        data_dir / "evidence" / LOG_FILENAME
        if (data_dir / "evidence").is_dir()
        else (data_dir / LOG_FILENAME)
    )


@evidence_app.command("snapshot")
def evidence_snapshot(
    out: Annotated[Path, typer.Option(help="Directory for snapshots (keep out of Git).")],
    data_dir: Annotated[Path, typer.Option(help="Data directory with the registry.")] = Path(
        "data"
    ),
    source_ids: Annotated[
        list[str] | None, typer.Option("--source-id", help="Only these sources.")
    ] = None,
) -> None:
    """Download the official URL of each non-synthetic source and extract its text.

    Records the HTTP status, final URL, retrieval time and SHA-256 hash. This command
    uses the network.
    """
    from liverswat_bench.evidence.verification import VerificationError, take_snapshot

    registry, _ = _registry(data_dir)
    failures = 0
    for sid, source in sorted(registry.sources.items()):
        if source.synthetic or not source.url or (source_ids and sid not in source_ids):
            continue
        try:
            meta = take_snapshot(sid, str(source.url), out)
            typer.echo(f"{sid}: HTTP {meta.http_status}, sha256 {meta.sha256[:12]}...")
        except VerificationError as exc:
            failures += 1
            typer.echo(f"error: {exc}", err=True)
    if failures:
        raise typer.Exit(EXIT_INVALID)


@evidence_app.command("check")
def evidence_check(
    snapshots: Annotated[Path, typer.Option(help="Snapshot directory from 'evidence snapshot'.")],
    data_dir: Annotated[Path, typer.Option(help="Data directory with the registry.")] = Path(
        "data"
    ),
    record: Annotated[
        bool, typer.Option(help="Append the machine check results to the verification log.")
    ] = False,
) -> None:
    """Check that each stored passage occurs verbatim in its source snapshot.

    A match is a machine check only. It does not verify the passage. A human review
    is required before any status can be set to verified.
    """
    from liverswat_bench.evidence.verification import append_log, load_snapshots, machine_check

    registry, _ = _registry(data_dir)
    if not snapshots.is_dir():
        typer.echo(f"error: snapshot directory not found: {snapshots}", err=True)
        raise typer.Exit(EXIT_INVALID)
    entries = machine_check(registry, load_snapshots(snapshots))
    for e in entries:
        typer.echo(f"{e.passage_id}: {e.result}")
    counts = {
        r: sum(e.result == r for e in entries) for r in ("match", "no_match", "not_checkable")
    }
    typer.echo(
        f"{counts['match']} match, {counts['no_match']} no_match, "
        f"{counts['not_checkable']} not_checkable. Machine checks do not verify evidence."
    )
    if record and entries:
        log = _log_path(data_dir)
        append_log(log, entries)
        typer.echo(f"Recorded {len(entries)} machine check(s) in {log}.")


@evidence_app.command("record-review")
def evidence_record_review(
    source_id: Annotated[str, typer.Option(help="Source ID that was reviewed.")],
    reviewer: Annotated[str, typer.Option(help="Name of the human reviewer.")],
    result: Annotated[str, typer.Option(help="confirmed, rejected or needs_changes.")],
    passage_id: Annotated[
        str | None, typer.Option(help="Passage ID. Omit to record a source-level review.")
    ] = None,
    notes: Annotated[str | None, typer.Option(help="What was checked, and how.")] = None,
    data_dir: Annotated[Path, typer.Option(help="Data directory with the registry.")] = Path(
        "data"
    ),
) -> None:
    """Append a human review to the verification log.

    Run this command only after a person has checked the official source. Do not
    record a review on the basis of a model statement.
    """
    from datetime import UTC, datetime

    from pydantic import ValidationError

    from liverswat_bench.evidence.verification import LogEntry, append_log

    registry, _ = _registry(data_dir)
    if source_id not in registry.sources:
        typer.echo(f"error: unknown source ID {source_id!r}", err=True)
        raise typer.Exit(EXIT_INVALID)
    if passage_id and registry.passages.get(passage_id, None) is None:
        typer.echo(f"error: unknown passage ID {passage_id!r}", err=True)
        raise typer.Exit(EXIT_INVALID)
    try:
        entry = LogEntry(
            timestamp=datetime.now(UTC),
            source_id=source_id,
            passage_id=passage_id,
            check_type="human_review",
            result=result,
            performed_by=reviewer,
            notes=notes,
        )
    except ValidationError as exc:
        typer.echo(f"error: {exc.errors()[0]['msg']}", err=True)
        raise typer.Exit(EXIT_INVALID) from exc
    log = _log_path(data_dir)
    append_log(log, [entry])
    typer.echo(f"Recorded human review ({result}) for {passage_id or source_id} in {log}.")
    typer.echo("Update the registry status separately, then run 'liverswat validate'.")


@evidence_app.command("status")
def evidence_status(
    data_dir: Annotated[Path, typer.Option(help="Data directory with the registry.")] = Path(
        "data"
    ),
) -> None:
    """Show each passage's registry status, latest machine check and latest human review."""
    from liverswat_bench.evidence.verification import read_log, summarise_status

    registry, _ = _registry(data_dir)
    rows = summarise_status(registry, read_log(_log_path(data_dir)))
    for r in rows:
        typer.echo(
            f"{r['passage_id']}: status={r['status']} machine={r['machine_check']} "
            f"human={r['human_review']}"
        )


if __name__ == "__main__":
    app()
