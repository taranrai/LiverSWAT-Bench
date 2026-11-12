"""Write run reports (JSON, CSV, Markdown) and multi-run comparisons."""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from liverswat_bench.evaluation.combine import CombinedRecord, CombineSettings
from liverswat_bench.evaluation.dimensions import Dimension
from liverswat_bench.evaluation.records import NOT_CLINICAL_LABEL
from liverswat_bench.evaluation.scoring_records import SCORING_LABEL, ScoreRecord
from liverswat_bench.reporting.judge_report import build_judge_section, render_judge_markdown
from liverswat_bench.reporting.summary import ScoredRun, summarise_run

DIM_LABELS = {
    Dimension.FACTUAL_ACCURACY: "Factual accuracy",
    Dimension.SAFETY_BEHAVIOUR: "Safety behaviour",
    Dimension.UK_EVIDENCE_ALIGNMENT: "UK evidence alignment",
    Dimension.ACTIONABILITY: "Actionability",
    Dimension.COMMUNICATION_QUALITY: "Communication quality",
    Dimension.UNCERTAINTY_HANDLING: "Uncertainty handling",
}

LIMITATIONS = [
    "Scores come from researcher-authored detection rules applied sentence by sentence. "
    "A rule match shows that wording is present, not that the statement is clinically correct.",
    "Only statements covered by an item's rules are assessed; the rest of each response "
    "is unassessed.",
    "Rule-based scoring cannot award 4; UK evidence alignment, actionability and "
    "communication quality are never scored by rules (only by judge consensus, if judges ran).",
    "Aggregate scores are computed only when every applicable dimension is scored; "
    "missing and abstained scores are never treated as zero.",
    "Critical flags are rule-detected and require human review. They are not clinical "
    "harm assessments.",
    "Dimension weights are provisional research design choices.",
]


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def item_rows(scores: Sequence[ScoreRecord]) -> list[dict[str, Any]]:
    rows = []
    for s in scores:
        row: dict[str, Any] = {
            "record_id": s.record_id,
            "question_id": s.question_id,
            "trial": s.trial,
            "track": s.provenance.track.value,
            "verification_status": s.provenance.verification_status.value,
            "evidence_level": s.provenance.evidence_level.value,
            "synthetic": s.provenance.synthetic,
            "primary_eligible": s.provenance.primary_eligible,
            "response_status": s.response_status,
        }
        for d in s.dimension_scores:
            row[f"{d.dimension.value}_status"] = d.status.value
            row[f"{d.dimension.value}_score"] = d.score
        row["aggregate_status"] = s.aggregate.status
        row["aggregate_score"] = s.aggregate.score
        row["critical_rule_detected"] = sum(f.status == "rule_detected" for f in s.critical_flags)
        row["critical_needs_review"] = sum(f.status == "needs_review" for f in s.critical_flags)
        row["checks_needing_review"] = sum(c.outcome == "needs_review" for c in s.checks)
        rows.append(row)
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        if not rows:
            fh.write("")
            return
        # Union of keys in first-seen order: rows may differ (e.g. judged vs unjudged runs).
        fieldnames = list(dict.fromkeys(k for row in rows for k in row))
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def dimension_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for part, ps in summary["partitions"].items():
        for dim, d in ps["dimensions"].items():
            rows.append(
                {
                    "partition": part,
                    "dimension": dim,
                    "weight": d["weight"],
                    "n_items_scored": d["n_items_scored"],
                    "case_level_mean": d["case_level_mean"],
                    "n_records_scored": d["n_records"]["scored"],
                    "n_records_abstained": d["n_records"]["abstained"],
                    "n_records_missing": d["n_records"]["missing"],
                    "n_records_not_applicable": d["n_records"]["not_applicable"],
                }
            )
    return rows


def _partition_md(title: str, ps: dict[str, Any], primary: bool) -> list[str]:
    lines = [f"## {title}", ""]
    if ps["n_records"] == 0:
        if primary:
            lines += [
                "**No primary-eligible items in this run. No primary benchmark scores are "
                "reported.** Primary eligibility requires Level A, `source_verified`, "
                "non-synthetic, primary-track items linked to verified evidence.",
                "",
            ]
        else:
            lines += ["No records.", ""]
        return lines
    if not primary:
        lines += [
            "> These records are **not primary benchmark results** (synthetic, exploratory, "
            "experimental or unverified items). Use them for development only.",
            "",
        ]
    lines += [
        f"- Items: {ps['n_items']} · Records: {ps['n_records']} · "
        f"Generation errors: {ps['n_generation_errors']} · "
        f"Synthetic items: {ps['n_synthetic_items']}",
        f"- Items by track: {ps['items_by_track']}",
        f"- Items by verification status: {ps['items_by_verification_status']}",
        "",
        "| Dimension | Weight | Items scored | Case-level mean (0-4) | Scored | Abstained | "
        "Missing | N/A |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for dim in Dimension:
        d = ps["dimensions"][dim.value]
        n = d["n_records"]
        lines.append(
            f"| {DIM_LABELS[dim]} | {d['weight']:.2f} | {d['n_items_scored']} | "
            f"{_fmt(d['case_level_mean'])} | {n['scored']} | {n['abstained']} | "
            f"{n['missing']} | {n['not_applicable']} |"
        )
    agg = ps["aggregate"]
    lines += [
        "",
        f"**Aggregate:** {agg['n_records']} · case-level mean of complete aggregates: "
        f"{_fmt(agg['case_level_mean_of_complete'])} "
        f"({agg['n_items_with_complete_aggregate']} item(s)). An aggregate is only computed "
        "when every applicable dimension is scored.",
        "",
        "### Critical safety flags (reported separately from scores)",
        "",
        f"- Records with rule-detected critical failures: "
        f"{ps['critical_flags']['n_records_rule_detected']}",
        f"- Records with possible critical failures needing review: "
        f"{ps['critical_flags']['n_records_needs_review']}",
        f"- Records with critical checks that have no rule (unchecked): "
        f"{ps['critical_flags']['n_records_with_unchecked_critical']}",
        "",
    ]
    if ps["critical_flags"]["flags"]:
        lines += [
            "| Question | Trial | Check | Status | Response excerpt |",
            "| --- | --- | --- | --- | --- |",
        ]
        for f in ps["critical_flags"]["flags"]:
            excerpt = (f["excerpt"] or "").replace("|", "\\|")
            lines.append(
                f"| {f['question_id']} | {f['trial']} | {f['check_id']} ({f['kind']}) | "
                f"{f['status']} | {excerpt} |"
            )
        lines.append("")

    lines += ["### Abstentions and missing scores", ""]
    any_reason = False
    for dim in Dimension:
        reasons = ps["dimensions"][dim.value]["abstention_and_missing_reasons"]
        for reason, count in reasons.items():
            any_reason = True
            lines.append(f"- {DIM_LABELS[dim]}: {reason} ({count})")
    if not any_reason:
        lines.append("- None")
    lines += [
        "",
        "### Check outcomes and claim assessments",
        "",
        f"- Check outcomes: {ps['check_outcomes']}",
        f"- Claim classifications: {ps['claim_assessments']['by_classification']} "
        f"(abstained: {ps['claim_assessments']['n_abstained']})",
    ]
    if ps["ineligibility_reasons"]:
        lines.append(f"- Reasons items are not primary-eligible: {ps['ineligibility_reasons']}")
    lines.append("")
    return lines


def render_markdown(
    summary: dict[str, Any],
    scores: Sequence[ScoreRecord],
    judge_section: dict[str, Any] | None = None,
) -> str:
    m = summary["model"]
    lines = [
        f"# LiverSWAT-Bench report: {summary['experiment_id']}",
        "",
        *[f"> **{label}**  " for label in summary["status_labels"]],
        "",
        "## Run",
        "",
        f"- Model: `{m['model_name']}` (config `{m['config_id']}`, backend `{m['backend']}`, "
        f"revision `{m['model_revision'] or 'n/a'}`)",
        f"- Licence: {m['licence'] or 'not recorded'} · open weights: {m['open_weight']} · "
        f"OSI-approved licence: {m['osi_approved_licence']}",
        f"- Generation: {summary['generation']} · trials: {summary['trials']}",
        f"- Dataset: `{summary['dataset']['path']}` (sha256 "
        f"`{summary['dataset']['sha256'][:16]}…`)",
        f"- Scorer: `{summary['scorer']}` · scored at {summary['scored_at']}",
        f"- Git: {summary['git']}",
        f"- {summary['weights_note']}",
        "",
    ]
    lines += _partition_md("Primary benchmark results", summary["partitions"]["primary"], True)
    lines += _partition_md(
        "Non-primary results (development only)", summary["partitions"]["non_primary"], False
    )
    lines += [
        "## Per-record scores",
        "",
        "| Question | Trial | Track | Primary | "
        + " | ".join(DIM_LABELS[d] for d in Dimension)
        + " | Aggregate | Critical |",
        "| --- | --- | --- | --- | " + " | ".join("---" for _ in Dimension) + " | --- | --- |",
    ]
    for s in scores:
        cells = []
        for d in s.dimension_scores:
            cells.append(str(d.score) if d.score is not None else d.status.value.replace("_", " "))
        crit = ", ".join(f"{f.check_id}:{f.status}" for f in s.critical_flags) or "none"
        agg = _fmt(s.aggregate.score) if s.aggregate.score is not None else s.aggregate.status
        lines.append(
            f"| {s.question_id} | {s.trial} | {s.provenance.track.value} | "
            f"{'yes' if s.provenance.primary_eligible else 'no'} | "
            + " | ".join(cells)
            + f" | {agg} | {crit} |"
        )
    if judge_section:
        lines += ["", *render_judge_markdown(judge_section)]
    lines += ["", "## Limitations", "", *[f"- {item}" for item in LIMITATIONS], ""]
    return "\n".join(lines)


def combined_rows(records: Sequence[CombinedRecord]) -> list[dict[str, Any]]:
    rows = []
    for c in records:
        row: dict[str, Any] = {
            "record_id": c.record_id,
            "question_id": c.question_id,
            "trial": c.trial,
            "primary_eligible": c.primary_eligible,
            "policy": c.policy.value,
        }
        for d in c.dimensions:
            key = d.dimension.value
            row[f"{key}_rule"] = d.rule_score
            for jid, v in d.judge_scores.items():
                row[f"{key}_judge_{jid}"] = v
            row[f"{key}_consensus"] = d.consensus
            row[f"{key}_combined_status"] = d.combined_status
            row[f"{key}_combined"] = d.combined_score
            row[f"{key}_source"] = d.combined_source
        row["combined_aggregate_status"] = c.combined_aggregate.status
        row["combined_aggregate"] = c.combined_aggregate.score
        row["judge_flagged_dangerous_claims"] = len(c.judge_flagged_dangerous_claims)
        rows.append(row)
    return rows


def write_report(
    run: ScoredRun, out_dir: Path, settings: CombineSettings | None = None
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = summarise_run(run)
    judge_section = build_judge_section(run, settings or CombineSettings())
    paths = {
        "summary_json": out_dir / "summary.json",
        "item_scores_csv": out_dir / "item_scores.csv",
        "dimension_summary_csv": out_dir / "dimension_summary.csv",
        "report_md": out_dir / "report.md",
    }
    if judge_section:
        combined = judge_section.pop("_combined_records")
        summary["judges"] = judge_section
        paths["combined_scores_jsonl"] = out_dir / "combined_scores.jsonl"
        paths["combined_scores_csv"] = out_dir / "combined_scores.csv"
        paths["oversight_json"] = out_dir / "oversight.json"
        paths["combined_scores_jsonl"].write_text(
            "".join(c.model_dump_json() + "\n" for c in combined), encoding="utf-8"
        )
        _write_csv(paths["combined_scores_csv"], combined_rows(combined))
        paths["oversight_json"].write_text(
            json.dumps(judge_section["oversight"], indent=2) + "\n", encoding="utf-8"
        )
    paths["summary_json"].write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _write_csv(paths["item_scores_csv"], item_rows(run.scores))
    _write_csv(paths["dimension_summary_csv"], dimension_rows(summary))
    paths["report_md"].write_text(
        render_markdown(summary, run.scores, judge_section), encoding="utf-8"
    )
    return paths


# ------------------------------------------------------------------ compare


def compare_runs(
    runs: Sequence[ScoredRun], settings: CombineSettings | None = None
) -> dict[str, Any]:
    settings = settings or CombineSettings()
    summaries = [summarise_run(r) for r in runs]
    judge_sections = [build_judge_section(r, settings) for r in runs]
    warnings = []
    if len({s["dataset"]["sha256"] for s in summaries}) > 1:
        warnings.append("Runs used different datasets; results are not directly comparable.")
    if len({s["scorer"] for s in summaries}) > 1:
        warnings.append("Runs were scored with different scorer versions.")
    if any(s["partitions"]["non_primary"]["n_synthetic_items"] for s in summaries):
        warnings.append("Some runs include synthetic demonstration items (non-primary).")
    if all(s["partitions"]["primary"]["n_records"] == 0 for s in summaries):
        warnings.append("No run contains primary-eligible items: no primary results to compare.")
    rows = []
    for s, js in zip(summaries, judge_sections, strict=True):
        for part in ("primary", "non_primary"):
            ps = s["partitions"][part]
            row = {
                "experiment_id": s["experiment_id"],
                "model_name": s["model"]["model_name"],
                "model_revision": s["model"]["model_revision"],
                "backend": s["model"]["backend"],
                "dataset_sha256": s["dataset"]["sha256"],
                "scorer": s["scorer"],
                "partition": part,
                "n_items": ps["n_items"],
                "n_records": ps["n_records"],
                "n_generation_errors": ps["n_generation_errors"],
            }
            for dim in Dimension:
                d = ps["dimensions"][dim.value]
                row[f"{dim.value}_mean"] = d["case_level_mean"]
                row[f"{dim.value}_n_items"] = d["n_items_scored"]
            row["aggregate_mean_of_complete"] = ps["aggregate"]["case_level_mean_of_complete"]
            row["critical_rule_detected_records"] = ps["critical_flags"]["n_records_rule_detected"]
            row["critical_needs_review_records"] = ps["critical_flags"]["n_records_needs_review"]
            row["judges"] = ",".join(j["judge_id"] for j in js["judges"]) if js else ""
            if js:
                cs = js["combined"][part]
                for dim in Dimension:
                    cd = cs["dimensions"][dim.value]
                    row[f"{dim.value}_combined_mean"] = cd["combined_case_level_mean"]
                    row[f"{dim.value}_combined_n_items"] = cd["n_items_scored"]
                row["combined_aggregate_mean_of_complete"] = cs["combined_aggregate"][
                    "case_level_mean_of_complete"
                ]
                row["rule_judge_material_disagreements"] = sum(
                    cs["dimensions"][d.value]["n_material_rule_judge_disagreements"]
                    for d in Dimension
                )
                row["judge_vs_judge_disagreements"] = sum(
                    cs["dimensions"][d.value]["consensus"].get("judges_disagree", 0)
                    for d in Dimension
                )
                row["judge_flagged_dangerous_records"] = cs[
                    "n_records_with_judge_flagged_dangerous_claims"
                ]
            rows.append(row)
    return {
        "labels": [NOT_CLINICAL_LABEL, SCORING_LABEL],
        "note": "Descriptive side-by-side summary only. Paired, case-level statistical "
        "comparison is planned for Milestone 7.",
        "warnings": warnings,
        "rows": rows,
    }


def write_comparison(
    runs: Sequence[ScoredRun], out_dir: Path, settings: CombineSettings | None = None
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    comparison = compare_runs(runs, settings)
    paths = {
        "comparison_json": out_dir / "comparison.json",
        "comparison_csv": out_dir / "comparison.csv",
        "comparison_md": out_dir / "comparison.md",
    }
    paths["comparison_json"].write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    _write_csv(paths["comparison_csv"], comparison["rows"])
    lines = [
        "# LiverSWAT-Bench run comparison",
        "",
        *[f"> **{label}**  " for label in comparison["labels"]],
        "",
        comparison["note"],
        "",
    ]
    lines += [f"- ⚠️ {w}" for w in comparison["warnings"]]
    for part, title in (("primary", "Primary results"), ("non_primary", "Non-primary (dev only)")):
        lines += [
            "",
            f"## {title}",
            "",
            "| Run | Model | Revision | Items | "
            + " | ".join(DIM_LABELS[d] for d in Dimension)
            + " | Aggregate | Critical (detected / review) |",
            "| --- | --- | --- | --- | " + " | ".join("---" for _ in Dimension) + " | --- | --- |",
        ]
        for r in comparison["rows"]:
            if r["partition"] != part:
                continue
            dims = " | ".join(
                f"{_fmt(r[f'{d.value}_mean'])} (n={r[f'{d.value}_n_items']})" for d in Dimension
            )
            lines.append(
                f"| {r['experiment_id']} | `{r['model_name']}` | {r['model_revision'] or 'n/a'} | "
                f"{r['n_items']} | {dims} | {_fmt(r['aggregate_mean_of_complete'])} | "
                f"{r['critical_rule_detected_records']} / {r['critical_needs_review_records']} |"
            )
    judged = [r for r in comparison["rows"] if r.get("judges")]
    if judged:
        lines += [
            "",
            "## Combined rule + judge view (automated; not clinical expert review)",
            "",
            "| Run | Partition | Judges | "
            + " | ".join(DIM_LABELS[d] for d in Dimension)
            + " | Aggregate | Rule/judge disagreements | Judge/judge disagreements | "
            "Judge-flagged dangerous |",
            "| --- | --- | --- | "
            + " | ".join("---" for _ in Dimension)
            + " | --- | --- | --- | --- |",
        ]
        for r in judged:
            if not r["n_records"]:
                continue
            dims = " | ".join(
                f"{_fmt(r[f'{d.value}_combined_mean'])} (n={r[f'{d.value}_combined_n_items']})"
                for d in Dimension
            )
            lines.append(
                f"| {r['experiment_id']} | {r['partition']} | {r['judges']} | {dims} | "
                f"{_fmt(r['combined_aggregate_mean_of_complete'])} | "
                f"{r['rule_judge_material_disagreements']} | "
                f"{r['judge_vs_judge_disagreements']} | {r['judge_flagged_dangerous_records']} |"
            )
    paths["comparison_md"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths
