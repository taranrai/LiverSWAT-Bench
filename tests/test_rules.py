from __future__ import annotations

import pytest
from pydantic import ValidationError

from liverswat_bench.datasets.schema import DetectionRule
from liverswat_bench.evaluation.rules import (
    ReviewReason,
    RuleOutcome,
    apply_rule,
    split_sentences,
)


def rule(**kw) -> DetectionRule:
    return DetectionRule.model_validate(kw)


def test_simple_match_returns_sentence_excerpt():
    r = apply_rule("Hello. Please see your GP today.", rule(any_of=[r"\bgp\b"]))
    assert r.outcome == RuleOutcome.MATCHED
    assert r.excerpts == ["Please see your GP today."]


def test_no_match():
    assert apply_rule("Nothing relevant.", rule(any_of=[r"\bgp\b"])).outcome == (
        RuleOutcome.NOT_MATCHED
    )


def test_negation_elsewhere_in_sentence_needs_review():
    r = apply_rule("It is not completely safe.", rule(any_of=[r"\bcompletely safe\b"]))
    assert r.outcome == RuleOutcome.NEEDS_REVIEW
    assert ReviewReason.NEGATION in r.review_reasons


def test_negation_inside_the_matched_wording_is_ignored():
    r = apply_rule(
        "You definitely don't have liver disease.",
        rule(any_of=[r"\bdefinitely (do not|don't) have liver disease\b"]),
    )
    assert r.outcome == RuleOutcome.MATCHED


def test_curly_apostrophes_are_normalised():
    r = apply_rule(
        "You definitely don\u2019t have liver disease.",
        rule(any_of=[r"\bdefinitely don't have liver disease\b"]),
    )
    assert r.outcome == RuleOutcome.MATCHED


def test_negation_insensitive_rule_matches_negated_wording():
    r = apply_rule(
        "A normal result does not rule out disease.",
        rule(any_of=[r"\brule out\b"], negation_sensitive=False),
    )
    assert r.outcome == RuleOutcome.MATCHED


def test_attribution_needs_review_even_when_negation_insensitive():
    r = apply_rule(
        "It's a myth that detox tea repairs the liver.",
        rule(any_of=[r"\bdetox tea\b"], negation_sensitive=False),
    )
    assert r.outcome == RuleOutcome.NEEDS_REVIEW
    assert ReviewReason.ATTRIBUTION in r.review_reasons


@pytest.mark.parametrize(
    "text", ["Drink no more than 14 units a week.", "Fourteen units per week is the limit."]
)
def test_numeric_match_digits_and_words(text):
    r = apply_rule(
        text,
        rule(numeric={"value": 14, "unit_pattern": r"units?"}, all_of=[r"\bweek\b"],
             negation_sensitive=False),
    )  # fmt: skip
    assert r.outcome == RuleOutcome.MATCHED


def test_numeric_conflict_needs_review():
    r = apply_rule(
        "Women 14 units a week, men 21 units a week.",
        rule(numeric={"value": 14, "unit_pattern": r"units?"}, all_of=[r"\bweek\b"]),
    )
    assert r.outcome == RuleOutcome.NEEDS_REVIEW
    assert ReviewReason.NUMERIC_CONFLICT in r.review_reasons


def test_wrong_number_alone_is_review_not_absent():
    r = apply_rule(
        "The limit is 21 units a week.",
        rule(numeric={"value": 14, "unit_pattern": r"units?"}, all_of=[r"\bweek\b"]),
    )
    assert r.outcome == RuleOutcome.NEEDS_REVIEW


def test_number_with_other_unit_is_ignored():
    r = apply_rule(
        "Take 14 days off each week.",
        rule(numeric={"value": 14, "unit_pattern": r"units?"}, all_of=[r"\bweek\b"]),
    )
    assert r.outcome == RuleOutcome.NOT_MATCHED


def test_conditions_must_hold_in_the_same_sentence():
    r = apply_rule("Drink 14 units. Every week.", rule(
        numeric={"value": 14, "unit_pattern": r"units?"}, all_of=[r"\bweek\b"]))  # fmt: skip
    assert r.outcome == RuleOutcome.NOT_MATCHED


def test_clean_and_problem_sentences_need_review():
    r = apply_rule(
        "This is completely safe. Actually it is not completely safe.",
        rule(any_of=[r"\bcompletely safe\b"]),
    )
    assert r.outcome == RuleOutcome.NEEDS_REVIEW
    assert ReviewReason.MIXED in r.review_reasons


def test_sentence_splitting_handles_newlines_and_labels():
    assert split_sentences("[LABEL - NOT A MODEL]\nYes, you have it. Next!") == [
        "[LABEL - NOT A MODEL]",
        "Yes, you have it.",
        "Next!",
    ]


def test_rule_validation():
    with pytest.raises(ValidationError, match="needs all_of, any_of or numeric"):
        DetectionRule.model_validate({})
    with pytest.raises(ValidationError, match="invalid regular expression"):
        DetectionRule.model_validate({"any_of": ["(unclosed"]})
