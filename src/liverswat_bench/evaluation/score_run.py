"""Score every response in a run directory and write ``scores.jsonl``."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from liverswat_bench.datasets.schema import BenchmarkItem
from liverswat_bench.datasets.validation import validate_dataset
from liverswat_bench.evaluation.eligibility import primary_eligibility
from liverswat_bench.evaluation.environment import sha256_file
from liverswat_bench.evaluation.records import ResponseRecord, RunManifest
from liverswat_bench.evaluation.scoring import (
    SCORER_VERSION,
    aggregate,
    assess_claims,
    critical_flags,
    run_checks,
    score_dimensions,
)
from liverswat_bench.evaluation.scoring_records import (
    SCORING_LABEL,
    ScoreRecord,
    ScoringManifest,
    ScoringProvenance,
)
from liverswat_bench.evidence.registry import EvidenceRegistry
from liverswat_bench.io import read_jsonl_models

SCORES_FILE = "scores.jsonl"
SCORING_MANIFEST_FILE = "scoring_manifest.json"


class ScoringError(RuntimeError):
    """A problem that prevents scoring from starting."""


@dataclass
class ScoreRunResult:
    scores_path: Path
    manifest: ScoringManifest


def score_record(
    record: ResponseRecord, item: BenchmarkItem, registry: EvidenceRegistry
) -> ScoreRecord:
    reasons = primary_eligibility(item, registry)
    ok = record.status == "ok" and record.response.text is not None
    checks = run_checks(item, record.response.text) if ok else None
    dims = score_dimensions(item, checks, ok)
    flags, unchecked = critical_flags(checks or [])
    return ScoreRecord(
        record_id=record.record_id,
        experiment_id=record.experiment_id,
        question_id=record.question_id,
        trial=record.trial,
        scorer=SCORER_VERSION,
        provenance=ScoringProvenance(
            synthetic=item.synthetic,
            track=item.track,
            verification_status=item.verification_status,
            evidence_level=item.evidence_level,
            primary_eligible=not reasons,
            ineligibility_reasons=reasons,
        ),
        response_status="ok" if ok else "error",
        checks=checks or [],
        claim_assessments=assess_claims(checks or []),
        dimension_scores=dims,
        aggregate=aggregate(dims),
        critical_flags=flags,
        unchecked_critical=unchecked,
    )


def score_run(
    run_dir: Path,
    *,
    source_files: Sequence[Path],
    passage_files: Sequence[Path],
    dataset_path: Path | None = None,
    overwrite: bool = False,
) -> ScoreRunResult:
    manifest_path = run_dir / "manifest.json"
    responses_path = run_dir / "responses.jsonl"
    if not manifest_path.is_file() or not responses_path.is_file():
        raise ScoringError(f"{run_dir} is not a run directory (manifest.json/responses.jsonl)")
    scores_path = run_dir / SCORES_FILE
    if scores_path.exists() and not overwrite:
        raise ScoringError(f"{scores_path} already exists (use --overwrite to rescore)")

    run_manifest = RunManifest.model_validate_json(manifest_path.read_text())
    dataset = dataset_path or Path(run_manifest.dataset_path)
    if not dataset.is_file():
        raise ScoringError(f"dataset not found: {dataset} (pass --dataset)")
    dataset_sha = sha256_file(dataset)
    if dataset_sha != run_manifest.dataset_sha256:
        raise ScoringError(
            f"dataset {dataset} has changed since the run (sha256 {dataset_sha[:12]}... vs "
            f"{run_manifest.dataset_sha256[:12]}...); score with the dataset version used"
        )

    report = validate_dataset([dataset], source_files, passage_files)
    if not report.ok:
        raise ScoringError(
            f"dataset failed validation ({len(report.issues)} issue(s)); run 'liverswat validate'"
        )
    registry, _ = EvidenceRegistry.load(source_files, passage_files)
    items = {i.question_id: i for _, i in read_jsonl_models(dataset, BenchmarkItem)[0]}

    responses, issues = read_jsonl_models(responses_path, ResponseRecord)
    if issues:
        raise ScoringError(f"invalid response records: {issues[0]}")

    scored: list[ScoreRecord] = []
    for _, record in responses:
        item = items.get(record.question_id)
        if item is None:
            raise ScoringError(f"response {record.record_id} refers to unknown item")
        scored.append(score_record(record, item, registry))

    tmp = scores_path.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(s.model_dump_json() + "\n" for s in scored), encoding="utf-8")
    tmp.replace(scores_path)

    manifest = ScoringManifest(
        experiment_id=run_manifest.experiment_id,
        scorer=SCORER_VERSION,
        scored_at=datetime.now(UTC),
        status_labels=[*run_manifest.status_labels, SCORING_LABEL],
        responses_sha256=sha256_file(responses_path),
        dataset_path=str(dataset),
        dataset_sha256=dataset_sha,
        registry_files={str(p): sha256_file(p) for p in [*source_files, *passage_files]},
        n_records=len(scored),
        n_primary_eligible_records=sum(s.provenance.primary_eligible for s in scored),
    )
    (run_dir / SCORING_MANIFEST_FILE).write_text(manifest.model_dump_json(indent=2) + "\n")
    return ScoreRunResult(scores_path=scores_path, manifest=manifest)
