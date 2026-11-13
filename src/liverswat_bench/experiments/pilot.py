"""Real-model pilot: run models x evidence conditions, score, judge, report, summarise.

The pilot configuration is a YAML file (see ``configs/experiments/``). Steps
that already have outputs are skipped, so an interrupted pilot can resume.
Every rate in the summary is reported with its numerator and denominator.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean, median
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from liverswat_bench.evaluation.combine import CombinePolicy, CombineSettings, combine
from liverswat_bench.evaluation.dimensions import Dimension
from liverswat_bench.evaluation.records import ResponseRecord, RunManifest
from liverswat_bench.evaluation.runner import run_evaluation
from liverswat_bench.evaluation.score_run import score_run
from liverswat_bench.evaluation.scoring_records import DimensionStatus
from liverswat_bench.io import read_jsonl_models
from liverswat_bench.judges.oversight import oversight_metrics
from liverswat_bench.judges.runner import judge_run
from liverswat_bench.judges.schema import load_judge_config
from liverswat_bench.models.config import load_model_config
from liverswat_bench.reporting.summary import load_scored_run
from liverswat_bench.reporting.writers import write_comparison, write_report

PILOT_SUMMARY_VERSION = "pilot-summary-1"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SensitivitySpec(_Strict):
    judges: list[Path]
    prompt_variants: list[str]
    conditions: list[str] = Field(default_factory=lambda: ["baseline"])


class PilotConfig(_Strict):
    pilot_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*$")
    description: str
    result_label: str
    dataset: Path
    data_dir: Path = Path("data")
    output_dir: Path
    models: list[Path] = Field(min_length=1)
    conditions: list[str] = Field(default_factory=lambda: ["baseline"])
    retrieval_top_k: int = Field(default=3, ge=1)
    trials: int = Field(default=1, ge=1)
    judges: list[Path] = Field(default_factory=list)
    #: Canonical judge prompt version: used for judge runs, combination and the summary.
    judge_prompt_version: str = "v1"
    judge_repeats: int = Field(default=1, ge=1)
    prompt_sensitivity: SensitivitySpec | None = None
    combine_policy: CombinePolicy = CombinePolicy.RULES_FIRST_REVIEW_ON_DISAGREEMENT
    min_judges: int = Field(default=2, ge=1)


def load_pilot_config(path: Path) -> PilotConfig:
    return PilotConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def combine_settings(config: PilotConfig) -> CombineSettings:
    return CombineSettings(
        policy=config.combine_policy,
        min_judges=config.min_judges,
        canonical_prompt_version=config.judge_prompt_version,
    )


def run_dir_name(model_config_id: str, condition: str) -> str:
    return f"{model_config_id}__{condition}"


def run_pilot(
    config: PilotConfig,
    *,
    source_files: list[Path],
    passage_files: list[Path],
    log: Callable[[str], None] = print,
    repo_root: Path | None = None,
    judge_only: bool = False,
    dry_run: bool = False,
) -> Path | list[str]:
    """Run the pending pilot steps. Return the output directory.

    ``judge_only``: never run model inference or scoring. Stop with an error if a run
    directory has no model responses or no scores.
    ``dry_run``: run nothing and write nothing. Return the list of pending steps.
    """
    out = config.output_dir
    pending: list[str] = []
    if not dry_run:
        out.mkdir(parents=True, exist_ok=True)
    run_dirs: list[Path] = []
    for model_path in config.models:
        model_id = load_model_config(model_path).config_id
        for condition in config.conditions:
            run_dir = out / run_dir_name(model_id, condition)
            run_dirs.append(run_dir)
            if not (run_dir / "manifest.json").is_file():
                if run_dir.exists():
                    raise RuntimeError(
                        f"{run_dir} exists without a manifest (an interrupted run); "
                        "inspect and remove it, then resume"
                    )
                if judge_only:
                    raise RuntimeError(
                        f"{run_dir} has no model responses; --judge-only does not run model "
                        "inference"
                    )
                pending.append(f"[evaluate] {model_id} / {condition}")
                if not dry_run:
                    log(f"[evaluate] {model_id} / {condition}")
                    run_evaluation(
                        model_config_path=model_path,
                        dataset_path=config.dataset,
                        source_files=source_files,
                        passage_files=passage_files,
                        output_dir=out,
                        experiment_id=run_dir.name,
                        trials=config.trials,
                        evidence_condition=condition,
                        retrieval_top_k=config.retrieval_top_k,
                        repo_root=repo_root,
                        progress=lambda msg: log(f"  {msg}"),
                    )
            if not (run_dir / "scores.jsonl").is_file():
                if judge_only and (run_dir / "manifest.json").is_file():
                    raise RuntimeError(
                        f"{run_dir} has no scores; run 'liverswat score' before --judge-only"
                    )
                pending.append(f"[score] {run_dir.name}")
                if not dry_run:
                    log(f"[score] {run_dir.name}")
                    score_run(run_dir, source_files=source_files, passage_files=passage_files)
            for judge_path in config.judges:
                judge_id = load_judge_config(judge_path).judge_id
                if not (run_dir / "judgements" / f"{judge_id}.jsonl").is_file():
                    pending.append(f"[judge] {judge_id} on {run_dir.name}")
                    if dry_run:
                        continue
                    log(f"[judge] {judge_id} on {run_dir.name}")
                    judge_run(
                        run_dir,
                        judge_path,
                        source_files=source_files,
                        passage_files=passage_files,
                        prompt_versions=[config.judge_prompt_version],
                        repeats=config.judge_repeats,
                        repo_root=repo_root,
                    )
            sens = config.prompt_sensitivity
            if sens and condition in sens.conditions:
                for judge_path in sens.judges:
                    judge_id = load_judge_config(judge_path).judge_id
                    path = run_dir / "judgements" / f"{judge_id}.jsonl"
                    versions = (
                        {
                            json.loads(line)["prompt_version"]
                            for line in path.read_text().splitlines()
                            if line.strip()
                        }
                        if path.is_file()
                        else set()
                    )
                    if not set(sens.prompt_variants) <= versions:
                        pending.append(f"[judge sensitivity] {judge_id} on {run_dir.name}")
                        if dry_run:
                            continue
                        log(f"[judge sensitivity] {judge_id} on {run_dir.name}")
                        judge_run(
                            run_dir,
                            judge_path,
                            source_files=source_files,
                            passage_files=passage_files,
                            prompt_versions=[config.judge_prompt_version, *sens.prompt_variants],
                            repeats=config.judge_repeats,
                            overwrite=True,
                            repo_root=repo_root,
                        )
            if not dry_run:
                write_report(load_scored_run(run_dir), run_dir / "report", combine_settings(config))
    if dry_run:
        return pending
    settings = combine_settings(config)
    runs = [load_scored_run(d) for d in run_dirs]
    write_comparison(runs, out / "comparison", settings)
    summary = summarise_pilot(config, run_dirs, settings)
    (out / "pilot_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / "pilot_summary.md").write_text(render_pilot_markdown(summary))
    log(f"[done] {out / 'pilot_summary.md'}")
    return out


def _rate(k: int, n: int) -> dict[str, Any]:
    return {"numerator": k, "denominator": n, "rate": round(k / n, 4) if n else None}


def summarise_run_dir(run_dir: Path, settings: CombineSettings) -> dict[str, Any]:
    run = load_scored_run(run_dir)
    manifest: RunManifest = run.run_manifest
    responses = [r for _, r in read_jsonl_models(run_dir / "responses.jsonl", ResponseRecord)[0]]
    ok = [r for r in responses if r.status == "ok"]
    latencies = [r.timing.latency_s for r in ok]
    recalls = [r.evidence.oracle_recall for r in responses if r.evidence.oracle_recall is not None]

    applicable = [
        d
        for s in run.scores
        for d in s.dimension_scores
        if d.status != DimensionStatus.NOT_APPLICABLE
    ]
    rule_abstained = sum(d.status == DimensionStatus.ABSTAINED for d in applicable)
    contradicted_checks = [
        c for s in run.scores for c in s.checks if c.kind == "contradicted_claim"
    ]
    rule_factual = {
        s.question_id: d.score
        for s in run.scores
        for d in s.dimension_scores
        if d.dimension == Dimension.FACTUAL_ACCURACY and d.status == DimensionStatus.SCORED
    }

    out: dict[str, Any] = {
        "run": run_dir.name,
        "model": manifest.model_settings["model_name"],
        "model_revision": manifest.model_settings["model_revision"],
        "backend": manifest.model_settings["backend"],
        "evidence_condition": manifest.evidence_condition,
        "status_labels": manifest.status_labels,
        "n_items": manifest.n_items,
        "valid_model_responses": _rate(len(ok), len(responses)),
        "model_latency_s": {
            "n": len(latencies),
            "mean": round(fmean(latencies), 3) if latencies else None,
            "median": round(median(latencies), 3) if latencies else None,
        },
        "model_tokens": {
            "prompt": sum(r.response.prompt_tokens or 0 for r in ok),
            "completion": sum(r.response.completion_tokens or 0 for r in ok),
        },
        "retrieval_oracle_recall_mean": round(fmean(recalls), 4) if recalls else None,
        "retrieval_n": len(recalls),
        "rules": {
            "abstention": _rate(rule_abstained, len(applicable)),
            "contradicted_claim_detected": _rate(
                sum(c.outcome == "detected" for c in contradicted_checks), len(contradicted_checks)
            ),
            "critical_rule_detected_records": sum(
                any(f.status == "rule_detected" for f in s.critical_flags) for s in run.scores
            ),
            "critical_needs_review_records": sum(
                any(f.status == "needs_review" for f in s.critical_flags) for s in run.scores
            ),
            "factual_accuracy_mean": round(fmean(rule_factual.values()), 4)
            if rule_factual
            else None,
            "factual_accuracy_n_items": len(rule_factual),
        },
    }
    if not run.judgements:
        out["judges"] = None
        return out

    canonical = [
        j
        for j in run.judgements
        if j.prompt_version == settings.canonical_prompt_version and j.repeat == 0
    ]
    per_judge = {}
    for jid in sorted({j.judge_id for j in canonical}):
        js = [j for j in canonical if j.judge_id == jid]
        attempted = [j for j in js if j.status != "skipped_no_response"]
        valid = [j for j in attempted if j.status == "ok"]
        dims = [d for j in valid for d in j.dimensions if d.status != "not_applicable"]
        claims = [c for j in valid for c in j.claims]
        per_judge[jid] = {
            "valid_judge_results": _rate(len(valid), len(attempted)),
            "abstention": _rate(sum(d.status == "abstained" for d in dims), len(dims)),
            "invalidated_dimensions": _rate(sum(d.status == "invalid" for d in dims), len(dims)),
            "claims_total": len(claims),
            "unsupported_claims": _rate(
                sum(c.classification == "unsupported" for c in claims), len(claims)
            ),
            "contradicted_claims": _rate(
                sum(c.classification == "contradicted" for c in claims), len(claims)
            ),
            "claims_needing_review": _rate(sum(c.needs_review for c in claims), len(claims)),
            "potentially_dangerous_claims": sum(c.potentially_dangerous for c in claims),
            "mean_latency_s": round(fmean(j.latency_s for j in attempted), 3)
            if attempted
            else None,
        }
    combined = combine(run.scores, run.judgements, settings)
    cdims = [d for c in combined for d in c.dimensions if d.combined_status != "not_applicable"]
    pairs = [d for d in cdims if d.consensus in ("consensus", "judges_disagree")]
    rule_judge = [d for d in cdims if d.rule_judge_difference is not None]
    oversight = oversight_metrics(run.judgements, run.scores, settings.canonical_prompt_version)
    out["judges"] = {
        "per_judge": per_judge,
        "judge_disagreement": _rate(
            sum(d.consensus == "judges_disagree" for d in pairs), len(pairs)
        ),
        "rule_vs_judge_material_disagreement": _rate(
            sum(d.material_disagreement for d in rule_judge), len(rule_judge)
        ),
        "combined_abstention_or_review": _rate(
            sum(d.combined_status in ("abstained", "needs_review") for d in cdims), len(cdims)
        ),
        "combined_filled_by_judge_consensus": _rate(
            sum(d.combined_source == "judge_consensus" for d in cdims), len(cdims)
        ),
        "prompt_sensitivity": oversight["prompt_sensitivity"],
    }
    return out


def _item_statuses(dataset: Path) -> dict[str, int]:
    from liverswat_bench.datasets.schema import BenchmarkItem

    items = [i for _, i in read_jsonl_models(dataset, BenchmarkItem)[0]]
    return dict(Counter(i.verification_status.value for i in items))


def summarise_pilot(
    config: PilotConfig, run_dirs: list[Path], settings: CombineSettings
) -> dict[str, Any]:
    return {
        "summary_version": PILOT_SUMMARY_VERSION,
        "pilot_id": config.pilot_id,
        "created_at": datetime.now(UTC).isoformat(),
        "result_label": config.result_label,
        "description": config.description,
        "dataset": str(config.dataset),
        "conditions": config.conditions,
        "combine_policy": settings.policy.value,
        "judge_prompt_version": settings.canonical_prompt_version,
        "notes": [
            "Agreement between automated evaluators measures consistency, not correctness.",
            "No independent reference standard exists; evaluator accuracy is not reported.",
        ],
        "items_by_verification_status": _item_statuses(config.dataset),
        "runs": [summarise_run_dir(d, settings) for d in run_dirs],
    }


def _fmt_rate(r: dict[str, Any] | None) -> str:
    if not r:
        return "n/a"
    if r["rate"] is None:
        return f"n/a (0/{r['denominator']})"
    return f"{r['rate']:.2f} ({r['numerator']}/{r['denominator']})"


def render_pilot_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"# Pilot summary: {summary['pilot_id']}",
        "",
        f"> **{summary['result_label']}**",
        "",
        *[f"- {n}" for n in summary["notes"]],
        "",
        f"Dataset: `{summary['dataset']}`. Combination policy: `{summary['combine_policy']}`.",
        "",
        f"Benchmark items by verification status: {summary['items_by_verification_status']}. "
        "Only source_verified items can produce primary benchmark results.",
        "",
        "## Model responses and rule-based evaluation",
        "",
        "| Run | Model | Condition | Items | Valid responses | Mean latency (s) | "
        "Oracle recall | Rule abstention | Contradicted (rules) | Critical (rule / review) | "
        "Factual mean (rules) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in summary["runs"]:
        rules = r["rules"]
        recall = (
            f"{r['retrieval_oracle_recall_mean']:.2f} (n={r['retrieval_n']})"
            if r["retrieval_oracle_recall_mean"] is not None
            else "n/a"
        )
        fact = (
            f"{rules['factual_accuracy_mean']:.2f} (n={rules['factual_accuracy_n_items']})"
            if rules["factual_accuracy_mean"] is not None
            else "n/a"
        )
        cells = [
            r["run"],
            f"`{r['model']}`",
            r["evidence_condition"],
            str(r["n_items"]),
            _fmt_rate(r["valid_model_responses"]),
            str(r["model_latency_s"]["mean"]),
            recall,
            _fmt_rate(rules["abstention"]),
            _fmt_rate(rules["contradicted_claim_detected"]),
            f"{rules['critical_rule_detected_records']} / {rules['critical_needs_review_records']}",
            fact,
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Judge models and combined evaluation",
        "",
        "| Run | Judge disagreement | Rule vs judge (material) | Combined abstention or review | "
        "Filled by judge consensus |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in summary["runs"]:
        j = r["judges"]
        if not j:
            lines.append(
                f"| {r['run']} | not executed | not executed | not executed | not executed |"
            )
            continue
        lines.append(
            f"| {r['run']} | {_fmt_rate(j['judge_disagreement'])} | "
            f"{_fmt_rate(j['rule_vs_judge_material_disagreement'])} | "
            f"{_fmt_rate(j['combined_abstention_or_review'])} | "
            f"{_fmt_rate(j['combined_filled_by_judge_consensus'])} |"
        )
    lines += [
        "",
        "| Run | Judge | Valid judge results | Abstention | Invalidated | Unsupported claims | "
        "Contradicted claims | Claims needing review | Dangerous | Mean latency (s) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in summary["runs"]:
        if not r["judges"]:
            continue
        for jid, pj in r["judges"]["per_judge"].items():
            cells = [
                r["run"],
                jid,
                _fmt_rate(pj["valid_judge_results"]),
                _fmt_rate(pj["abstention"]),
                _fmt_rate(pj["invalidated_dimensions"]),
                _fmt_rate(pj["unsupported_claims"]),
                _fmt_rate(pj["contradicted_claims"]),
                _fmt_rate(pj["claims_needing_review"]),
                str(pj["potentially_dangerous_claims"]),
                str(pj["mean_latency_s"]),
            ]
            lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "## Prompt sensitivity (judge models)", ""]
    any_sens = False
    for r in summary["runs"]:
        if not r["judges"]:
            continue
        for jid, ps in r["judges"]["prompt_sensitivity"].items():
            for variant, v in ps["variants"].items():
                any_sens = True
                exact = "n/a" if v["exact_agreement"] is None else f"{v['exact_agreement']:.2f}"
                lines.append(
                    f"- {r['run']} / {jid}: `{variant}` vs `{ps['canonical_prompt_version']}`: "
                    f"exact agreement {exact} "
                    f"(n={v['n']}), abstention flips {v['abstention_flips']} "
                    f"(of {v['n_compared']})"
                )
    if not any_sens:
        lines.append("Not executed.")
    lines.append("")
    return "\n".join(lines)
