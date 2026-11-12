"""Source-verification workflow: snapshots, machine text checks and an auditable log.

Policy:

1. A machine check can confirm that a stored passage occurs verbatim in a
   snapshot of the official page. It cannot verify the passage.
2. Only a human-review entry (``check_type: human_review``, ``result:
   confirmed``) in the verification log allows a source or passage to have the
   status ``verified``. The validator enforces this.
3. An LLM statement that evidence is correct is never a verification entry.

The log is ``verification_log.jsonl`` in the same directory as the source and
passage files. Entries are appended, never edited.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from liverswat_bench import __version__

LOG_FILENAME = "verification_log.jsonl"
USER_AGENT = f"liverswat-bench-evidence-snapshot/{__version__}"
TOOL_ID = f"automated:liverswat-bench/{__version__}"


class VerificationError(RuntimeError):
    pass


class LogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    source_id: str
    passage_id: str | None = None
    check_type: Literal["machine_text_match", "human_review"]
    result: Literal["match", "no_match", "not_checkable", "confirmed", "rejected", "needs_changes"]
    performed_by: str = Field(min_length=1)
    snapshot_url: str | None = None
    snapshot_sha256: str | None = None
    snapshot_retrieved_at: datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> LogEntry:
        machine = self.check_type == "machine_text_match"
        if machine and self.result not in ("match", "no_match", "not_checkable"):
            raise ValueError("machine checks record match, no_match or not_checkable")
        if not machine and self.result not in ("confirmed", "rejected", "needs_changes"):
            raise ValueError("human reviews record confirmed, rejected or needs_changes")
        if not machine and self.performed_by.lower().startswith("automated"):
            raise ValueError("a human review must name a human reviewer")
        if machine and not self.performed_by.startswith("automated:"):
            raise ValueError("machine checks must be performed_by 'automated:<tool>'")
        return self


def read_log(path: Path) -> list[LogEntry]:
    if not path.is_file():
        return []
    entries = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip():
            try:
                entries.append(LogEntry.model_validate_json(line))
            except ValueError as exc:
                raise VerificationError(f"{path}:{line_no}: invalid log entry: {exc}") from exc
    return entries


def append_log(path: Path, entries: list[LogEntry]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(entry.model_dump_json(exclude_none=True) + "\n")


def human_confirmed(entries: list[LogEntry]) -> tuple[set[str], set[str]]:
    """(source IDs, passage IDs) whose latest human review is 'confirmed'."""
    latest: dict[tuple[str, str | None], LogEntry] = {}
    for e in sorted(entries, key=lambda e: e.timestamp):
        if e.check_type == "human_review":
            latest[(e.source_id, e.passage_id)] = e
    sources = {s for (s, p), e in latest.items() if p is None and e.result == "confirmed"}
    passages = {p for (_, p), e in latest.items() if p is not None and e.result == "confirmed"}
    return sources, passages


# ------------------------------------------------------------- text extraction


class _TextParser(HTMLParser):
    SKIP = frozenset({"script", "style", "noscript", "svg", "head"})
    BLOCK = frozenset(
        {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "div", "section", "br", "dd"}
    )

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(html)
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)


def pdf_to_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader  # optional dependency
    except ImportError as exc:
        raise VerificationError("PDF text extraction needs the optional package 'pypdf'") from exc
    import io

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def normalise_for_match(text: str) -> str:
    """Whitespace, non-breaking spaces and curly quotes only. Case and wording are kept."""
    text = text.replace("\u00a0", " ").replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------- snapshots


class SnapshotMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    url: str
    final_url: str
    http_status: int
    content_type: str | None
    retrieved_at: datetime
    sha256: str
    raw_file: str
    text_file: str


def take_snapshot(source_id: str, url: str, out_dir: Path, timeout: float = 30) -> SnapshotMeta:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
            status = response.status
            final_url = response.geturl()
            content_type = response.headers.get("Content-Type")
    except urllib.error.HTTPError as exc:
        raise VerificationError(f"{source_id}: HTTP {exc.code} for {url}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise VerificationError(f"{source_id}: cannot fetch {url}: {exc}") from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    is_pdf = (content_type or "").startswith("application/pdf") or data[:5] == b"%PDF-"
    raw_path = out_dir / f"{source_id}.{'pdf' if is_pdf else 'html'}"
    text_path = out_dir / f"{source_id}.txt"
    raw_path.write_bytes(data)
    text = pdf_to_text(data) if is_pdf else html_to_text(data.decode("utf-8", errors="replace"))
    text_path.write_text(text, encoding="utf-8")
    meta = SnapshotMeta(
        source_id=source_id,
        url=url,
        final_url=final_url,
        http_status=status,
        content_type=content_type,
        retrieved_at=datetime.now(UTC),
        sha256=hashlib.sha256(data).hexdigest(),
        raw_file=raw_path.name,
        text_file=text_path.name,
    )
    (out_dir / f"{source_id}.meta.json").write_text(meta.model_dump_json(indent=2) + "\n")
    return meta


def load_snapshots(snapshot_dir: Path) -> dict[str, tuple[SnapshotMeta, str]]:
    out = {}
    for meta_path in sorted(snapshot_dir.glob("*.meta.json")):
        meta = SnapshotMeta.model_validate_json(meta_path.read_text())
        text = (snapshot_dir / meta.text_file).read_text(encoding="utf-8")
        out[meta.source_id] = (meta, text)
    return out


def machine_check(registry, snapshots: dict[str, tuple[SnapshotMeta, str]]) -> list[LogEntry]:
    """Check each passage of each snapshotted source for a verbatim match."""
    entries: list[LogEntry] = []
    now = datetime.now(UTC)
    for passage in sorted(registry.passages.values(), key=lambda p: p.passage_id):
        if passage.source_id not in snapshots:
            continue
        meta, text = snapshots[passage.source_id]
        if not passage.text:
            result, notes = "not_checkable", "passage stores no text (locator only)"
        elif normalise_for_match(passage.text) in normalise_for_match(text):
            result, notes = (
                "match",
                "passage text found verbatim (whitespace and quotes normalised)",
            )
        else:
            result, notes = "no_match", "passage text not found in snapshot"
        entries.append(
            LogEntry(
                timestamp=now,
                source_id=passage.source_id,
                passage_id=passage.passage_id,
                check_type="machine_text_match",
                result=result,
                performed_by=TOOL_ID,
                snapshot_url=meta.final_url,
                snapshot_sha256=meta.sha256,
                snapshot_retrieved_at=meta.retrieved_at,
                notes=notes,
            )
        )
    return entries


def summarise_status(registry, entries: list[LogEntry]) -> list[dict]:
    """Per passage: registry status, latest machine result, latest human result."""
    latest_machine: dict[str, LogEntry] = {}
    latest_human: dict[str, LogEntry] = {}
    for e in sorted(entries, key=lambda e: e.timestamp):
        if e.passage_id is None:
            continue
        target = latest_machine if e.check_type == "machine_text_match" else latest_human
        target[e.passage_id] = e
    rows = []
    for pid, passage in sorted(registry.passages.items()):
        m, h = latest_machine.get(pid), latest_human.get(pid)
        rows.append(
            {
                "passage_id": pid,
                "source_id": passage.source_id,
                "status": passage.status.value,
                "machine_check": m.result if m else None,
                "machine_checked_at": m.timestamp.isoformat() if m else None,
                "human_review": h.result if h else None,
                "human_reviewer": h.performed_by if h else None,
            }
        )
    return rows


def dumps(rows: list[dict]) -> str:
    return json.dumps(rows, indent=2)
