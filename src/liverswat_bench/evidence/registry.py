"""Loading and indexing of the evidence registry."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from liverswat_bench.evidence.schema import EvidencePassage, Source
from liverswat_bench.io import ValidationIssue, read_jsonl_models


@dataclass
class EvidenceRegistry:
    sources: dict[str, Source] = field(default_factory=dict)
    passages: dict[str, EvidencePassage] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        source_files: Iterable[Path],
        passage_files: Iterable[Path],
    ) -> tuple[EvidenceRegistry, list[ValidationIssue]]:
        """Load sources and passages, reporting schema and integrity problems."""
        registry = cls()
        issues: list[ValidationIssue] = []

        for path in source_files:
            records, file_issues = read_jsonl_models(path, Source)
            issues.extend(file_issues)
            for line_no, source in records:
                if source.source_id in registry.sources:
                    issues.append(
                        ValidationIssue(path, line_no, f"duplicate source_id {source.source_id!r}")
                    )
                    continue
                registry.sources[source.source_id] = source

        for path in passage_files:
            records, file_issues = read_jsonl_models(path, EvidencePassage)
            issues.extend(file_issues)
            for line_no, passage in records:
                if passage.passage_id in registry.passages:
                    issues.append(
                        ValidationIssue(
                            path, line_no, f"duplicate passage_id {passage.passage_id!r}"
                        )
                    )
                    continue
                source = registry.sources.get(passage.source_id)
                if source is None:
                    issues.append(
                        ValidationIssue(
                            path,
                            line_no,
                            f"passage {passage.passage_id!r} references unknown "
                            f"source_id {passage.source_id!r}",
                        )
                    )
                elif source.synthetic != passage.synthetic:
                    issues.append(
                        ValidationIssue(
                            path,
                            line_no,
                            f"passage {passage.passage_id!r} synthetic flag does not "
                            f"match its source {source.source_id!r}",
                        )
                    )
                registry.passages[passage.passage_id] = passage

        return registry, issues
