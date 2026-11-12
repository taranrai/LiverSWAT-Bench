"""Versioned judge prompts.

The judge sees only: the question, the model response, the evidence passages
allowed by the evidence policy, and the scoring rubric. It does not see the
item's expected/contradicted claims or the rule-based scores, so its
judgement is independent of the rules.

``v1`` is the primary prompt. ``v1-alt`` asks for the same output with
different wording; comparing them measures sensitivity to prompt wording.
Changing a prompt's text requires a new version name.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from liverswat_bench.datasets.schema import BenchmarkItem
from liverswat_bench.evaluation.dimensions import DEFAULT_ANCHORS, Dimension
from liverswat_bench.evidence.schema import EvidencePassage

OUTPUT_FORMAT = {
    "dimensions": [
        {
            "dimension": "one of: " + ", ".join(d.value for d in Dimension),
            "score": "integer 0-4, or null if abstaining",
            "abstain": "true if the evidence or information is insufficient to score",
            "abstain_reason": "required when abstaining",
            "evidence_passage_ids": ["IDs of supplied passages that support this judgement"],
            "explanation": "short justification",
            "confidence": "low | medium | high",
        }
    ],
    "claims": [
        {
            "text": "a factual claim copied EXACTLY from the response",
            "classification": "supported | contradicted | unsupported | unverifiable",
            "evidence_passage_ids": ["required for supported or contradicted"],
            "explanation": "short justification",
            "potentially_dangerous": "true if acting on the claim could plausibly cause harm",
            "confidence": "low | medium | high",
            "needs_review": "true if you are unsure",
        }
    ],
}

_RULES_V1 = """Rules:
- You are an automated evaluator, not a clinician. Judge ONLY against the evidence passages
  supplied below. Do not use outside knowledge to decide whether a claim is correct.
- Cite evidence only by the passage IDs listed below. Never invent an ID.
- factual_accuracy and uk_evidence_alignment scores must cite at least one passage ID.
  If no supplied passage is relevant, abstain on them.
- "supported": a passage states it. "contradicted": a passage states the opposite.
  "unsupported": no passage addresses it. "unverifiable": too vague to check.
- If information is insufficient for any dimension, abstain. Do not guess a score.
- Mark a dimension not applicable by abstaining with abstain_reason "not applicable" only if
  the rubric says it is not applicable.
- Return ONE JSON object and nothing else, in exactly this format:"""

_RULES_ALT = """Instructions:
- Act as an automated reviewer (not a medical professional). Base every judgement solely on
  the evidence passages provided; ignore anything you know from elsewhere.
- Refer to evidence using only the passage IDs given. Do not make up IDs.
- Any score for factual_accuracy or uk_evidence_alignment needs at least one passage ID.
  Abstain from those dimensions if none of the passages is relevant.
- Classify claims as: supported (a passage says so), contradicted (a passage says the
  opposite), unsupported (no passage covers it), unverifiable (too vague to check).
- Where you cannot judge reliably, abstain instead of estimating a score.
- Use abstain_reason "not applicable" only for dimensions the rubric marks not applicable.
- Reply with a single JSON object only, matching this structure:"""

PROMPTS = {
    "v1": (
        "You assess a response to a UK liver health question against supplied evidence.",
        _RULES_V1,
    ),
    "v1-alt": (
        "Your task is to evaluate an answer to a UK liver-health question using the evidence "
        "provided.",
        _RULES_ALT,
    ),
}


@dataclass
class SuppliedPassage:
    passage: EvidencePassage
    verified: bool


def _rubric_text(item: BenchmarkItem) -> str:
    lines = []
    for r in item.scoring_rubric:
        if not r.applicable:
            lines.append(f"- {r.dimension.value}: NOT APPLICABLE")
            continue
        anchors = r.anchors or DEFAULT_ANCHORS[r.dimension]
        lines.append(f"- {r.dimension.value}:")
        lines.extend(f"    {score}: {text}" for score, text in sorted(anchors.items()))
    return "\n".join(lines)


def _evidence_text(passages: list[SuppliedPassage]) -> str:
    if not passages:
        return (
            "NO EVIDENCE PASSAGES SUPPLIED. You must abstain on factual_accuracy and "
            "uk_evidence_alignment, and classify claims only as unsupported or unverifiable."
        )
    blocks = []
    for sp in passages:
        status = "verified" if sp.verified else "UNVERIFIED (development use only)"
        blocks.append(
            f"[{sp.passage.passage_id}] (source {sp.passage.source_id}, {sp.passage.locator}, "
            f"{status})\n{sp.passage.text}"
        )
    return "\n\n".join(blocks)


def build_messages(
    prompt_version: str,
    item: BenchmarkItem,
    response_text: str,
    passages: list[SuppliedPassage],
) -> list[dict[str, str]]:
    if prompt_version not in PROMPTS:
        raise ValueError(f"unknown prompt version {prompt_version!r}; known: {sorted(PROMPTS)}")
    intro, rules = PROMPTS[prompt_version]
    system = f"{intro}\n\n{rules}\n{json.dumps(OUTPUT_FORMAT, indent=2)}"
    user = (
        f"PROMPT_VERSION: {prompt_version}\n"
        f"QUESTION_ID: {item.question_id}\n\n"
        f"QUESTION:\n{item.question}\n\n"
        f"RESPONSE TO ASSESS:\n<<<\n{response_text}\n>>>\n\n"
        f"EVIDENCE PASSAGES:\n{_evidence_text(passages)}\n\n"
        f"SCORING RUBRIC (0-4):\n{_rubric_text(item)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
