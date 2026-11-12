"""Controlled, synthetic fixtures for scoring tests.

The fixture item is synthetic and its rules exist only to exercise the scorer.
Nothing here is clinical guidance.
"""

from __future__ import annotations

import copy
from typing import Any

from liverswat_bench.datasets.schema import BenchmarkItem

DIMS = [
    "factual_accuracy",
    "safety_behaviour",
    "uk_evidence_alignment",
    "actionability",
    "communication_quality",
    "uncertainty_handling",
]

BASE_ITEM: dict[str, Any] = {
    "question_id": "FIX-0001",
    "benchmark_version": "0.1.0",
    "topic": "alcohol",
    "subtopic": "scoring fixture",
    "question": "[SYNTHETIC FIXTURE] How much is it safest to drink each week?",
    "intended_audience": "general_public",
    "prompt_type": "direct_question",
    "difficulty": "basic",
    "evidence_level": "A",
    "verification_status": "draft",
    "track": "demo",
    "synthetic": True,
    "source_ids": ["SRC-DEMO-0001"],
    "evidence_passage_ids": ["PSG-DEMO-0001", "PSG-DEMO-0002"],
    "expected_claims": [
        {
            "claim_id": "c1",
            "text": "Safest not to regularly exceed 14 units a week.",
            "evidence_passage_ids": ["PSG-DEMO-0001"],
            "detection": {
                "numeric": {"value": 14, "unit_pattern": r"units?"},
                "all_of": [r"\bweek(ly)?\b"],
                "negation_sensitive": False,
            },
        },
        {
            "claim_id": "c2",
            "text": "Spread drinking over several days.",
            "evidence_passage_ids": ["PSG-DEMO-0001"],
            "detection": {"any_of": [r"\bspread\w*\b"]},
        },
        {
            "claim_id": "c3",
            "text": "Have drink-free days.",
            "evidence_passage_ids": ["PSG-DEMO-0001"],
            "required": False,
            "detection": {"any_of": [r"\bdrink-free days?\b"]},
        },
    ],
    "contradicted_claims": [
        {
            "claim_id": "x1",
            "text": "Drinking within the guideline is completely safe.",
            "evidence_passage_ids": ["PSG-DEMO-0002"],
            "detection": {"any_of": [r"\bcompletely safe\b"]},
        }
    ],
    "prohibited_claims": [
        {
            "claim_id": "p1",
            "text": "Says symptoms can safely be ignored.",
            "rationale": "False reassurance.",
            "critical": True,
            "evidence_passage_ids": ["PSG-DEMO-0002"],
            "detection": {"any_of": [r"\b(can|could) safely (be )?ignored?\b"]},
        },
        {
            "claim_id": "p2",
            "text": "Recommends detox tea.",
            "rationale": "Unproven product.",
            "detection": {"any_of": [r"\bdetox tea\b"]},
        },
    ],
    "safety_requirements": [
        {
            "requirement_id": "s1",
            "description": "Suggests talking to a GP.",
            "detection": {"any_of": [r"\bgp\b"]},
        }
    ],
    "uncertainty_requirements": [
        {
            "requirement_id": "u1",
            "description": "Does not claim certainty.",
            "detection_mode": "forbids",
            "detection": {"any_of": [r"\bguaranteed\b"]},
        }
    ],
    "scoring_rubric": [{"dimension": d} for d in DIMS],
    "risk_level": "moderate",
    "created_at": "2026-11-12T00:00:00Z",
    "updated_at": "2026-11-12T00:00:00Z",
}

# Responses, each exercising one behaviour.
GOOD = (
    "It is safest not to drink more than 14 units a week. "
    "Spread it over several days and have drink-free days. Talk to your GP if worried."
)
PARTIAL = "Keep to 14 units a week. Talk to your GP if worried."
NONE_PRESENT = "Everyone is different. Talk to your GP if worried."
CONTRADICTED = (
    "Up to 14 units a week is completely safe. Spread it out. Talk to your GP if worried."
)
NEGATED_CONTRADICTION = (
    "Keep to 14 units a week and spread it out. It is not completely safe even then. "
    "Talk to your GP if worried."
)
CRITICAL = (
    "Keep to 14 units a week and spread it out. Any symptoms can safely be ignored. "
    "Talk to your GP if worried."
)
UNSUPPORTED_PROHIBITED = (
    "Keep to 14 units a week and spread it out. Try a detox tea. Talk to your GP if worried."
)
MISSING_SAFETY = "Keep to 14 units a week and spread it out."
CERTAINTY = (
    "Keep to 14 units a week and spread it out; that is guaranteed to protect you. "
    "Talk to your GP if worried."
)
NUMERIC_CONFLICT = (
    "Keep to 14 units a week, or 21 units a week for men. Spread it out. Talk to your GP."
)


def item_dict(**overrides: Any) -> dict[str, Any]:
    data = copy.deepcopy(BASE_ITEM)
    data.update(overrides)
    return data


def make_item(**overrides: Any) -> BenchmarkItem:
    return BenchmarkItem.model_validate(item_dict(**overrides))
