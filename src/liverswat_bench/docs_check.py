"""Advisory documentation style check, based on ASD-STE100 principles.

This check does not certify ASD-STE100 compliance. It reports four kinds of
finding:

* ``discouraged_term`` (deterministic): terms the project policy forbids, such
  as "safe model", or "clinically validated" without a nearby negation. Only
  these findings can fail the check, and only with ``--strict``.
* ``undefined_abbreviation`` (advisory): an upper-case abbreviation used before
  it is defined in the form "Expansion (ABBR)" or "ABBR (expansion)".
* ``long_sentence`` (advisory): a prose sentence longer than the word limit.
* ``ambiguous_wording`` (advisory): vague words or a sentence that starts with
  a pronoun such as "It" or "This" followed by a linking verb.

Code blocks, inline code, URLs and table rows are ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_WORDS = 25

#: Abbreviations accepted without definition (common file formats and the country).
KNOWN_ABBREVIATIONS = frozenset(
    {"UK", "JSON", "JSONL", "CSV", "YAML", "URL", "URLS", "PDF", "HTML", "ID", "IDS", "OK", "MIT"}
)

DISCOURAGED: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bsafe models?\b", re.I),
        'Do not use "safe model"; describe the benchmark result.',
    ),
    (
        re.compile(r"\bjudge outputs?\b", re.I),
        'Use the project term "judge result" instead of "judge output".',
    ),
]
_CLIN_VALIDATED = re.compile(r"\bclinically[- ]validated\b", re.I)
_NEGATION_BEFORE = re.compile(r"\b(not|never|no|without|un)\b[\w\s,-]{0,25}$", re.I)

_VAGUE = re.compile(r"\b(etc\.?|and so on|various|stuff|things like|some sort of)\b", re.I)
_PRONOUN_START = re.compile(r"^(It|This|That|These|Those) (is|are|was|were|means|can|will)\b")

#: Capitalised English words used for emphasis, not abbreviations.
EMPHASIS_WORDS = frozenset({"NOT", "AND", "OR", "ALL", "NO", "ONLY", "MUST", "NEVER", "DO"})

_ABBR = re.compile(r"\b[A-Z][A-Z0-9]{1,}(?:-[A-Z0-9]+)*s?\b")
_DEFINED_AFTER = re.compile(r"\(([A-Z][A-Z0-9]{1,}(?:-[A-Z0-9]+)*)s?\)")
_DEFINED_BEFORE = re.compile(r"\b([A-Z][A-Z0-9]{1,}(?:-[A-Z0-9]+)*) \([a-z]", re.I)


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    rule: str
    message: str
    excerpt: str
    enforceable: bool = False

    def __str__(self) -> str:
        level = "ERROR" if self.enforceable else "advisory"
        return f"{self.path}:{self.line}: [{level}] {self.rule}: {self.message} | {self.excerpt}"


def _strip_inline(text: str) -> str:
    text = re.sub(r"`[^`]*`", " CODE ", text)
    text = re.sub(r"\]\([^)]*\)", "]", text)  # markdown link targets
    text = re.sub(r"https?://\S+", " URL ", text)
    return text


def _paragraphs(markdown: str) -> list[tuple[int, str, str]]:
    """Return (start_line, text, kind) blocks; kind is "prose", "heading" or "table"."""
    blocks: list[tuple[int, str, str]] = []
    in_code = False
    current: list[str] = []
    start = 0

    def flush():
        if current:
            blocks.append((start, " ".join(current), "prose"))
            current.clear()

    for i, raw in enumerate(markdown.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("```"):
            in_code = not in_code
            flush()
            continue
        if in_code or not line:
            flush()
            continue
        if line.startswith("|"):
            flush()
            if not re.fullmatch(r"[|\s:-]+", line):  # skip separator rows
                blocks.append((i, line.strip("|").replace("|", " ; "), "table"))
            continue
        if line.startswith("#"):
            flush()
            blocks.append((i, line.lstrip("#").strip(), "heading"))
            continue
        if re.match(r"^([-*+]|\d+\.)\s", line) or line.startswith(">"):
            flush()
            start = i
            current.append(re.sub(r"^([-*+]|\d+\.|>)\s*", "", line))
            continue
        if not current:
            start = i
        current.append(line)
    flush()
    return blocks


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(])", text)
    return [p.strip() for p in parts if p.strip()]


def check_text(path: Path, markdown: str, max_words: int = DEFAULT_MAX_WORDS) -> list[Finding]:
    findings: list[Finding] = []
    defined: set[str] = set(KNOWN_ABBREVIATIONS)
    reported_abbr: set[str] = set()
    for line_no, block, kind in _paragraphs(markdown):
        text = _strip_inline(block)
        for m in _DEFINED_AFTER.finditer(text):
            defined.add(m.group(1).upper())
        for m in _DEFINED_BEFORE.finditer(text):
            if m.group(1).isupper():
                defined.add(m.group(1).upper())

        for pattern, message in DISCOURAGED:
            for m in pattern.finditer(text):
                findings.append(
                    Finding(path, line_no, "discouraged_term", message, m.group(0), True)
                )
        for m in _CLIN_VALIDATED.finditer(text):
            if not _NEGATION_BEFORE.search(text[: m.start()]):
                findings.append(
                    Finding(
                        path,
                        line_no,
                        "discouraged_term",
                        '"clinically validated" without negation: source evidence checked '
                        "against guidance is not clinical validation.",
                        text[max(0, m.start() - 30) : m.end()],
                        True,
                    )
                )

        for m in _ABBR.finditer(text):
            token = m.group(0)
            base = token[:-1] if token.endswith("s") and token[:-1].isupper() else token
            if base in ("CODE", "URL") or base.upper() in defined or base in reported_abbr:
                continue
            if len(base) < 2 or base.isdigit() or base in EMPHASIS_WORDS:
                continue
            # Long all-capital words without digits are emphasis or file names (LICENSE),
            # not abbreviations.
            if len(base.replace("-", "")) > 6 and not any(ch.isdigit() for ch in base):
                continue
            reported_abbr.add(base)
            findings.append(
                Finding(
                    path,
                    line_no,
                    "undefined_abbreviation",
                    f'"{base}" is not defined at first use (write "Expansion ({base})").',
                    text[max(0, m.start() - 20) : m.end() + 20],
                )
            )

        if kind != "prose":  # headings and table cells are not sentences
            continue
        for sentence in _sentences(text):
            words = sentence.split()
            if len(words) > max_words:
                findings.append(
                    Finding(
                        path,
                        line_no,
                        "long_sentence",
                        f"{len(words)} words (advisory limit {max_words}).",
                        " ".join(words[:12]) + " ...",
                    )
                )
            if _VAGUE.search(sentence) or _PRONOUN_START.search(sentence):
                findings.append(
                    Finding(
                        path,
                        line_no,
                        "ambiguous_wording",
                        "Vague word or pronoun start; name the subject explicitly.",
                        " ".join(words[:12]),
                    )
                )
    return findings


def default_paths(root: Path) -> list[Path]:
    paths = [root / "README.md", root / "DATASET_CARD.md", root / "CONTRIBUTING.md"]
    paths += sorted((root / "docs").rglob("*.md"))
    return [p for p in paths if p.is_file()]


def check_files(paths: list[Path], max_words: int = DEFAULT_MAX_WORDS) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        findings.extend(check_text(path, path.read_text(encoding="utf-8"), max_words))
    return findings
