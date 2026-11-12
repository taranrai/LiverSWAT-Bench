"""Cross-record validation: referential integrity against the evidence registry."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from liverswat_bench.datasets.schema import BenchmarkItem, VerificationStatus
from liverswat_bench.evidence.registry import EvidenceRegistry
from liverswat_bench.evidence.schema import SourceStatus
from liverswat_bench.io import ValidationIssue, read_jsonl_models


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)
    n_sources: int = 0
    n_passages: int = 0
    items_per_file: dict[Path, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.issues


def check_item_references(
    item: BenchmarkItem, registry: EvidenceRegistry, path: Path, line: int
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    def issue(msg: str) -> None:
        issues.append(ValidationIssue(path, line, f"{item.question_id}: {msg}"))

    for sid in item.source_ids:
        source = registry.sources.get(sid)
        if source is None:
            issue(f"unknown source_id {sid!r}")
            continue
        if source.synthetic != item.synthetic:
            kind = "synthetic" if source.synthetic else "real"
            issue(f"source {sid!r} is {kind} but item synthetic={item.synthetic}")
        if (
            item.verification_status == VerificationStatus.SOURCE_VERIFIED
            and source.source_status != SourceStatus.VERIFIED
        ):
            issue(
                f"item is source_verified but source {sid!r} has status "
                f"{source.source_status.value!r}"
            )

    for pid in item.evidence_passage_ids:
        passage = registry.passages.get(pid)
        if passage is None:
            issue(f"unknown evidence_passage_id {pid!r}")
            continue
        if passage.source_id not in item.source_ids:
            issue(
                f"passage {pid!r} belongs to source {passage.source_id!r}, "
                "which is not listed in source_ids"
            )
        if (
            item.verification_status == VerificationStatus.SOURCE_VERIFIED
            and passage.status != SourceStatus.VERIFIED
        ):
            issue(
                f"item is source_verified but passage {pid!r} has status {passage.status.value!r}"
            )
    return issues


def validate_dataset(
    item_files: Iterable[Path],
    source_files: Iterable[Path],
    passage_files: Iterable[Path],
) -> ValidationReport:
    registry, issues = EvidenceRegistry.load(source_files, passage_files)
    report = ValidationReport(
        issues=list(issues),
        n_sources=len(registry.sources),
        n_passages=len(registry.passages),
    )

    seen: dict[str, tuple[Path, int]] = {}
    for path in item_files:
        records, file_issues = read_jsonl_models(path, BenchmarkItem)
        report.issues.extend(file_issues)
        report.items_per_file[path] = len(records)
        for line_no, item in records:
            if item.question_id in seen:
                first_path, first_line = seen[item.question_id]
                report.issues.append(
                    ValidationIssue(
                        path,
                        line_no,
                        f"duplicate question_id {item.question_id!r} "
                        f"(first seen at {first_path}:{first_line})",
                    )
                )
            else:
                seen[item.question_id] = (path, line_no)
            report.issues.extend(check_item_references(item, registry, path, line_no))
    return report


def discover_files(data_dir: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """Find item, source and passage files under ``data_dir`` by filename suffix.

    Conventions: ``*items.jsonl``, ``*sources.jsonl``, ``*passages.jsonl``.
    The ``private`` directory (holdout data) is never included.
    """

    def find(suffix: str) -> list[Path]:
        return sorted(
            p
            for p in data_dir.rglob(f"*{suffix}")
            if "private" not in p.relative_to(data_dir).parts
        )

    return find("items.jsonl"), find("sources.jsonl"), find("passages.jsonl")
