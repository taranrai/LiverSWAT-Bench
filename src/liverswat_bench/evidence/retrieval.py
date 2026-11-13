"""A deterministic lexical retriever over the local evidence registry.

This is a simple TF-IDF (term frequency-inverse document frequency) retriever
with cosine similarity. It is a real retrieval component, but it is not a
semantic or production retrieval system. Its corpus is the passages stored in
the registry, so retrieval quality is limited by the size of that corpus.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass

from liverswat_bench.evidence.registry import EvidenceRegistry
from liverswat_bench.evidence.schema import EvidencePassage

RETRIEVER_ID = "lexical-tfidf-v1"

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "its",
        "my",
        "of",
        "on",
        "or",
        "should",
        "so",
        "that",
        "the",
        "their",
        "there",
        "this",
        "to",
        "was",
        "what",
        "when",
        "where",
        "which",
        "who",
        "will",
        "with",
        "you",
        "your",
        "me",
        "we",
        "they",
        "them",
        "our",
        "been",
        "being",
        "any",
        "all",
        "about",
        "into",
        "than",
        "then",
        "also",
        "just",
    }
)
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenise(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


@dataclass(frozen=True)
class Retrieved:
    passage_id: str
    score: float


class LexicalRetriever:
    def __init__(self, passages: list[EvidencePassage]) -> None:
        self.passages = sorted((p for p in passages if p.text), key=lambda p: p.passage_id)
        docs = [Counter(tokenise(p.text)) for p in self.passages]
        n = len(docs)
        df = Counter(term for doc in docs for term in doc)
        self.idf = {t: math.log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}
        self.vectors = [self._weigh(doc) for doc in docs]
        digest = hashlib.sha256()
        for p in self.passages:
            digest.update(f"{p.passage_id}\x00{p.text}\x00".encode())
        self.corpus_sha256 = digest.hexdigest()

    @classmethod
    def from_registry(cls, registry: EvidenceRegistry, synthetic: bool) -> LexicalRetriever:
        return cls([p for p in registry.passages.values() if p.synthetic == synthetic])

    def _weigh(self, counts: Counter) -> dict[str, float]:
        vec = {t: c * self.idf.get(t, 0.0) for t, c in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values()))
        return {t: v / norm for t, v in vec.items()} if norm else {}

    def search(self, query: str, top_k: int = 3) -> list[Retrieved]:
        q = self._weigh(Counter(tokenise(query)))
        scored = [
            Retrieved(p.passage_id, round(sum(w * vec.get(t, 0.0) for t, w in q.items()), 6))
            for p, vec in zip(self.passages, self.vectors, strict=True)
        ]
        scored = [r for r in scored if r.score > 0]
        scored.sort(key=lambda r: (-r.score, r.passage_id))
        return scored[:top_k]
