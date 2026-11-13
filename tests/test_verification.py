"""Source-verification workflow: log rules, machine checks, snapshots and enforcement."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from liverswat_bench.cli import EXIT_INVALID, app
from liverswat_bench.evidence.registry import EvidenceRegistry
from liverswat_bench.evidence.verification import (
    LogEntry,
    VerificationError,
    html_to_text,
    human_confirmed,
    load_snapshots,
    machine_check,
    normalise_for_match,
    read_log,
    take_snapshot,
)
from tests.conftest import write_jsonl

TS = "2026-11-12T00:00:00Z"
PAGE = (
    "<html><head><title>x</title><script>var a=1;</script></head><body>"
    "<h1>Test page</h1><p>Treatment can cure the\n   infection in most people.</p>"
    "<p>It\u2019s important to finish treatment.</p></body></html>"
)


def registry_files(tmp_path, status="unverified", with_review=False):
    source = {"source_id": "SRC-T", "organisation": "NHS", "title": "TEST FIXTURE"}
    if status == "verified":
        source.update(source_status="verified", url="https://example.org/x",
                      date_accessed="2026-11-12", licence="test")  # fmt: skip
    passages = [
        {"passage_id": "PSG-T-1", "source_id": "SRC-T", "section": "s", "locator": "l",
         "text_type": "verbatim", "text": "Treatment can cure the infection in most people.",
         "status": status, **({"date_verified": "2026-11-12"} if status == "verified" else {})},
        {"passage_id": "PSG-T-2", "source_id": "SRC-T", "section": "s", "locator": "l",
         "text_type": "verbatim", "text": "Treatment always cures everyone."},
        {"passage_id": "PSG-T-3", "source_id": "SRC-T", "section": "s", "locator": "l",
         "text_type": "locator_only"},
    ]  # fmt: skip
    s = write_jsonl(tmp_path / "sources.jsonl", [source])
    p = write_jsonl(tmp_path / "passages.jsonl", passages)
    if with_review:
        base = {"timestamp": TS, "source_id": "SRC-T", "check_type": "human_review",
                "result": "confirmed", "performed_by": "A. Reviewer"}  # fmt: skip
        write_jsonl(tmp_path / "verification_log.jsonl", [base, {**base, "passage_id": "PSG-T-1"}])
    return s, p


def test_log_entry_rules():
    with pytest.raises(ValidationError, match="human reviewer"):
        LogEntry.model_validate(
            {"timestamp": TS, "source_id": "S", "check_type": "human_review",
             "result": "confirmed", "performed_by": "automated:llm"}
        )  # fmt: skip
    with pytest.raises(ValidationError, match="machine checks record"):
        LogEntry.model_validate({"timestamp": TS, "source_id": "S",
                                 "check_type": "machine_text_match", "result": "confirmed",
                                 "performed_by": "automated:x"})  # fmt: skip
    with pytest.raises(ValidationError, match="automated:"):
        LogEntry.model_validate({"timestamp": TS, "source_id": "S",
                                 "check_type": "machine_text_match", "result": "match",
                                 "performed_by": "someone"})  # fmt: skip


def test_latest_human_review_wins():
    entries = [
        LogEntry(timestamp="2026-01-01T00:00:00Z", source_id="S", passage_id="P",
                 check_type="human_review", result="confirmed", performed_by="R"),
        LogEntry(timestamp="2026-02-01T00:00:00Z", source_id="S", passage_id="P",
                 check_type="human_review", result="rejected", performed_by="R"),
    ]  # fmt: skip
    assert human_confirmed(entries) == (set(), set())


def test_verified_evidence_without_human_review_is_rejected(tmp_path):
    s, p = registry_files(tmp_path, status="verified")
    _, issues = EvidenceRegistry.load([s], [p])
    messages = [i.message for i in issues]
    assert any(
        "source 'SRC-T' is verified but has no confirmed human review" in m for m in messages
    )
    assert any(
        "passage 'PSG-T-1' is verified but has no confirmed human review" in m for m in messages
    )


def test_verified_evidence_with_human_review_is_accepted(tmp_path):
    s, p = registry_files(tmp_path, status="verified", with_review=True)
    _, issues = EvidenceRegistry.load([s], [p])
    assert issues == []


def test_machine_match_alone_does_not_verify(tmp_path):
    s, p = registry_files(tmp_path, status="verified")
    machine = {"timestamp": TS, "source_id": "SRC-T", "passage_id": "PSG-T-1",
               "check_type": "machine_text_match", "result": "match",
               "performed_by": "automated:liverswat"}  # fmt: skip
    write_jsonl(tmp_path / "verification_log.jsonl", [machine])
    _, issues = EvidenceRegistry.load([s], [p])
    assert any("no confirmed human review" in i.message for i in issues)


def test_invalid_log_is_reported(tmp_path):
    s, p = registry_files(tmp_path)
    (tmp_path / "verification_log.jsonl").write_text("{not json\n")
    _, issues = EvidenceRegistry.load([s], [p])
    assert any("invalid log entry" in i.message for i in issues)
    with pytest.raises(VerificationError):
        read_log(tmp_path / "verification_log.jsonl")


def test_html_to_text_and_normalisation():
    text = html_to_text(PAGE)
    assert "var a" not in text and "Test page" in text
    assert normalise_for_match("It\u2019s  important\u00a0to") == "It's important to"
    assert normalise_for_match("Case Kept") != normalise_for_match("case kept")


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/missing":
            self.send_response(404)
            self.end_headers()
            return
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_snapshot_and_machine_check(tmp_path, server):
    s, p = registry_files(tmp_path)
    meta = take_snapshot("SRC-T", f"{server}/page", tmp_path / "snaps")
    assert meta.http_status == 200 and len(meta.sha256) == 64
    registry, _ = EvidenceRegistry.load([s], [p])
    entries = machine_check(registry, load_snapshots(tmp_path / "snaps"))
    results = {e.passage_id: e.result for e in entries}
    assert results == {"PSG-T-1": "match", "PSG-T-2": "no_match", "PSG-T-3": "not_checkable"}
    assert all(e.snapshot_sha256 == meta.sha256 for e in entries)
    assert all(e.performed_by.startswith("automated:") for e in entries)


def test_snapshot_http_error(tmp_path, server):
    with pytest.raises(VerificationError, match="HTTP 404"):
        take_snapshot("SRC-T", f"{server}/missing", tmp_path)


def test_evidence_cli_workflow(tmp_path, server):
    data = tmp_path / "data"
    data.mkdir()
    s, _ = registry_files(data)
    rows = [json.loads(line) for line in s.read_text().splitlines()]
    rows[0]["url"] = f"{server}/page"
    write_jsonl(s, rows)
    runner = CliRunner()
    snaps = tmp_path / "snaps"
    out = runner.invoke(app, ["evidence", "snapshot", "--data-dir", str(data), "--out", str(snaps)])
    assert out.exit_code == 0, out.output
    out = runner.invoke(app, ["evidence", "check", "--data-dir", str(data),
                              "--snapshots", str(snaps), "--record"])  # fmt: skip
    assert out.exit_code == 0, out.output
    assert "1 match, 1 no_match, 1 not_checkable" in out.output
    log = read_log(data / "verification_log.jsonl")
    assert len(log) == 3
    out = runner.invoke(app, ["evidence", "record-review", "--data-dir", str(data),
                              "--source-id", "SRC-T", "--passage-id", "PSG-T-1",
                              "--reviewer", "A. Reviewer", "--result", "confirmed"])  # fmt: skip
    assert out.exit_code == 0, out.output
    assert read_log(data / "verification_log.jsonl")[-1].check_type == "human_review"
    bad = runner.invoke(app, ["evidence", "record-review", "--data-dir", str(data),
                              "--source-id", "SRC-T", "--reviewer", "automated:llm",
                              "--result", "confirmed"])  # fmt: skip
    assert bad.exit_code == EXIT_INVALID
    status = runner.invoke(app, ["evidence", "status", "--data-dir", str(data)])
    assert status.exit_code == 0 and "PSG-T-1" in status.output
