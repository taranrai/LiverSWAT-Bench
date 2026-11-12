"""Machine-readable dataset metadata for a future Hugging Face release.

The metadata is generated from the data files, so it cannot drift from them.
It contains no timestamps, so the committed copy can be checked by a test.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from liverswat_bench import BENCHMARK_VERSION
from liverswat_bench.datasets.schema import BenchmarkItem
from liverswat_bench.datasets.validation import discover_files
from liverswat_bench.evaluation.eligibility import primary_eligibility
from liverswat_bench.evidence.registry import EvidenceRegistry
from liverswat_bench.io import read_jsonl_models

RELEASE_GATE = (
    "Do not publish to Hugging Face until (1) the public split contains source_verified items "
    "with a confirmed human review, (2) every stored extract has a licence that permits "
    "redistribution with the required attribution, and (3) the maintainer approves the release."
)


def build_metadata(data_dir: Path) -> dict[str, Any]:
    item_files, source_files, passage_files = discover_files(data_dir)
    registry, _ = EvidenceRegistry.load(source_files, passage_files)
    files = {}
    eligible = 0
    for path in item_files:
        items = [i for _, i in read_jsonl_models(path, BenchmarkItem)[0]]
        eligible += sum(not primary_eligibility(i, registry) for i in items)
        files[str(path.relative_to(data_dir.parent))] = {
            "n_items": len(items),
            "by_track": dict(sorted(Counter(i.track.value for i in items).items())),
            "by_verification_status": dict(
                sorted(Counter(i.verification_status.value for i in items).items())
            ),
            "by_topic": dict(sorted(Counter(i.topic.value for i in items).items())),
            "synthetic": sum(i.synthetic for i in items),
        }
    real_sources = [s for s in registry.sources.values() if not s.synthetic]
    return {
        "dataset": "LiverSWAT-Bench",
        "benchmark_version": BENCHMARK_VERSION,
        "release_status": "not released",
        "release_gate": RELEASE_GATE,
        "clinical_validation": "not clinically validated",
        "code_licence": "MIT",
        "primary_eligible_items": eligible,
        "item_files": files,
        "sources": [
            {
                "source_id": s.source_id,
                "organisation": s.organisation.value,
                "title": s.title,
                "url": str(s.url) if s.url else None,
                "status": s.source_status.value,
                "licence": s.licence,
                "attribution": s.attribution,
                "n_passages": sum(p.source_id == s.source_id for p in registry.passages.values()),
            }
            for s in sorted(real_sources, key=lambda s: s.source_id)
        ],
        "passages_by_status": dict(
            sorted(
                Counter(
                    p.status.value for p in registry.passages.values() if not p.synthetic
                ).items()
            )
        ),
    }


def render(data_dir: Path) -> str:
    return json.dumps(build_metadata(data_dir), indent=2) + "\n"
