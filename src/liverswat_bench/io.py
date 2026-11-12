"""Shared JSONL reading utilities with line-level error reporting."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass(frozen=True)
class ValidationIssue:
    path: Path
    line: int | None
    message: str

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line is not None else str(self.path)
        return f"{where}: {self.message}"


def _format_pydantic_error(err: ValidationError) -> str:
    parts = []
    for e in err.errors():
        loc = ".".join(str(p) for p in e["loc"]) or "<record>"
        parts.append(f"{loc}: {e['msg']}")
    return "; ".join(parts)


def read_jsonl_models(
    path: Path, model: type[ModelT]
) -> tuple[list[tuple[int, ModelT]], list[ValidationIssue]]:
    """Parse a JSONL file into models. Blank lines are skipped.

    Returns successfully parsed ``(line_number, record)`` pairs and a list of
    issues; one bad line does not stop the rest of the file being checked.
    """
    records: list[tuple[int, ModelT]] = []
    issues: list[ValidationIssue] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [ValidationIssue(path, None, f"cannot read file: {exc}")]

    for line_no, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            issues.append(ValidationIssue(path, line_no, f"invalid JSON: {exc.msg}"))
            continue
        if not isinstance(data, dict):
            issues.append(ValidationIssue(path, line_no, "each line must be a JSON object"))
            continue
        try:
            records.append((line_no, model.model_validate(data)))
        except ValidationError as exc:
            issues.append(ValidationIssue(path, line_no, _format_pydantic_error(exc)))
    return records, issues
