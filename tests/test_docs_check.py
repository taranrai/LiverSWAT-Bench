from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from liverswat_bench.cli import EXIT_INVALID, app
from liverswat_bench.docs_check import check_files, check_text, default_paths
from tests.conftest import REPO_ROOT

P = Path("doc.md")


def rules(text: str, **kw) -> list[tuple[str, bool]]:
    return [(f.rule, f.enforceable) for f in check_text(P, text, **kw)]


def test_discouraged_terms_are_deterministic():
    findings = check_text(P, "This is a safe model. Use the judge output.")
    terms = [f for f in findings if f.rule == "discouraged_term"]
    assert len(terms) == 2 and all(f.enforceable for f in terms)


def test_clinically_validated_needs_negation():
    assert ("discouraged_term", True) in rules("The items are clinically validated.")
    assert not any(
        r == "discouraged_term" for r, _ in rules("The items are not clinically validated.")
    )
    assert not any(
        r == "discouraged_term"
        for r, _ in rules("It is evidence-grounded, never clinically validated.")
    )


def test_abbreviations_defined_at_first_use_are_accepted():
    ok = "The National Health Service (NHS) publishes guidance. The NHS updates it."
    assert not any(r == "undefined_abbreviation" for r, _ in rules(ok))
    ok2 = "Results go to the LLM (large language model) judge."
    assert not any(r == "undefined_abbreviation" for r, _ in rules(ok2))
    bad = check_text(P, "Use the BSG guidance. The BSG guidance is long.")
    abbr = [f for f in bad if f.rule == "undefined_abbreviation"]
    assert len(abbr) == 1 and not abbr[0].enforceable  # reported once, advisory


def test_known_formats_emphasis_and_code_are_ignored():
    text = (
        "Write JSON and CSV files. Do NOT edit LICENSE.\n\n```\nRUN SOMETHING ABC\n```\n`XYZ` code."
    )
    assert not any(r == "undefined_abbreviation" for r, _ in rules(text))


def test_long_sentence_and_ambiguous_wording_are_advisory():
    long = " ".join(["word"] * 30) + "."
    found = check_text(P, long + " It is unclear. Use various tools etc.")
    by_rule = {f.rule for f in found}
    assert {"long_sentence", "ambiguous_wording"} <= by_rule
    assert not any(f.enforceable for f in found)
    assert not any(r == "long_sentence" for r, _ in rules(long, max_words=40))


def test_tables_and_headings_are_not_length_checked():
    text = "# " + " ".join(["Heading"] * 40) + "\n\n| " + " | ".join(["cell"] * 40) + " |\n"
    assert not any(r == "long_sentence" for r, _ in rules(text))


def test_repository_docs_have_no_deterministic_findings():
    findings = check_files(default_paths(REPO_ROOT))
    errors = [str(f) for f in findings if f.enforceable]
    assert errors == []


def test_cli_check_docs(tmp_path):
    runner = CliRunner()
    good = tmp_path / "good.md"
    good.write_text("Run the test. The test checks the file.\n")
    bad = tmp_path / "bad.md"
    bad.write_text("This is a safe model.\n")
    result = runner.invoke(app, ["check-docs", str(good), str(bad)])
    assert result.exit_code == 0  # advisory by default
    assert "does not certify ASD-STE100 compliance" in result.output
    strict = runner.invoke(app, ["check-docs", "--strict", str(bad)])
    assert strict.exit_code == EXIT_INVALID
    missing = runner.invoke(app, ["check-docs", str(tmp_path / "none.md")])
    assert missing.exit_code == EXIT_INVALID
