"""Loading and indexing of the evidence registry."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from liverswat_bench.evidence.schema import EvidencePassage, Source, SourceStatus
from liverswat_bench.evidence.verification import (
    LOG_FILENAME,
    VerificationError,
    human_confirmed,
    read_log,
)
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
        """Load sources and passages, reporting schema and integrity problems.

        A ``verified`` source or passage must have a confirmed human review in the
        ``verification_log.jsonl`` file next to its registry file.
        """
        registry = cls()
        issues: list[ValidationIssue] = []
        source_files, passage_files = list(source_files), list(passage_files)

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

        issues.extend(_check_human_review(registry, source_files, passage_files))
        return registry, issues


def _check_human_review(
    registry: EvidenceRegistry, source_files: list[Path], passage_files: list[Path]
) -> list[ValidationIssue]:
    log_paths = sorted({p.parent / LOG_FILENAME for p in [*source_files, *passage_files]})
    entries = []
    issues: list[ValidationIssue] = []
    for log in log_paths:
        try:
            entries.extend(read_log(log))
        except VerificationError as exc:
            issues.append(ValidationIssue(log, None, str(exc)))
    confirmed_sources, confirmed_passages = human_confirmed(entries)
    where = log_paths[0] if log_paths else Path(LOG_FILENAME)
    for sid, source in registry.sources.items():
        if source.source_status == SourceStatus.VERIFIED and sid not in confirmed_sources:
            issues.append(
                ValidationIssue(
                    where,
                    None,
                    f"source {sid!r} is verified but has no confirmed human review in "
                    f"{LOG_FILENAME}",
                )
            )
    for pid, passage in registry.passages.items():
        if passage.status == SourceStatus.VERIFIED and pid not in confirmed_passages:
            issues.append(
                ValidationIssue(
                    where,
                    None,
                    f"passage {pid!r} is verified but has no confirmed human review in "
                    f"{LOG_FILENAME}",
                )
            )
    return issues
