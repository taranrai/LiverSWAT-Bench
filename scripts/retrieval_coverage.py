"""Write the retrieval coverage report for a pilot (Condition B, retrieved).

Usage: python scripts/retrieval_coverage.py RESULTS_DIR
Reads RESULTS_DIR/*__retrieved/responses.jsonl and writes RESULTS_DIR/retrieval_coverage.json.
The report describes the retriever only. It does not assess model responses.
"""

import json
import sys
from pathlib import Path
from statistics import fmean

results = Path(sys.argv[1])
runs = sorted(results.glob("*__retrieved"))
if not runs:
    sys.exit(f"no *__retrieved runs in {results}")
per_run = {}
for run in runs:
    records = [json.loads(line) for line in (run / "responses.jsonl").read_text().splitlines()]
    per_run[run.name] = {r["question_id"]: r["evidence"] for r in records}
first = next(iter(per_run.values()))


def retrieved_ids(run: dict) -> dict:
    return {q: e["passage_ids"] for q, e in run.items()}


identical = all(retrieved_ids(other) == retrieved_ids(first) for other in per_run.values())
items = []
for qid, e in first.items():
    oracle = e["oracle_passage_ids"]
    items.append(
        {
            "question_id": qid,
            "oracle_passage_ids": oracle,
            "retrieved": [
                {"passage_id": p, "score": e["retrieval_scores"][p], "cited_by_item": p in oracle}
                for p in e["passage_ids"]
            ],
            "oracle_recall": e["oracle_recall"],
        }
    )
manifest = json.loads((runs[0] / "manifest.json").read_text())
recalls = [i["oracle_recall"] for i in items]
retrieved_total = sum(len(i["retrieved"]) for i in items)
report = {
    "description": "Retrieval coverage for Condition B (retrieved). Describes the retriever only.",
    "retriever": manifest["retriever"],
    "runs": list(per_run),
    "retrieval_identical_across_runs": identical,
    "n_items": len(items),
    "mean_oracle_recall": round(fmean(recalls), 4),
    "items_full_recall": sum(r == 1.0 for r in recalls),
    "items_zero_recall": sum(r == 0 for r in recalls),
    "retrieved_passages_not_cited": {
        "numerator": sum(not p["cited_by_item"] for i in items for p in i["retrieved"]),
        "denominator": retrieved_total,
    },
    "items": items,
}
(results / "retrieval_coverage.json").write_text(json.dumps(report, indent=2) + "\n")
print(f"wrote {results / 'retrieval_coverage.json'}")
