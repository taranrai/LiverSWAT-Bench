"""Judge, combination and oversight sections of run reports."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import fmean
from typing import Any

from liverswat_bench.evaluation.combine import CombinedRecord, CombineSettings, combine
from liverswat_bench.evaluation.dimensions import Dimension
from liverswat_bench.judges.oversight import oversight_metrics
from liverswat_bench.reporting.summary import ScoredRun


def _case_mean(values_by_item: dict[str, list[float]]) -> tuple[float | None, int]:
    means = [fmean(v) for v in values_by_item.values() if v]
    return (round(fmean(means), 4) if means else None), len(means)


def summarise_combined(records: list[CombinedRecord]) -> dict[str, Any]:
    out: dict[str, Any] = {"n_records": len(records), "dimensions": {}}
    for dim in Dimension:
        rows = [next(d for d in r.dimensions if d.dimension == dim) for r in records]
        by_item: dict[str, list[float]] = defaultdict(list)
        for r, d in zip(records, rows, strict=True):
            if d.combined_score is not None:
                by_item[r.question_id].append(d.combined_score)
        mean, n_items = _case_mean(by_item)
        out["dimensions"][dim.value] = {
            "combined_case_level_mean": mean,
            "n_items_scored": n_items,
            "combined_status": dict(Counter(d.combined_status for d in rows)),
            "combined_source": dict(Counter(d.combined_source for d in rows)),
            "consensus": dict(Counter(d.consensus for d in rows)),
            "n_material_rule_judge_disagreements": sum(d.material_disagreement for d in rows),
        }
    agg_items: dict[str, list[float]] = defaultdict(list)
    for r in records:
        if r.combined_aggregate.status == "complete":
            agg_items[r.question_id].append(r.combined_aggregate.score)
    mean, n_items = _case_mean(agg_items)
    out["combined_aggregate"] = {
        "n_records": dict(Counter(r.combined_aggregate.status for r in records)),
        "case_level_mean_of_complete": mean,
        "n_items_with_complete_aggregate": n_items,
    }
    out["n_records_with_judge_flagged_dangerous_claims"] = sum(
        bool(r.judge_flagged_dangerous_claims) for r in records
    )
    return out


def build_judge_section(run: ScoredRun, settings: CombineSettings) -> dict[str, Any] | None:
    if not run.judgements:
        return None
    combined = combine(run.scores, run.judgements, settings)
    partitions = {
        "primary": [c for c in combined if c.primary_eligible],
        "non_primary": [c for c in combined if not c.primary_eligible],
    }
    disagreements = [
        {
            "record_id": c.record_id,
            "question_id": c.question_id,
            "dimension": d.dimension.value,
            "type": "rule_vs_judges" if d.material_disagreement else "judge_vs_judge",
            "rule_score": d.rule_score,
            "judge_scores": d.judge_scores,
            "consensus_score": d.consensus_score,
            "combined_status": d.combined_status,
        }
        for c in combined
        for d in c.dimensions
        if d.material_disagreement or d.consensus == "judges_disagree"
    ]
    labels = sorted({label for m in run.judge_manifests for label in m.status_labels})
    return {
        "labels": labels,
        "settings": {
            "policy": settings.policy.value,
            "min_judges": settings.min_judges,
            "judge_tolerance": settings.judge_tolerance,
            "rule_disagreement_threshold": settings.rule_disagreement_threshold,
            "canonical_prompt_version": settings.canonical_prompt_version,
        },
        "judges": [
            {
                "judge_id": m.judge_id,
                "model_name": m.judge_config["model"]["model_name"],
                "model_revision": m.judge_config["model"]["model_revision"],
                "backend": m.judge_config["model"]["backend"],
                "evidence_policy": m.judge_config["evidence_policy"],
                "prompt_versions": m.prompt_versions,
                "repeats": m.repeats,
                "n_by_status": m.n_by_status,
            }
            for m in run.judge_manifests
        ],
        "combined": {name: summarise_combined(recs) for name, recs in partitions.items()},
        "disagreements": disagreements,
        "dangerous_claims": [
            {"record_id": c.record_id, "question_id": c.question_id, **d.model_dump()}
            for c in combined
            for d in c.judge_flagged_dangerous_claims
        ],
        "oversight": oversight_metrics(
            run.judgements, run.scores, settings.canonical_prompt_version
        ),
        "_combined_records": combined,
    }


def _fmt(v: Any) -> str:
    if v is None:
        return "n/a"
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def render_judge_markdown(section: dict[str, Any]) -> list[str]:
    s = section["settings"]
    lines = [
        "## Automated LLM judges",
        "",
        *[f"> **{label}**  " for label in section["labels"]],
        "",
        "Judges are automated evaluators, not clinical experts. Their scores are stored "
        "separately from rule scores; the combined view below never overrides a rule score.",
        "",
        f"- Combination policy: `{s['policy']}` · min judges for consensus: {s['min_judges']} · "
        f"judge tolerance: {s['judge_tolerance']} · rule/judge disagreement threshold: "
        f"{s['rule_disagreement_threshold']} · canonical prompt: `{s['canonical_prompt_version']}`",
        "",
        "| Judge | Model | Revision | Backend | Evidence policy | Prompts | Repeats | Statuses |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for j in section["judges"]:
        lines.append(
            f"| {j['judge_id']} | `{j['model_name']}` | {j['model_revision'] or 'n/a'} | "
            f"{j['backend']} | {j['evidence_policy']} | {', '.join(j['prompt_versions'])} | "
            f"{j['repeats']} | {j['n_by_status']} |"
        )
    for part, title in (("primary", "primary"), ("non_primary", "non-primary (development only)")):
        cs = section["combined"][part]
        lines += ["", f"### Combined scores: {title}", ""]
        if cs["n_records"] == 0:
            lines += ["No records.", ""]
            continue
        lines += [
            "| Dimension | Combined mean | Items | From rule | From judge consensus | "
            "Needs review | Abstained | Rule/judge disagreements |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for dim in Dimension:
            d = cs["dimensions"][dim.value]
            src, st = d["combined_source"], d["combined_status"]
            lines.append(
                f"| {dim.value} | {_fmt(d['combined_case_level_mean'])} | {d['n_items_scored']} | "
                f"{src.get('rule', 0)} | {src.get('judge_consensus', 0)} | "
                f"{st.get('needs_review', 0)} | {st.get('abstained', 0)} | "
                f"{d['n_material_rule_judge_disagreements']} |"
            )
        agg = cs["combined_aggregate"]
        lines += [
            "",
            f"Combined aggregate: {agg['n_records']} · case-level mean of complete: "
            f"{_fmt(agg['case_level_mean_of_complete'])}",
        ]

    lines += ["", "### Disagreements", ""]
    if section["disagreements"]:
        lines += [
            "| Question | Dimension | Type | Rule | Judges | Combined |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for d in section["disagreements"]:
            lines.append(
                f"| {d['question_id']} | {d['dimension']} | {d['type']} | "
                f"{_fmt(d['rule_score'])} | {d['judge_scores']} | {d['combined_status']} |"
            )
    else:
        lines.append("None.")

    lines += ["", "### Judge-flagged potentially dangerous claims (for human review)", ""]
    if section["dangerous_claims"]:
        lines += ["| Question | Judge | Claim | Classification |", "| --- | --- | --- | --- |"]
        for c in section["dangerous_claims"]:
            text = c["text"].replace("|", "\\|")
            lines.append(
                f"| {c['question_id']} | {c['judge_id']} | {text} | {c['classification']} |"
            )
    else:
        lines.append("None.")

    o = section["oversight"]
    lines += ["", "### Scalable-oversight measurements", "", f"_{o['note']}_", ""]
    lines += [
        "| Judge | Statuses | Invalid/error rate | Mean retries | Validation issues | "
        "Mean latency (s) | Tokens (prompt/completion) | Est. cost | Claims | Dangerous |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for jid, pj in o["per_judge"].items():
        tok = pj["tokens"]
        cost = _fmt(pj["estimated_cost"]) if pj["estimated_cost"] is not None else "n/a"
        lines.append(
            f"| {jid} | {pj['by_status']} | {_fmt(pj['invalid_or_error_rate'])} | "
            f"{_fmt(pj['mean_retries'])} | {pj['n_validation_issues']} | "
            f"{_fmt(pj['latency_s']['mean'])} | {_fmt(tok['prompt'])}/{_fmt(tok['completion'])} | "
            f"{cost} | {pj['claims']['by_classification']} | "
            f"{pj['claims']['n_potentially_dangerous']} |"
        )
    lines += ["", "**Abstention rate by dimension (canonical judgements)**", ""]
    lines += ["| Judge | " + " | ".join(d.value for d in Dimension) + " |"]
    lines += ["| --- | " + " | ".join("---" for _ in Dimension) + " |"]
    for jid, pj in o["per_judge"].items():
        cells = [
            f"{_fmt(pj['abstention_by_dimension'][d.value]['abstained'])} "
            f"(n={pj['abstention_by_dimension'][d.value]['n_applicable']})"
            for d in Dimension
        ]
        lines.append(f"| {jid} | " + " | ".join(cells) + " |")
    lines += ["", "**Judge-vs-judge agreement (both scored)**", ""]
    if o["judge_vs_judge"]:
        lines += ["| Pair | " + " | ".join(d.value for d in Dimension) + " | Claim agreement |"]
        lines += ["| --- | " + " | ".join("---" for _ in Dimension) + " | --- |"]
        for pair, pv in o["judge_vs_judge"].items():
            cells = [
                f"{_fmt(pv['by_dimension'][d.value]['exact_agreement'])} "
                f"(n={pv['by_dimension'][d.value]['n']})"
                for d in Dimension
            ]
            cc = pv["claim_classification"]
            lines.append(
                f"| {pair} | " + " | ".join(cells) + f" | {_fmt(cc['classification_agreement'])} "
                f"(n={cc['n_aligned_claims']}) |"
            )
    else:
        lines.append("Fewer than two judges.")
    lines += ["", "**Rule-vs-judge agreement (both scored; exact agreement)**", ""]
    lines += ["| Judge | " + " | ".join(d.value for d in Dimension) + " |"]
    lines += ["| --- | " + " | ".join("---" for _ in Dimension) + " |"]
    for jid, per_dim in o["rule_vs_judge"].items():
        cells = [
            f"{_fmt(per_dim[d.value]['exact_agreement'])} (n={per_dim[d.value]['n']})"
            for d in Dimension
        ]
        lines.append(f"| {jid} | " + " | ".join(cells) + " |")
    lines += ["", "**Stability across repeats and prompt sensitivity**", ""]
    for jid in o["per_judge"]:
        st = o["stability_across_repeats"][jid]
        ps = o["prompt_sensitivity"][jid]
        variants = (
            "; ".join(
                f"{v}: exact {_fmt(x['exact_agreement'])} (n={x['n']}), "
                f"abstention flips {x['abstention_flips']}"
                for v, x in ps["variants"].items()
            )
            or ps["note"]
        )
        lines.append(
            f"- {jid}: identical across repeats {_fmt(st['identical_across_repeats'])} "
            f"(n={st['n_dimension_groups']}){' - ' + st['note'] if st['note'] else ''}; "
            f"prompt variants vs `{ps['canonical_prompt_version']}`: {variants}"
        )
    lines.append("")
    return lines
