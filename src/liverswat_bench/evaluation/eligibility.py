"""Which items may contribute to primary benchmark scores.

Re-checked at scoring time against the current evidence registry, because a
source can lose its verified status after responses were collected.
"""

from __future__ import annotations

from liverswat_bench.datasets.schema import (
    BenchmarkItem,
    EvidenceLevel,
    Track,
    VerificationStatus,
)
from liverswat_bench.evidence.registry import EvidenceRegistry
from liverswat_bench.evidence.schema import SourceStatus


def primary_eligibility(item: BenchmarkItem, registry: EvidenceRegistry) -> list[str]:
    """Return the reasons the item is NOT primary-eligible (empty list = eligible)."""
    reasons: list[str] = []
    if item.evidence_level != EvidenceLevel.A:
        reasons.append(f"evidence level {item.evidence_level.value} (requires A)")
    if item.verification_status != VerificationStatus.SOURCE_VERIFIED:
        reasons.append(f"verification status {item.verification_status.value}")
    if item.synthetic:
        reasons.append("synthetic item")
    if item.track != Track.PRIMARY:
        reasons.append(f"track {item.track.value}")
    if not item.evidence_passage_ids:
        reasons.append("no evidence passages")
    for sid in item.source_ids:
        source = registry.sources.get(sid)
        if source is None:
            reasons.append(f"source {sid} missing from registry")
        elif source.source_status != SourceStatus.VERIFIED:
            reasons.append(f"source {sid} is {source.source_status.value}")
    for pid in item.evidence_passage_ids:
        passage = registry.passages.get(pid)
        if passage is None:
            reasons.append(f"passage {pid} missing from registry")
        elif passage.status != SourceStatus.VERIFIED:
            reasons.append(f"passage {pid} is {passage.status.value}")
    return reasons
