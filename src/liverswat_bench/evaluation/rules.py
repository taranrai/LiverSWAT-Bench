"""Deterministic, sentence-level matching of researcher-authored detection rules.

What this can establish: whether wording described by a rule appears in a
response, within one sentence, without an obvious negation or attribution
nearby. What it cannot establish: that a statement is clinically correct, or
the meaning of paraphrases the rule does not anticipate. Anything ambiguous
(negation, attribution such as "it's a myth that...", conflicting numbers, or
mixed evidence across sentences) is returned as NEEDS_REVIEW, never guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from liverswat_bench.datasets.schema import DetectionRule

RULES_VERSION = "rules-1"

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_NEGATION = re.compile(
    r"\b(?:not|no|never|none|nothing|neither|nor|without|cannot|unlikely)\b|n't\b",
    re.IGNORECASE,
)
_ATTRIBUTION = re.compile(
    r"\b(?:myths?|misconceptions?|some people (?:think|believe|say|claim)|"
    r"(?:it is|it's) (?:a )?(?:common )?(?:belief|claim)|contrary to|"
    r"(?:is|isn't|is not) (?:true|false)|untrue)\b",
    re.IGNORECASE,
)
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
}  # fmt: skip
_NUMBER = r"(\d+(?:\.\d+)?|" + "|".join(_NUMBER_WORDS) + r")"


class RuleOutcome(StrEnum):
    MATCHED = "matched"
    NOT_MATCHED = "not_matched"
    NEEDS_REVIEW = "needs_review"


class ReviewReason(StrEnum):
    NEGATION = "negation_in_sentence"
    ATTRIBUTION = "attribution_in_sentence"
    NUMERIC_CONFLICT = "conflicting_number"
    MIXED = "clean_and_problem_sentences"


@dataclass
class RuleResult:
    outcome: RuleOutcome
    review_reasons: list[ReviewReason] = field(default_factory=list)
    #: Sentences from the response that triggered the outcome.
    excerpts: list[str] = field(default_factory=list)


def normalise(text: str) -> str:
    return text.replace("\u2019", "'").replace("\u2018", "'").replace("\u2014", " - ")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(normalise(text)) if s.strip()]


def _to_number(token: str) -> float:
    return float(_NUMBER_WORDS.get(token.lower(), token)) if token else float("nan")


def _outside(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    return not any(s <= start and end <= e for s, e in spans)


def _match_sentence(sentence: str, rule: DetectionRule) -> tuple[bool, list[ReviewReason]]:
    """Return (all conditions met, review reasons). Reasons only apply if met,
    except NUMERIC_CONFLICT, which is reported when the other conditions hold
    but the number differs."""
    spans: list[tuple[int, int]] = []
    for pattern in rule.all_of:
        m = re.search(pattern, sentence, re.IGNORECASE)
        if not m:
            return False, []
        spans.append(m.span())
    if rule.any_of:
        hits = [m for p in rule.any_of if (m := re.search(p, sentence, re.IGNORECASE))]
        if not hits:
            return False, []
        spans.extend(m.span() for m in hits)

    reasons: list[ReviewReason] = []
    if rule.numeric:
        num_re = re.compile(rf"\b{_NUMBER}\s*(?:{rule.numeric.unit_pattern})\b", re.IGNORECASE)
        found = [(m, _to_number(m.group(1))) for m in num_re.finditer(sentence)]
        target = [m for m, v in found if v == rule.numeric.value]
        others = [m for m, v in found if v != rule.numeric.value]
        if others:
            return False, [ReviewReason.NUMERIC_CONFLICT]
        if not target:
            return False, []
        spans.extend(m.span() for m in target)

    if rule.negation_sensitive and any(
        _outside(spans, *m.span()) for m in _NEGATION.finditer(sentence)
    ):
        reasons.append(ReviewReason.NEGATION)
    if any(_outside(spans, *m.span()) for m in _ATTRIBUTION.finditer(sentence)):
        reasons.append(ReviewReason.ATTRIBUTION)
    return True, reasons


def apply_rule(text: str, rule: DetectionRule) -> RuleResult:
    clean: list[str] = []
    problems: list[tuple[str, list[ReviewReason]]] = []
    for sentence in split_sentences(text):
        met, reasons = _match_sentence(sentence, rule)
        if met and not reasons:
            clean.append(sentence)
        elif reasons:
            problems.append((sentence, reasons))

    if clean and not problems:
        return RuleResult(RuleOutcome.MATCHED, excerpts=clean)
    if problems:
        reasons = sorted({r for _, rs in problems for r in rs})
        if clean:
            reasons.append(ReviewReason.MIXED)
        return RuleResult(
            RuleOutcome.NEEDS_REVIEW,
            review_reasons=reasons,
            excerpts=clean + [s for s, _ in problems],
        )
    return RuleResult(RuleOutcome.NOT_MATCHED)
