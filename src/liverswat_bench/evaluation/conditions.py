"""Evidence conditions for the evidence experiment.

* ``baseline`` (Condition A): the model receives the question only.
* ``retrieved`` (Condition B): the model receives passages chosen by the
  lexical retriever (:mod:`liverswat_bench.evidence.retrieval`).
* ``oracle`` (Condition C): the model receives the item's own cited passages.

All conditions use the same model configuration and generation settings. Only
the user message changes. The evidence wording is versioned.
"""

from __future__ import annotations

from enum import StrEnum

from liverswat_bench.datasets.schema import BenchmarkItem
from liverswat_bench.evaluation.records import EvidenceSupplied
from liverswat_bench.evidence.registry import EvidenceRegistry
from liverswat_bench.evidence.retrieval import RETRIEVER_ID, LexicalRetriever
from liverswat_bench.evidence.schema import SourceStatus
from liverswat_bench.models.config import ModelConfig

EVIDENCE_PROMPT_VERSION = "evidence-v1"
EVIDENCE_INSTRUCTION = (
    "Use the UK health information below when you answer the question. "
    "If the information does not cover the question, say so."
)


class EvidenceCondition(StrEnum):
    BASELINE = "baseline"
    RETRIEVED = "retrieved"
    ORACLE = "oracle"


def _verified(registry: EvidenceRegistry, pid: str) -> bool:
    p = registry.passages[pid]
    s = registry.sources.get(p.source_id)
    return (
        p.status == SourceStatus.VERIFIED
        and s is not None
        and (s.source_status == SourceStatus.VERIFIED)
    )


def build_condition_messages(
    config: ModelConfig,
    item: BenchmarkItem,
    condition: EvidenceCondition,
    registry: EvidenceRegistry,
    retriever: LexicalRetriever | None = None,
    top_k: int = 3,
) -> tuple[list[dict[str, str]], EvidenceSupplied]:
    oracle_ids = [
        pid
        for pid in item.evidence_passage_ids
        if pid in registry.passages and registry.passages[pid].text
    ]
    if condition == EvidenceCondition.BASELINE:
        return config.build_messages(item.question), EvidenceSupplied(
            condition="baseline", oracle_passage_ids=oracle_ids
        )

    scores: dict[str, float] = {}
    if condition == EvidenceCondition.ORACLE:
        ids = oracle_ids
    else:
        if retriever is None:
            raise ValueError("the retrieved condition needs a retriever")
        hits = retriever.search(item.question, top_k)
        ids = [h.passage_id for h in hits]
        scores = {h.passage_id: h.score for h in hits}

    blocks = [f"[{n}] {registry.passages[pid].text}" for n, pid in enumerate(ids, start=1)]
    information = "\n".join(blocks) if blocks else "(No information was found.)"
    content = (
        f"{EVIDENCE_INSTRUCTION}\n\nInformation:\n{information}\n\n"
        f"Question:\n{config.render_prompt(item.question)}"
    )
    messages = []
    if config.system_prompt:
        messages.append({"role": "system", "content": config.system_prompt})
    messages.append({"role": "user", "content": content})

    retrieved = condition == EvidenceCondition.RETRIEVED
    recall = None
    if retrieved and oracle_ids:
        recall = round(len(set(ids) & set(oracle_ids)) / len(oracle_ids), 4)
    return messages, EvidenceSupplied(
        condition=condition.value,
        evidence_prompt_version=EVIDENCE_PROMPT_VERSION,
        passage_ids=ids,
        passages_verified=[pid for pid in ids if _verified(registry, pid)],
        retriever=RETRIEVER_ID if retrieved else None,
        retrieval_scores=scores,
        corpus_size=len(retriever.passages) if retrieved else None,
        corpus_sha256=retriever.corpus_sha256 if retrieved else None,
        oracle_passage_ids=oracle_ids,
        oracle_recall=recall,
    )
