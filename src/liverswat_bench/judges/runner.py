"""Run one LLM judge over every response in a run directory.

Output: ``<run_dir>/judgements/<judge_id>.jsonl`` (one JudgeRecord per
response x prompt version x repeat) and ``<judge_id>.manifest.json``.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from liverswat_bench.datasets.schema import BenchmarkItem
from liverswat_bench.datasets.validation import validate_dataset
from liverswat_bench.evaluation.environment import capture_environment, sha256_file
from liverswat_bench.evaluation.records import ResponseRecord, RunManifest
from liverswat_bench.evidence.registry import EvidenceRegistry
from liverswat_bench.evidence.schema import PassageTextType, SourceStatus
from liverswat_bench.io import read_jsonl_models
from liverswat_bench.judges.prompts import PROMPTS, SuppliedPassage, build_messages
from liverswat_bench.judges.schema import (
    JUDGE_LABEL,
    Attempt,
    EvidencePolicy,
    JudgeConfig,
    JudgeRecord,
    JudgeRunManifest,
    load_judge_config,
)
from liverswat_bench.judges.validate import JudgeOutputError, parse_output, validate_output
from liverswat_bench.models import AdapterError, ModelAdapter, create_adapter
from liverswat_bench.models.config import ModelConfig

JUDGEMENTS_DIR = "judgements"


class JudgeRunError(RuntimeError):
    """A problem that prevents judging from starting."""


@dataclass
class JudgeRunResult:
    path: Path
    manifest: JudgeRunManifest


def select_passages(
    item: BenchmarkItem, registry: EvidenceRegistry, policy: EvidencePolicy
) -> tuple[list[SuppliedPassage], dict[str, str]]:
    """Passages the judge may see, and why any others were withheld."""
    supplied: list[SuppliedPassage] = []
    withheld: dict[str, str] = {}
    for pid in item.evidence_passage_ids:
        passage = registry.passages.get(pid)
        if passage is None:
            withheld[pid] = "missing from registry"
            continue
        source = registry.sources.get(passage.source_id)
        verified = (
            passage.status == SourceStatus.VERIFIED
            and source is not None
            and source.source_status == SourceStatus.VERIFIED
        )
        if passage.text_type == PassageTextType.LOCATOR_ONLY or not passage.text:
            withheld[pid] = "no stored text (locator only)"
        elif not verified and policy == EvidencePolicy.VERIFIED_ONLY:
            withheld[pid] = "not verified (evidence policy verified_only)"
        else:
            supplied.append(SuppliedPassage(passage=passage, verified=verified))
    return supplied, withheld


def _sum(values: list[int | None]) -> int | None:
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def judge_one(
    *,
    adapter: ModelAdapter,
    config: JudgeConfig,
    record: ResponseRecord,
    item: BenchmarkItem,
    registry: EvidenceRegistry,
    prompt_version: str,
    repeat: int,
) -> JudgeRecord:
    supplied, withheld = select_passages(item, registry, config.evidence_policy)
    supplied_ids = {sp.passage.passage_id for sp in supplied}
    base_seed = config.model.generation.seed
    params = config.model.generation.model_copy(
        update={"seed": None if base_seed is None else base_seed + repeat}
    )
    common = {
        "judgement_id": f"{record.record_id}:{config.judge_id}:{prompt_version}:{repeat}",
        "record_id": record.record_id,
        "question_id": record.question_id,
        "trial": record.trial,
        "judge_id": config.judge_id,
        "judge_model": {
            "config_id": config.model.config_id,
            "model_name": config.model.model_name,
            "model_revision": config.model.model_revision,
            "revision_pinned": config.model.revision_pinned,
            "backend": config.model.backend.value,
        },
        "prompt_version": prompt_version,
        "repeat": repeat,
        "evidence_policy": config.evidence_policy,
        "passages_supplied": sorted(supplied_ids),
        "passages_supplied_verified": sorted(
            sp.passage.passage_id for sp in supplied if sp.verified
        ),
        "passages_withheld": withheld,
        "generation": params,
        "created_at": datetime.now(UTC),
    }
    if record.status != "ok" or record.response.text is None:
        return JudgeRecord(
            **common,
            messages=[],
            prompt_sha256="",
            status="skipped_no_response",
            attempts=[],
            latency_s=0.0,
        )

    messages = build_messages(prompt_version, item, record.response.text, supplied)
    prompt_sha = hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()
    attempts: list[Attempt] = []
    raw = None
    for attempt in range(config.max_retries + 1):
        seed = None if params.seed is None else params.seed + 1000 * attempt
        attempt_params = params.model_copy(update={"seed": seed})
        clock = time.perf_counter()
        try:
            result = adapter.generate(messages, attempt_params)
        except AdapterError as exc:
            attempts.append(
                Attempt(
                    attempt=attempt,
                    seed=seed,
                    raw_output=None,
                    error=f"generation error: {exc}",
                    latency_s=time.perf_counter() - clock,
                )
            )
            continue
        latency = time.perf_counter() - clock
        try:
            raw = parse_output(result.text)
            error = None
        except JudgeOutputError as exc:
            error = f"invalid output: {exc}"
        attempts.append(
            Attempt(
                attempt=attempt,
                seed=seed,
                raw_output=result.text,
                error=error,
                latency_s=latency,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
            )
        )
        if raw is not None:
            break

    prompt_tokens = _sum([a.prompt_tokens for a in attempts])
    completion_tokens = _sum([a.completion_tokens for a in attempts])
    cost = None
    rates = config.cost
    if (
        rates.input_per_1k_tokens is not None
        and rates.output_per_1k_tokens is not None
        and prompt_tokens is not None
        and completion_tokens is not None
    ):
        cost = round(
            prompt_tokens / 1000 * rates.input_per_1k_tokens
            + completion_tokens / 1000 * rates.output_per_1k_tokens,
            8,
        )
    totals = {
        "messages": messages,
        "prompt_sha256": prompt_sha,
        "attempts": attempts,
        "latency_s": sum(a.latency_s for a in attempts),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost": cost,
        "cost_currency": rates.currency if cost is not None else None,
    }
    if raw is None:
        any_output = any(a.raw_output is not None for a in attempts)
        return JudgeRecord(
            **common,
            **totals,
            status="invalid_output" if any_output else "error",
            validation_issues=[a.error for a in attempts if a.error],
        )
    dims, claims, issues = validate_output(raw, item, record.response.text, supplied_ids)
    return JudgeRecord(
        **common, **totals, status="ok", validation_issues=issues, dimensions=dims, claims=claims
    )


def judge_run(
    run_dir: Path,
    judge_config_path: Path,
    *,
    source_files: Sequence[Path],
    passage_files: Sequence[Path],
    prompt_versions: Sequence[str] | None = None,
    repeats: int = 1,
    overwrite: bool = False,
    repo_root: Path | None = None,
    adapter_factory: Callable[[ModelConfig], ModelAdapter] = create_adapter,
) -> JudgeRunResult:
    if repeats < 1:
        raise JudgeRunError("repeats must be at least 1")
    config = load_judge_config(judge_config_path)
    versions = list(prompt_versions or [config.prompt_version])
    unknown = [v for v in versions if v not in PROMPTS]
    if unknown:
        raise JudgeRunError(f"unknown prompt version(s) {unknown}; known: {sorted(PROMPTS)}")

    manifest_path, responses_path = run_dir / "manifest.json", run_dir / "responses.jsonl"
    if not manifest_path.is_file() or not responses_path.is_file():
        raise JudgeRunError(f"{run_dir} is not a run directory (manifest.json/responses.jsonl)")
    out_dir = run_dir / JUDGEMENTS_DIR
    out_path = out_dir / f"{config.judge_id}.jsonl"
    if out_path.exists() and not overwrite:
        raise JudgeRunError(f"{out_path} already exists (use --overwrite to re-judge)")

    run_manifest = RunManifest.model_validate_json(manifest_path.read_text())
    dataset = Path(run_manifest.dataset_path)
    if not dataset.is_file() or sha256_file(dataset) != run_manifest.dataset_sha256:
        raise JudgeRunError(f"dataset {dataset} is missing or has changed since the run")
    report = validate_dataset([dataset], source_files, passage_files)
    if not report.ok:
        raise JudgeRunError("dataset failed validation; run 'liverswat validate'")
    registry, _ = EvidenceRegistry.load(source_files, passage_files)
    items = {i.question_id: i for _, i in read_jsonl_models(dataset, BenchmarkItem)[0]}
    responses, issues = read_jsonl_models(responses_path, ResponseRecord)
    if issues:
        raise JudgeRunError(f"invalid response records: {issues[0]}")

    started = datetime.now(UTC)
    adapter = adapter_factory(config.model)  # may raise AdapterError: nothing written yet
    judgements: list[JudgeRecord] = []
    try:
        for _, record in responses:
            item = items[record.question_id]
            for version in versions:
                for repeat in range(repeats):
                    judgements.append(
                        judge_one(
                            adapter=adapter,
                            config=config,
                            record=record,
                            item=item,
                            registry=registry,
                            prompt_version=version,
                            repeat=repeat,
                        )
                    )
        backend_info = adapter.runtime_info()
    finally:
        adapter.close()

    out_dir.mkdir(exist_ok=True)
    out_path.write_text("".join(j.model_dump_json() + "\n" for j in judgements), encoding="utf-8")
    labels = [*run_manifest.status_labels, JUDGE_LABEL]
    if config.evidence_policy == EvidencePolicy.INCLUDE_UNVERIFIED:
        labels.append("JUDGES WERE SHOWN UNVERIFIED EVIDENCE - DEVELOPMENT USE ONLY")
    manifest = JudgeRunManifest(
        experiment_id=run_manifest.experiment_id,
        judge_id=config.judge_id,
        judge_config_path=str(judge_config_path),
        judge_config_sha256=sha256_file(judge_config_path),
        judge_config=config.model_dump(mode="json"),
        prompt_versions=versions,
        repeats=repeats,
        status_labels=labels,
        started_at=started,
        completed_at=datetime.now(UTC),
        n_judgements=len(judgements),
        n_by_status=dict(Counter(j.status for j in judgements)),
        responses_sha256=sha256_file(responses_path),
        dataset_sha256=run_manifest.dataset_sha256,
        registry_files={str(p): sha256_file(p) for p in [*source_files, *passage_files]},
        environment=capture_environment(repo_root or Path.cwd(), backend_info),
    )
    (out_dir / f"{config.judge_id}.manifest.json").write_text(
        manifest.model_dump_json(indent=2) + "\n"
    )
    return JudgeRunResult(path=out_path, manifest=manifest)
