"""Judge parsing, validation, retries, abstention and evidence policy. No real models."""

from __future__ import annotations

import json

import pytest

from liverswat_bench.datasets import discover_files
from liverswat_bench.datasets.schema import BenchmarkItem
from liverswat_bench.evaluation.records import ResponseRecord
from liverswat_bench.evaluation.runner import run_evaluation
from liverswat_bench.evidence.registry import EvidenceRegistry
from liverswat_bench.io import read_jsonl_models
from liverswat_bench.judges.prompts import build_messages
from liverswat_bench.judges.runner import judge_one, select_passages
from liverswat_bench.judges.schema import JudgeConfig
from liverswat_bench.judges.validate import (
    JudgeOutputError,
    extract_json,
    parse_output,
    validate_output,
)
from tests import judge_fixtures as jf
from tests.conftest import REPO_ROOT

DEMO = REPO_ROOT / "data" / "examples" / "demo_items.jsonl"
_, SOURCES, PASSAGES = discover_files(REPO_ROOT / "data")
REGISTRY, _ = EvidenceRegistry.load(SOURCES, PASSAGES)
ITEMS = {i.question_id: i for _, i in read_jsonl_models(DEMO, BenchmarkItem)[0]}
ITEM = ITEMS["DEMO-0002"]  # passages PSG-DEMO-0002, PSG-DEMO-0003
RESPONSE = "Yes. A normal liver blood test proves your liver is healthy."
SUPPLIED = {"PSG-DEMO-0002", "PSG-DEMO-0003"}


def judge_config(**kw) -> JudgeConfig:
    data = {
        "judge_id": "test-judge",
        "evidence_policy": "include_unverified",
        "max_retries": 2,
        "model": {"config_id": "t", "model_name": "t", "backend": "mock"},
    }
    data.update(kw)
    return JudgeConfig.model_validate(data)


@pytest.fixture(scope="module")
def responses(tmp_path_factory) -> dict[str, ResponseRecord]:
    import os

    out = tmp_path_factory.mktemp("runs")
    cwd = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        run = run_evaluation(
            model_config_path=REPO_ROOT / "configs/models/mock-scripted.yaml",
            dataset_path=DEMO,
            source_files=SOURCES,
            passage_files=PASSAGES,
            output_dir=out,
            experiment_id="judge-tests",
            repo_root=REPO_ROOT,
        )
    finally:
        os.chdir(cwd)
    return {r.question_id: r for _, r in read_jsonl_models(run.responses_path, ResponseRecord)[0]}


# ------------------------------------------------------------------ parsing


@pytest.mark.parametrize(
    "text",
    [
        '{"a": 1}',
        'Here is my assessment:\n```json\n{"a": 1}\n```\nThanks.',
        'Sure! {"a": 1} Hope that helps.',
    ],
)
def test_extract_json_variants(text):
    assert extract_json(text) == {"a": 1}


@pytest.mark.parametrize("text", ["not json at all", "{broken: json", "[1, 2, 3]"])
def test_invalid_json(text):
    with pytest.raises(JudgeOutputError, match="no valid JSON object"):
        extract_json(text)


def test_schema_errors():
    good = json.loads(jf.output())
    missing = {**good, "dimensions": good["dimensions"][:-1]}
    with pytest.raises(JudgeOutputError, match="each of the six dimensions"):
        parse_output(json.dumps(missing))
    out_of_range = json.loads(jf.output({"actionability": jf.dim("actionability", 5)}))
    with pytest.raises(JudgeOutputError, match="schema"):
        parse_output(json.dumps(out_of_range))
    both = jf.dim("actionability", 2)
    both["abstain"] = True
    both["abstain_reason"] = "x"
    with pytest.raises(JudgeOutputError, match="must not give a score"):
        parse_output(jf.output({"actionability": both}))


# --------------------------------------------------------------- validation


def validate(text: str, response: str = RESPONSE, supplied=SUPPLIED, item=ITEM):
    return validate_output(parse_output(text), item, response, set(supplied))


def test_valid_output_is_scored():
    dims, _, issues = validate(jf.output())
    assert {d.status for d in dims} == {"scored"}
    assert issues == []


def test_claim_classifications_preserved():
    claims_in = [
        jf.claim(
            "A normal liver blood test proves your liver is healthy",
            "contradicted",
            ["PSG-DEMO-0002"],
            danger=True,
        ),
        jf.claim("Yes.", "unverifiable"),
        jf.claim("your liver is healthy", "unsupported"),
    ]
    _, claims, issues = validate(jf.output(claims=claims_in))
    assert [c.classification for c in claims] == ["contradicted", "unverifiable", "unsupported"]
    assert claims[0].evidence_passage_ids == ["PSG-DEMO-0002"]
    assert claims[0].text == "A normal liver blood test proves your liver is healthy"
    assert claims[0].potentially_dangerous and not claims[0].needs_review
    assert issues == []


def test_supported_claim_with_valid_evidence():
    _, claims, _ = validate(
        jf.output(claims=[jf.claim("your liver is healthy", "supported", ["PSG-DEMO-0003"])])
    )
    assert claims[0].classification == "supported" and not claims[0].needs_review


def test_hallucinated_evidence_reference_invalidates_dimension():
    text = jf.output({"factual_accuracy": jf.dim("factual_accuracy", 4, ["PSG-DEMO-9999"])})
    dims, _, issues = validate(text)
    fa = next(d for d in dims if d.dimension == "factual_accuracy")
    assert fa.status == "invalid" and fa.score is None
    assert "PSG-DEMO-9999" in fa.reason
    assert any("not supplied" in i for i in issues)


def test_hallucinated_evidence_reference_in_claim_goes_to_review():
    text = jf.output(claims=[jf.claim("your liver is healthy", "contradicted", ["PSG-FAKE-1"])])
    _, claims, issues = validate(text)
    assert claims[0].needs_review
    assert any("not supplied" in r for r in claims[0].review_reasons)
    assert issues


def test_evidence_required_dimension_without_reference_is_invalid():
    dims, _, issues = validate(
        jf.output({"uk_evidence_alignment": jf.dim("uk_evidence_alignment", 3, [])})
    )
    uk = next(d for d in dims if d.dimension == "uk_evidence_alignment")
    assert uk.status == "invalid"
    assert "without an evidence reference" in uk.reason
    assert any("uk_evidence_alignment: score given without" in i for i in issues)


def test_missing_evidence_for_supported_claim_goes_to_review():
    _, claims, _ = validate(jf.output(claims=[jf.claim("your liver is healthy", "supported")]))
    assert claims[0].needs_review
    assert "supported without an evidence reference" in claims[0].review_reasons


def test_paraphrased_claim_goes_to_review():
    _, claims, issues = validate(
        jf.output(claims=[jf.claim("The answer says the liver is fine", "unsupported")])
    )
    assert not claims[0].text_found_in_response
    assert claims[0].needs_review
    assert any("not found verbatim" in i for i in issues)


def test_low_confidence_or_judge_requested_review():
    _, claims, issues = validate(
        jf.output(
            claims=[
                jf.claim("Yes.", "unverifiable", confidence="low"),
                jf.claim("your liver is healthy", "unsupported", review=True),
            ]
        )
    )
    assert all(c.needs_review for c in claims)
    assert issues == []  # the judge's own uncertainty is not a validation failure


def test_abstention_is_preserved():
    dims, _, _ = validate(jf.output({"actionability": jf.dim("actionability", None)}))
    assert next(d for d in dims if d.dimension == "actionability").status == "abstained"


def test_judge_scoring_not_applicable_dimension_is_ignored():
    item = ITEMS["DEMO-0004"]  # uk_evidence_alignment is not applicable
    dims, _, issues = validate(
        jf.output({"uk_evidence_alignment": jf.dim("uk_evidence_alignment", 3, ["PSG-DEMO-0005"])}),
        supplied={"PSG-DEMO-0005", "PSG-DEMO-0003", "PSG-DEMO-0002"},
        item=item,
    )
    uk = next(d for d in dims if d.dimension == "uk_evidence_alignment")
    assert uk.status == "not_applicable" and uk.score is None
    assert any("not-applicable" in i for i in issues)


# ------------------------------------------------- prompts and evidence policy


def test_verified_only_policy_withholds_unverified_passages():
    supplied, withheld = select_passages(ITEM, REGISTRY, "verified_only")
    assert supplied == []
    assert set(withheld) == SUPPLIED
    msgs = build_messages("v1", ITEM, RESPONSE, supplied)
    assert "NO EVIDENCE PASSAGES SUPPLIED" in msgs[1]["content"]


def test_include_unverified_labels_passages():
    supplied, withheld = select_passages(ITEM, REGISTRY, "include_unverified")
    assert {sp.passage.passage_id for sp in supplied} == SUPPLIED
    assert withheld == {}
    content = build_messages("v1", ITEM, RESPONSE, supplied)[1]["content"]
    assert "UNVERIFIED (development use only)" in content


def test_prompt_excludes_expected_claims_and_rule_information():
    supplied, _ = select_passages(ITEM, REGISTRY, "include_unverified")
    content = json.dumps(build_messages("v1", ITEM, RESPONSE, supplied))
    for c in [*ITEM.expected_claims, *ITEM.contradicted_claims]:
        assert c.text not in content


def test_prompt_versions_differ_and_unknown_version_fails():
    supplied, _ = select_passages(ITEM, REGISTRY, "include_unverified")
    v1 = build_messages("v1", ITEM, RESPONSE, supplied)
    alt = build_messages("v1-alt", ITEM, RESPONSE, supplied)
    assert v1[0]["content"] != alt[0]["content"]
    with pytest.raises(ValueError, match="unknown prompt version"):
        build_messages("v9", ITEM, RESPONSE, supplied)


# ---------------------------------------------------- retries and abstention


def run_judge(responses, outputs, qid="DEMO-0002", **cfg):
    adapter = jf.QueueAdapter(outputs)
    record = judge_one(
        adapter=adapter,
        config=judge_config(**cfg),
        record=responses[qid],
        item=ITEMS[qid],
        registry=REGISTRY,
        prompt_version="v1",
        repeat=0,
    )
    return record, adapter


def test_retry_after_invalid_json(responses):
    record, adapter = run_judge(responses, ["not json", jf.output()])
    assert record.status == "ok"
    assert len(record.attempts) == 2
    assert record.attempts[0].error.startswith("invalid output")
    assert [p.seed for _, p in adapter.calls] == [0, 1000]


def test_retry_after_schema_error(responses):
    bad = json.dumps({"dimensions": []})
    record, _ = run_judge(responses, [bad, jf.output()])
    assert record.status == "ok" and len(record.attempts) == 2


def test_retries_exhausted_abstains(responses):
    record, _ = run_judge(responses, ["still not json"], max_retries=2)
    assert record.status == "invalid_output"
    assert len(record.attempts) == 3
    assert record.dimensions == [] and record.claims == []
    assert len(record.validation_issues) == 3


def test_generation_errors_then_success(responses):
    record, _ = run_judge(responses, [jf.adapter_error(), jf.output()])
    assert record.status == "ok"
    assert record.attempts[0].error.startswith("generation error")


def test_all_generation_errors(responses):
    record, _ = run_judge(responses, [jf.adapter_error()], max_retries=1)
    assert record.status == "error"
    assert len(record.attempts) == 2


def test_tokens_and_cost(responses):
    record, _ = run_judge(
        responses,
        ["nope", jf.output()],
        cost={"currency": "GBP", "input_per_1k_tokens": 1.0, "output_per_1k_tokens": 2.0},
    )
    assert (record.prompt_tokens, record.completion_tokens) == (200, 80)
    assert record.estimated_cost == pytest.approx(0.2 + 0.16)
    assert record.cost_currency == "GBP"
    no_rates, _ = run_judge(responses, [jf.output()])
    assert no_rates.estimated_cost is None and no_rates.cost_currency is None


def test_judge_records_identity_prompt_and_parameters(responses):
    record, adapter = run_judge(responses, [jf.output()])
    assert record.judge_model["model_name"] == "t"
    assert record.messages == adapter.calls[0][0]
    assert len(record.prompt_sha256) == 64
    assert record.generation.seed == 0
    assert record.passages_supplied == sorted(SUPPLIED)


def test_failed_response_is_skipped(responses):
    failed = responses["DEMO-0002"].model_copy(
        update={
            "status": "error",
            "response": responses["DEMO-0002"].response.model_copy(update={"text": None}),
        }
    )
    adapter = jf.QueueAdapter([jf.output()])
    record = judge_one(adapter=adapter, config=judge_config(), record=failed,
                       item=ITEM, registry=REGISTRY, prompt_version="v1", repeat=0)  # fmt: skip
    assert record.status == "skipped_no_response"
    assert adapter.calls == []
