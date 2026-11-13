"""Evidence conditions (baseline, retrieved, oracle) and the lexical retriever."""

from __future__ import annotations

import pytest

from liverswat_bench.datasets import discover_files
from liverswat_bench.datasets.schema import BenchmarkItem
from liverswat_bench.evaluation.conditions import (
    EVIDENCE_INSTRUCTION,
    EvidenceCondition,
    build_condition_messages,
)
from liverswat_bench.evaluation.records import ResponseRecord, RunManifest
from liverswat_bench.evaluation.runner import EvaluationError, run_evaluation
from liverswat_bench.evidence.registry import EvidenceRegistry
from liverswat_bench.evidence.retrieval import LexicalRetriever, tokenise
from liverswat_bench.io import read_jsonl_models
from liverswat_bench.models.config import load_model_config
from tests.conftest import REPO_ROOT, load_jsonl

NHS = REPO_ROOT / "data" / "pilot" / "nhs_pilot_items.jsonl"
DEMO = REPO_ROOT / "data" / "examples" / "demo_items.jsonl"
MOCK = REPO_ROOT / "configs" / "models" / "mock.yaml"
_, SOURCES, PASSAGES = discover_files(REPO_ROOT / "data")
REGISTRY, _ = EvidenceRegistry.load(SOURCES, PASSAGES)
ITEMS = {i.question_id: i for _, i in read_jsonl_models(NHS, BenchmarkItem)[0]}
CONFIG = load_model_config(MOCK)


def test_tokenise_removes_stopwords_and_punctuation():
    assert tokenise("Can I catch hepatitis C by hugging?") == ["catch", "hepatitis", "hugging"]


def test_retriever_is_deterministic_and_ranks_relevant_passage_first():
    retriever = LexicalRetriever.from_registry(REGISTRY, synthetic=False)
    hits = retriever.search("Can I catch hepatitis C by hugging someone or sharing food?", 3)
    assert hits[0].passage_id == "PSG-NHS-HEPC-TRANSMISSION"
    assert hits == retriever.search(
        "Can I catch hepatitis C by hugging someone or sharing food?", 3
    )
    assert all(h.score > 0 for h in hits)
    assert retriever.search("zzzz qqqq", 3) == []


def test_retriever_corpus_excludes_synthetic_passages():
    real = LexicalRetriever.from_registry(REGISTRY, synthetic=False)
    demo = LexicalRetriever.from_registry(REGISTRY, synthetic=True)
    assert not any(p.passage_id.startswith("PSG-DEMO") for p in real.passages)
    assert all(p.passage_id.startswith("PSG-DEMO") for p in demo.passages)
    assert real.corpus_sha256 != demo.corpus_sha256


def test_baseline_messages_are_unchanged():
    item = ITEMS["LSB-HEPC-0001"]
    messages, evidence = build_condition_messages(
        CONFIG, item, EvidenceCondition.BASELINE, REGISTRY
    )
    assert messages == CONFIG.build_messages(item.question)
    assert evidence.condition == "baseline" and evidence.passage_ids == []
    assert evidence.oracle_passage_ids == item.evidence_passage_ids


def test_oracle_supplies_exact_cited_passages():
    item = ITEMS["LSB-HEPC-0001"]
    messages, evidence = build_condition_messages(CONFIG, item, EvidenceCondition.ORACLE, REGISTRY)
    assert evidence.passage_ids == item.evidence_passage_ids
    content = messages[-1]["content"]
    assert content.startswith(EVIDENCE_INSTRUCTION)
    for pid in item.evidence_passage_ids:
        assert REGISTRY.passages[pid].text in content
    assert content.rstrip().endswith(item.question)
    assert evidence.passages_verified == []  # nothing is verified yet


def test_retrieved_records_scores_and_oracle_recall():
    item = ITEMS["LSB-HEPC-0003"]
    retriever = LexicalRetriever.from_registry(REGISTRY, synthetic=False)
    _, evidence = build_condition_messages(
        CONFIG, item, EvidenceCondition.RETRIEVED, REGISTRY, retriever, top_k=2
    )
    assert len(evidence.passage_ids) == 2
    assert set(evidence.retrieval_scores) == set(evidence.passage_ids)
    assert evidence.retriever == "lexical-tfidf-v1"
    assert evidence.corpus_size == len(retriever.passages)
    assert evidence.oracle_recall == 1.0


def test_retrieved_condition_requires_retriever():
    with pytest.raises(ValueError, match="needs a retriever"):
        build_condition_messages(
            CONFIG, ITEMS["LSB-HEPC-0001"], EvidenceCondition.RETRIEVED, REGISTRY
        )


@pytest.mark.parametrize("condition", ["baseline", "retrieved", "oracle"])
def test_runner_records_condition_with_same_generation_settings(tmp_path, condition):
    run = run_evaluation(
        model_config_path=MOCK, dataset_path=NHS, source_files=SOURCES, passage_files=PASSAGES,
        output_dir=tmp_path, evidence_condition=condition, repo_root=REPO_ROOT,
    )  # fmt: skip
    recs = [ResponseRecord.model_validate(r) for r in load_jsonl(run.responses_path)]
    assert {r.evidence.condition for r in recs} == {condition}
    assert {r.generation.model_dump_json() for r in recs} == {CONFIG.generation.model_dump_json()}
    manifest = RunManifest.model_validate_json((run.output_dir / "manifest.json").read_text())
    assert manifest.evidence_condition == condition
    assert (manifest.retriever is not None) == (condition == "retrieved")
    if condition != "baseline":
        assert run.output_dir.name.endswith(condition)


def test_unknown_condition_is_rejected(tmp_path):
    with pytest.raises(EvaluationError, match="unknown evidence condition"):
        run_evaluation(
            model_config_path=MOCK, dataset_path=DEMO, source_files=SOURCES,
            passage_files=PASSAGES, output_dir=tmp_path, evidence_condition="rag",
        )  # fmt: skip


def test_milestone_4_response_records_still_load_as_baseline(tmp_path):
    run = run_evaluation(
        model_config_path=MOCK, dataset_path=DEMO, source_files=SOURCES,
        passage_files=PASSAGES, output_dir=tmp_path, experiment_id="legacy",
    )  # fmt: skip
    raw = load_jsonl(run.responses_path)[0]
    del raw["evidence"]  # Milestone 4 records had no evidence field
    record = ResponseRecord.model_validate(raw)
    assert record.evidence.condition == "baseline"
    assert record.evidence.passage_ids == []
