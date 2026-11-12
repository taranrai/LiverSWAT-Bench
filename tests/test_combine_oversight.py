"""Combination policy (rules + judges) and oversight metrics."""

from __future__ import annotations

import pytest

from liverswat_bench.evaluation.combine import (
    CombinePolicy,
    CombineSettings,
    combine,
)
from liverswat_bench.evaluation.scoring import SILENCE_REASON
from liverswat_bench.judges.oversight import oversight_metrics
from tests import judge_fixtures as jf

RID = "exp:DEMO-0001:0"
JUDGEMENT = ("abstained", None, "requires judgement of next steps (LLM judges)")
NEEDS_REVIEW = ("abstained", None, "a check needs review")


def combined_dim(score, judges, dimension, settings=None):
    rec = combine([score], judges, settings)[0]
    return next(d for d in rec.dimensions if d.dimension == dimension), rec


def test_rule_score_kept_when_judges_agree():
    score = jf.score_record(RID, {"factual_accuracy": ("scored", 3, "x")})
    js = [jf.judge_record(RID, "a", {"factual_accuracy": 3}),
          jf.judge_record(RID, "b", {"factual_accuracy": 4})]  # fmt: skip
    d, _ = combined_dim(score, js, "factual_accuracy")
    assert (d.combined_status, d.combined_score, d.combined_source) == ("scored", 3, "rule")
    assert d.consensus == "consensus" and d.consensus_score == 3  # lower median
    assert d.rule_score == 3


def test_material_disagreement_goes_to_review_by_default():
    score = jf.score_record(RID, {"factual_accuracy": ("scored", 3, "x")})
    js = [jf.judge_record(RID, "a", {"factual_accuracy": 1}),
          jf.judge_record(RID, "b", {"factual_accuracy": 1})]  # fmt: skip
    d, _ = combined_dim(score, js, "factual_accuracy")
    assert d.material_disagreement and d.rule_judge_difference == -2
    assert (d.combined_status, d.combined_score) == ("needs_review", None)
    assert d.rule_score == 3  # rule result preserved, not overridden


def test_rules_first_policy_keeps_rule_and_flags():
    score = jf.score_record(RID, {"factual_accuracy": ("scored", 3, "x")})
    js = [jf.judge_record(RID, "a", {"factual_accuracy": 1}),
          jf.judge_record(RID, "b", {"factual_accuracy": 1})]  # fmt: skip
    settings = CombineSettings(policy=CombinePolicy.RULES_FIRST)
    d, _ = combined_dim(score, js, "factual_accuracy", settings)
    assert (d.combined_status, d.combined_score, d.combined_source) == ("scored", 3, "rule")
    assert d.material_disagreement


@pytest.mark.parametrize(
    "reason",
    [
        "requires judgement of next steps (LLM judges)",
        "a check has no detection rule",
        "item defines no safety checks",
        SILENCE_REASON,
    ],
)
def test_fillable_abstentions_take_judge_consensus(reason):
    score = jf.score_record(RID, {"actionability": ("abstained", None, reason)})
    js = [jf.judge_record(RID, "a", {"actionability": 2}),
          jf.judge_record(RID, "b", {"actionability": 3})]  # fmt: skip
    d, _ = combined_dim(score, js, "actionability")
    assert (d.combined_status, d.combined_score, d.combined_source) == (
        "scored", 2, "judge_consensus")  # fmt: skip


def test_needs_review_abstention_is_not_filled():
    score = jf.score_record(RID, {"safety_behaviour": NEEDS_REVIEW})
    js = [jf.judge_record(RID, "a", {"safety_behaviour": 3}),
          jf.judge_record(RID, "b", {"safety_behaviour": 3})]  # fmt: skip
    d, _ = combined_dim(score, js, "safety_behaviour")
    assert (d.combined_status, d.combined_score) == ("abstained", None)


def test_missing_and_not_applicable_are_never_filled():
    score = jf.score_record(
        RID,
        {
            "factual_accuracy": ("missing", None, "no response"),
            "uk_evidence_alignment": ("not_applicable", None, "rubric"),
        },
    )
    js = [jf.judge_record(RID, "a", {}), jf.judge_record(RID, "b", {})]
    rec = combine([score], js)[0]
    by = {d.dimension: d for d in rec.dimensions}
    assert by["factual_accuracy"].combined_status == "missing"
    assert by["uk_evidence_alignment"].combined_status == "not_applicable"


def test_conflicting_judges_send_fillable_dimension_to_review():
    score = jf.score_record(RID, {"actionability": JUDGEMENT})
    js = [jf.judge_record(RID, "a", {"actionability": 4}),
          jf.judge_record(RID, "b", {"actionability": 1})]  # fmt: skip
    d, _ = combined_dim(score, js, "actionability")
    assert d.consensus == "judges_disagree"
    assert (d.combined_status, d.combined_source) == ("needs_review", "judge_disagreement")


def test_single_judge_is_insufficient():
    score = jf.score_record(RID, {"actionability": JUDGEMENT})
    js = [jf.judge_record(RID, "a", {"actionability": 3}),
          jf.judge_record(RID, "b", {"actionability": None})]  # fmt: skip
    d, _ = combined_dim(score, js, "actionability")
    assert d.consensus == "insufficient_judges" and d.combined_status == "abstained"


def test_invalid_judge_output_does_not_count():
    score = jf.score_record(RID, {"actionability": JUDGEMENT})
    js = [jf.judge_record(RID, "a", {"actionability": 3}),
          jf.judge_record(RID, "b", {}, status="invalid_output")]  # fmt: skip
    d, rec = combined_dim(score, js, "actionability")
    assert d.judge_statuses["b"] == "no_valid_output"
    assert d.combined_status == "abstained"
    assert rec.judges_without_valid_output == ["b"]


def test_only_canonical_judgements_are_combined():
    score = jf.score_record(RID, {"actionability": JUDGEMENT})
    js = [
        jf.judge_record(RID, "a", {"actionability": 3}),
        jf.judge_record(RID, "b", {"actionability": 3}),
        jf.judge_record(RID, "a", {"actionability": 0}, prompt_version="v1-alt"),
        jf.judge_record(RID, "b", {"actionability": 0}, repeat=1),
    ]
    d, _ = combined_dim(score, js, "actionability")
    assert d.combined_score == 3


def test_combined_aggregate_and_dangerous_claims_are_separate():
    score = jf.score_record(RID, {})  # all rule dimensions scored 2
    danger = {
        "claim_index": 0, "text": "x", "text_found_in_response": True,
        "classification": "unsupported", "evidence_passage_ids": [], "explanation": "t",
        "potentially_dangerous": True, "confidence": "high", "needs_review": False,
    }  # fmt: skip
    js = [jf.judge_record(RID, "a", {}, claims=[danger]), jf.judge_record(RID, "b", {})]
    rec = combine([score], js)[0]
    assert rec.combined_aggregate.status == "complete"
    assert rec.combined_aggregate.score == pytest.approx(2.0)
    assert [c.text for c in rec.judge_flagged_dangerous_claims] == ["x"]


# ------------------------------------------------------------------ oversight


def test_oversight_agreement_abstention_and_stability():
    r1, r2 = "exp:DEMO-0001:0", "exp:DEMO-0002:0"
    scores = [jf.score_record(r1, {}), jf.score_record(r2, {})]
    js = [
        jf.judge_record(r1, "a", {"actionability": 3}),
        jf.judge_record(r1, "b", {"actionability": 3}),
        jf.judge_record(r2, "a", {"actionability": 1}),
        jf.judge_record(r2, "b", {"actionability": None}),
        jf.judge_record(r1, "a", {"actionability": 3}, repeat=1),
        jf.judge_record(r2, "a", {"actionability": 2}, repeat=1),
        jf.judge_record(r1, "a", {"actionability": 1}, prompt_version="v1-alt"),
        jf.judge_record(r1, "c", {}, status="invalid_output"),
        jf.judge_record(r1, "c", {}, status="invalid_output", repeat=1),
    ]
    o = oversight_metrics(js, scores)
    ab = o["judge_vs_judge"]["a vs b"]["by_dimension"]["actionability"]
    assert ab == {"n": 1, "exact_agreement": 1.0, "within_one": 1.0, "mean_abs_difference": 0.0}
    assert o["per_judge"]["b"]["abstention_by_dimension"]["actionability"]["abstained"] == 0.5
    assert o["per_judge"]["c"]["invalid_or_error_rate"] == 1.0
    assert o["stability_across_repeats"]["a"]["n_dimension_groups"] == 12
    assert o["stability_across_repeats"]["a"]["identical_across_repeats"] == pytest.approx(
        11 / 12, abs=1e-4
    )
    assert o["stability_across_repeats"]["c"]["n_dimension_groups"] == 0
    assert o["stability_across_repeats"]["c"]["identical_across_repeats"] is None
    sens = o["prompt_sensitivity"]["a"]["variants"]["v1-alt"]
    assert sens["exact_agreement"] == pytest.approx(5 / 6, abs=1e-4)
    rvj = o["rule_vs_judge"]["a"]["actionability"]
    assert rvj["n"] == 2 and rvj["mean_judge_minus_rule"] == pytest.approx(0.0)


def test_oversight_with_no_data_reports_none():
    o = oversight_metrics([jf.judge_record("exp:DEMO-0001:0", "a", {}, status="error")], [])
    assert o["per_judge"]["a"]["abstention_by_dimension"]["actionability"]["abstained"] is None
    assert o["judge_vs_judge"] == {}
    assert o["per_judge"]["a"]["estimated_cost"] is None
