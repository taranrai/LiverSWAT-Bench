"""Run a model over a benchmark dataset and store responses as JSONL.

Output layout::

    <output_dir>/<experiment_id>/
        responses.jsonl   one ResponseRecord per (item, trial)
        manifest.json     run-level reproducibility metadata and status labels

This module only collects responses. Scoring is done separately (Milestone 3).
"""

from __future__ import annotations

import re
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from liverswat_bench.datasets.schema import (
    BenchmarkItem,
    EvidenceLevel,
    Track,
    VerificationStatus,
)
from liverswat_bench.datasets.validation import validate_dataset
from liverswat_bench.evaluation.conditions import (
    EVIDENCE_PROMPT_VERSION,
    EvidenceCondition,
    build_condition_messages,
)
from liverswat_bench.evaluation.environment import capture_environment, sha256_file
from liverswat_bench.evaluation.records import (
    MOCK_LABEL,
    NOT_CLINICAL_LABEL,
    REAL_LABEL,
    SYNTHETIC_LABEL,
    UNVERIFIED_LABEL,
    DataProvenance,
    ModelInfo,
    PromptInfo,
    ResponseInfo,
    ResponseRecord,
    RunManifest,
    Timing,
)
from liverswat_bench.evidence.registry import EvidenceRegistry
from liverswat_bench.evidence.retrieval import RETRIEVER_ID, LexicalRetriever
from liverswat_bench.io import read_jsonl_models
from liverswat_bench.models import AdapterError, ModelAdapter, create_adapter
from liverswat_bench.models.config import ModelConfig, load_model_config

EXPERIMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class EvaluationError(RuntimeError):
    """A problem that prevents an evaluation from starting."""


@dataclass
class RunResult:
    output_dir: Path
    responses_path: Path
    manifest: RunManifest


def is_primary_eligible(item: BenchmarkItem) -> bool:
    return (
        item.track == Track.PRIMARY
        and item.evidence_level == EvidenceLevel.A
        and item.verification_status == VerificationStatus.SOURCE_VERIFIED
        and not item.synthetic
    )


def status_labels(items: Sequence[BenchmarkItem], backend: str | None = None) -> list[str]:
    labels = [NOT_CLINICAL_LABEL]
    if any(i.synthetic for i in items):
        labels.insert(0, SYNTHETIC_LABEL)
    if any(not is_primary_eligible(i) for i in items):
        labels.append(UNVERIFIED_LABEL)
    if backend is not None:
        labels.append(MOCK_LABEL if backend == "mock" else REAL_LABEL)
    return labels


def default_experiment_id(config: ModelConfig, dataset_path: Path, now: datetime) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]", "-", dataset_path.stem)
    return f"{now:%Y%m%dT%H%M%SZ}_{config.config_id}_{stem}"


def _now() -> datetime:
    return datetime.now(UTC)


def load_items(
    dataset_path: Path,
    source_files: Sequence[Path],
    passage_files: Sequence[Path],
) -> list[BenchmarkItem]:
    """Load items, refusing to run on anything that fails validation."""
    report = validate_dataset([dataset_path], source_files, passage_files)
    if not report.ok:
        shown = "\n".join(f"  - {i}" for i in report.issues[:20])
        more = len(report.issues) - 20
        suffix = f"\n  ... and {more} more" if more > 0 else ""
        raise EvaluationError(
            f"dataset failed validation ({len(report.issues)} issue(s)); "
            f"run 'liverswat validate' for details:\n{shown}{suffix}"
        )
    records, _ = read_jsonl_models(dataset_path, BenchmarkItem)
    return [item for _, item in records]


def run_evaluation(
    *,
    model_config_path: Path,
    dataset_path: Path,
    source_files: Sequence[Path],
    passage_files: Sequence[Path],
    output_dir: Path,
    experiment_id: str | None = None,
    trials: int = 1,
    limit: int | None = None,
    repo_root: Path | None = None,
    adapter_factory: Callable[[ModelConfig], ModelAdapter] = create_adapter,
    command: list[str] | None = None,
    progress: Callable[[str], None] | None = None,
    evidence_condition: str = "baseline",
    retrieval_top_k: int = 3,
) -> RunResult:
    if trials < 1:
        raise EvaluationError("trials must be at least 1")
    try:
        condition = EvidenceCondition(evidence_condition)
    except ValueError as exc:
        raise EvaluationError(
            f"unknown evidence condition {evidence_condition!r}; use baseline, retrieved or oracle"
        ) from exc
    if retrieval_top_k < 1:
        raise EvaluationError("retrieval_top_k must be at least 1")
    if limit is not None and limit < 1:
        raise EvaluationError("limit must be at least 1")

    config = load_model_config(model_config_path)
    all_items = load_items(dataset_path, source_files, passage_files)
    active = [i for i in all_items if i.verification_status != VerificationStatus.RETIRED]
    n_retired = len(all_items) - len(active)
    items = active[:limit] if limit else active
    if not items:
        raise EvaluationError("no items to evaluate (all retired, or the dataset is empty)")

    started = _now()
    if experiment_id is None:
        experiment_id = default_experiment_id(config, dataset_path, started)
        if condition != EvidenceCondition.BASELINE:
            experiment_id = f"{experiment_id}_{condition.value}"
    registry, _ = EvidenceRegistry.load(source_files, passage_files)
    retrievers = {
        flag: LexicalRetriever.from_registry(registry, synthetic=flag) for flag in (False, True)
    }
    if not EXPERIMENT_ID_PATTERN.match(experiment_id):
        raise EvaluationError(f"invalid experiment id {experiment_id!r}")
    run_dir = output_dir / experiment_id
    if run_dir.exists():
        raise EvaluationError(f"output directory already exists: {run_dir}")

    dataset_sha = sha256_file(dataset_path)
    adapter = adapter_factory(config)  # may raise AdapterError: nothing written yet
    run_dir.mkdir(parents=True)
    responses_path = run_dir / "responses.jsonl"

    model_info = ModelInfo(
        config_id=config.config_id,
        model_name=config.model_name,
        model_revision=config.model_revision,
        revision_pinned=config.revision_pinned,
        backend=config.backend,
        licence=config.licence,
        open_weight=config.open_weight,
        osi_approved_licence=config.osi_approved_licence,
        parameter_count=config.parameter_count,
        quantisation=config.quantisation,
    )

    n_ok = n_error = 0
    try:
        with responses_path.open("w", encoding="utf-8") as out:
            for item in items:
                provenance = DataProvenance(
                    synthetic=item.synthetic,
                    track=item.track,
                    verification_status=item.verification_status,
                    evidence_level=item.evidence_level,
                    primary_eligible=is_primary_eligible(item),
                    dataset_path=str(dataset_path),
                    dataset_sha256=dataset_sha,
                )
                messages, evidence = build_condition_messages(
                    config,
                    item,
                    condition,
                    registry,
                    retrievers[item.synthetic],
                    retrieval_top_k,
                )
                for trial in range(trials):
                    base_seed = config.generation.seed
                    params = config.generation.model_copy(
                        update={"seed": None if base_seed is None else base_seed + trial}
                    )
                    t_start = _now()
                    clock = time.perf_counter()
                    try:
                        result = adapter.generate(messages, params)
                        response = ResponseInfo(
                            text=result.text,
                            finish_reason=result.finish_reason,
                            prompt_tokens=result.prompt_tokens,
                            completion_tokens=result.completion_tokens,
                        )
                        served = result.served_model_id
                        status, error = "ok", None
                        n_ok += 1
                    except AdapterError as exc:
                        response = ResponseInfo(text=None)
                        served = None
                        status, error = "error", str(exc)
                        n_error += 1
                    latency = time.perf_counter() - clock
                    record = ResponseRecord(
                        record_id=f"{experiment_id}:{item.question_id}:{trial}",
                        experiment_id=experiment_id,
                        question_id=item.question_id,
                        benchmark_version=item.benchmark_version,
                        trial=trial,
                        data_provenance=provenance,
                        model=model_info.model_copy(update={"served_model_id": served}),
                        evidence=evidence,
                        prompt=PromptInfo(
                            system_prompt=config.system_prompt,
                            prompt_template=config.prompt_template,
                            messages=messages,
                        ),
                        generation=params,
                        response=response,
                        status=status,
                        error=error,
                        timing=Timing(started_at=t_start, completed_at=_now(), latency_s=latency),
                    )
                    out.write(record.model_dump_json() + "\n")
                    if progress:
                        progress(f"{item.question_id} trial {trial}: {status}")
        backend_info = adapter.runtime_info()
    finally:
        adapter.close()

    manifest = RunManifest(
        experiment_id=experiment_id,
        status_labels=status_labels(items, config.backend.value),
        started_at=started,
        completed_at=_now(),
        model_config_path=str(model_config_path),
        model_config_sha256=sha256_file(model_config_path),
        model_settings=config.model_dump(mode="json"),
        dataset_path=str(dataset_path),
        dataset_sha256=dataset_sha,
        registry_files={str(p): sha256_file(p) for p in [*source_files, *passage_files]},
        benchmark_versions=sorted({i.benchmark_version for i in items}),
        trials=trials,
        n_items=len(items),
        n_items_skipped_retired=n_retired,
        n_records=n_ok + n_error,
        n_ok=n_ok,
        n_error=n_error,
        items_by_track=dict(Counter(i.track.value for i in items)),
        items_by_verification_status=dict(Counter(i.verification_status.value for i in items)),
        n_synthetic_items=sum(i.synthetic for i in items),
        n_primary_eligible_items=sum(is_primary_eligible(i) for i in items),
        environment=capture_environment(repo_root or Path.cwd(), backend_info),
        command=command,
        evidence_condition=condition.value,
        retriever=None
        if condition != EvidenceCondition.RETRIEVED
        else {
            "retriever": RETRIEVER_ID,
            "top_k": retrieval_top_k,
            "corpus_size_real": len(retrievers[False].passages),
            "corpus_sha256_real": retrievers[False].corpus_sha256,
            "evidence_prompt_version": EVIDENCE_PROMPT_VERSION,
        },
    )
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")
    return RunResult(output_dir=run_dir, responses_path=responses_path, manifest=manifest)
