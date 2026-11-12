"""Scalable-oversight measurements over judge outputs.

All metrics report their sample size (n). With n = 0 the value is None, never
0 or 1. These measure agreement between automated evaluators; agreement is
not evidence of clinical correctness.
"""

from __future__ import annotations

import itertools
import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from statistics import fmean, median
from typing import Any

from liverswat_bench.evaluation.dimensions import Dimension
from liverswat_bench.evaluation.rules import normalise
from liverswat_bench.evaluation.scoring_records import DimensionStatus, ScoreRecord
from liverswat_bench.judges.schema import JudgeRecord


def _rate(k: int, n: int) -> float | None:
    return round(k / n, 4) if n else None


def _pair_stats(pairs: list[tuple[int, int]]) -> dict[str, Any]:
    n = len(pairs)
    return {
        "n": n,
        "exact_agreement": _rate(sum(a == b for a, b in pairs), n),
        "within_one": _rate(sum(abs(a - b) <= 1 for a, b in pairs), n),
        "mean_abs_difference": round(fmean(abs(a - b) for a, b in pairs), 4) if n else None,
    }


def _dim_score(j: JudgeRecord, dim: Dimension) -> tuple[str, int | None]:
    if j.status != "ok":
        return "no_valid_output", None
    d = next(x for x in j.dimensions if x.dimension == dim)
    return d.status, d.score


def _claim_key(text: str) -> str:
    return re.sub(r"\s+", " ", normalise(text)).strip().casefold()


def _claim_consistency(groups: list[tuple[JudgeRecord, JudgeRecord]]) -> dict[str, Any]:
    """Align claims by normalised text between paired judgements on the same response."""
    aligned = agree = unmatched = 0
    for a, b in groups:
        ca = {_claim_key(c.text): c.classification for c in a.claims}
        cb = {_claim_key(c.text): c.classification for c in b.claims}
        shared = ca.keys() & cb.keys()
        aligned += len(shared)
        agree += sum(ca[k] == cb[k] for k in shared)
        unmatched += len(ca.keys() ^ cb.keys())
    return {
        "n_aligned_claims": aligned,
        "classification_agreement": _rate(agree, aligned),
        "n_unaligned_claims": unmatched,
        "note": "Claims are aligned only when their normalised text is identical.",
    }


def oversight_metrics(
    judgements: Sequence[JudgeRecord],
    scores: Sequence[ScoreRecord],
    canonical_prompt_version: str = "v1",
) -> dict[str, Any]:
    by_judge: dict[str, list[JudgeRecord]] = defaultdict(list)
    for j in judgements:
        by_judge[j.judge_id].append(j)
    canon = {
        (j.record_id, j.judge_id): j
        for j in judgements
        if j.prompt_version == canonical_prompt_version and j.repeat == 0
    }
    record_ids = sorted({j.record_id for j in judgements})
    judge_ids = sorted(by_judge)
    rule_by_record = {s.record_id: s for s in scores}

    per_judge: dict[str, Any] = {}
    for jid, js in by_judge.items():
        attempted = [j for j in js if j.status != "skipped_no_response"]
        latencies = [j.latency_s for j in attempted]
        canon_ok = [
            j
            for j in js
            if j.prompt_version == canonical_prompt_version and j.repeat == 0 and j.status == "ok"
        ]
        abstention = {}
        for dim in Dimension:
            statuses = Counter(_dim_score(j, dim)[0] for j in canon_ok)
            applicable = sum(v for k, v in statuses.items() if k != "not_applicable")
            abstention[dim.value] = {
                "n_applicable": applicable,
                "abstained": _rate(statuses.get("abstained", 0), applicable),
                "invalid": _rate(statuses.get("invalid", 0), applicable),
            }
        costs = [j.estimated_cost for j in attempted if j.estimated_cost is not None]
        per_judge[jid] = {
            "n_judgements": len(js),
            "by_status": dict(Counter(j.status for j in js)),
            "invalid_or_error_rate": _rate(
                sum(j.status in ("invalid_output", "error") for j in attempted), len(attempted)
            ),
            "mean_retries": round(fmean(len(j.attempts) - 1 for j in attempted), 4)
            if attempted
            else None,
            "n_validation_issues": sum(len(j.validation_issues) for j in js),
            "abstention_by_dimension": abstention,
            "latency_s": {
                "n": len(latencies),
                "mean": round(fmean(latencies), 6) if latencies else None,
                "median": round(median(latencies), 6) if latencies else None,
                "max": round(max(latencies), 6) if latencies else None,
            },
            "tokens": {
                "prompt": sum(j.prompt_tokens or 0 for j in attempted)
                if any(j.prompt_tokens is not None for j in attempted)
                else None,
                "completion": sum(j.completion_tokens or 0 for j in attempted)
                if any(j.completion_tokens is not None for j in attempted)
                else None,
            },
            "estimated_cost": round(sum(costs), 8) if costs else None,
            "cost_note": None if costs else "not available (no cost rates configured)",
            "claims": {
                "by_classification": dict(
                    Counter(c.classification.value for j in canon_ok for c in j.claims)
                ),
                "n_needs_review": sum(c.needs_review for j in canon_ok for c in j.claims),
                "n_potentially_dangerous": sum(
                    c.potentially_dangerous for j in canon_ok for c in j.claims
                ),
            },
        }

    # Judge-vs-judge agreement on canonical judgements.
    pairwise: dict[str, Any] = {}
    for a, b in itertools.combinations(judge_ids, 2):
        per_dim = {}
        abstain_agree = abstain_n = 0
        for dim in Dimension:
            pairs = []
            for rid in record_ids:
                ja, jb = canon.get((rid, a)), canon.get((rid, b))
                if not ja or not jb or ja.status != "ok" or jb.status != "ok":
                    continue
                (sa, va), (sb, vb) = _dim_score(ja, dim), _dim_score(jb, dim)
                if "not_applicable" in (sa, sb):
                    continue
                abstain_n += 1
                abstain_agree += (sa == "scored") == (sb == "scored")
                if va is not None and vb is not None:
                    pairs.append((va, vb))
            per_dim[dim.value] = _pair_stats(pairs)
        groups = [
            (canon[(rid, a)], canon[(rid, b)])
            for rid in record_ids
            if (rid, a) in canon and (rid, b) in canon
            and canon[(rid, a)].status == "ok" and canon[(rid, b)].status == "ok"
        ]  # fmt: skip
        pairwise[f"{a} vs {b}"] = {
            "by_dimension": per_dim,
            "scored_vs_abstained_agreement": _rate(abstain_agree, abstain_n),
            "n_dimension_judgements": abstain_n,
            "claim_classification": _claim_consistency(groups),
        }

    # Rule-vs-judge agreement (where both scored).
    rule_vs_judge: dict[str, Any] = {}
    for jid in judge_ids:
        per_dim = {}
        for dim in Dimension:
            pairs = []
            for rid in record_ids:
                j, s = canon.get((rid, jid)), rule_by_record.get(rid)
                if not j or not s or j.status != "ok":
                    continue
                rule = next(d for d in s.dimension_scores if d.dimension == dim)
                _, v = _dim_score(j, dim)
                if rule.status == DimensionStatus.SCORED and v is not None:
                    pairs.append((rule.score, v))
            stats = _pair_stats(pairs)
            stats["mean_judge_minus_rule"] = (
                round(fmean(b - a for a, b in pairs), 4) if pairs else None
            )
            per_dim[dim.value] = stats
        rule_vs_judge[jid] = per_dim

    # Stability across repeats and sensitivity to prompt wording, per judge.
    stability: dict[str, Any] = {}
    sensitivity: dict[str, Any] = {}
    for jid, js in by_judge.items():
        groups: dict[tuple[str, str], list[JudgeRecord]] = defaultdict(list)
        for j in js:
            groups[(j.record_id, j.prompt_version)].append(j)
        same = total = 0
        repeat_pairs = []
        for (_, _), rs in groups.items():
            rs = sorted(rs, key=lambda r: r.repeat)
            # Only groups where every repeat produced a valid judgement measure stability;
            # identical failures are not stable judgements.
            if len(rs) < 2 or any(r.status != "ok" for r in rs):
                continue
            repeat_pairs.extend(itertools.combinations(rs, 2))
            for dim in Dimension:
                total += 1
                same += len({_dim_score(r, dim) for r in rs}) == 1
        stability[jid] = {
            "n_dimension_groups": total,
            "identical_across_repeats": _rate(same, total),
            "claim_classification": _claim_consistency(
                [(a, b) for a, b in repeat_pairs if a.status == "ok" and b.status == "ok"]
            ),
            "note": None
            if total
            else "no prompt version with 2+ valid repeats (use --repeats; invalid outputs "
            "are excluded)",
        }
        versions = sorted({j.prompt_version for j in js} - {canonical_prompt_version})
        per_version = {}
        for v in versions:
            pairs, flips, n = [], 0, 0
            for rid in record_ids:
                base = canon.get((rid, jid))
                alt = next(
                    (
                        j
                        for j in js
                        if j.record_id == rid and j.prompt_version == v and j.repeat == 0
                    ),
                    None,
                )
                if not base or not alt or base.status != "ok" or alt.status != "ok":
                    continue
                for dim in Dimension:
                    (sa, va), (sb, vb) = _dim_score(base, dim), _dim_score(alt, dim)
                    if "not_applicable" in (sa, sb):
                        continue
                    n += 1
                    flips += (sa == "scored") != (sb == "scored")
                    if va is not None and vb is not None:
                        pairs.append((va, vb))
            per_version[v] = {**_pair_stats(pairs), "abstention_flips": flips, "n_compared": n}
        sensitivity[jid] = {
            "canonical_prompt_version": canonical_prompt_version,
            "variants": per_version,
            "note": None if versions else "no prompt variants run (use --prompt-variant)",
        }

    return {
        "note": "Agreement between automated evaluators measures consistency, not clinical "
        "correctness. No expert-labelled reference set exists yet.",
        "canonical_prompt_version": canonical_prompt_version,
        "per_judge": per_judge,
        "judge_vs_judge": pairwise,
        "rule_vs_judge": rule_vs_judge,
        "stability_across_repeats": stability,
        "prompt_sensitivity": sensitivity,
    }
