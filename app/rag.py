from __future__ import annotations

import math
import re
import hashlib
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.policy import PolicyRegistry, PolicyRule, policy_registry


class Tokenizer(Protocol):
    def tokenize(self, text: str) -> list[str]: ...


class SimpleChineseTokenizer:
    """Offline tokenizer supporting identifiers, words, CJK characters and bigrams."""
    _pattern = re.compile(r"[A-Za-z0-9_-]+|[\u4e00-\u9fff]")

    def tokenize(self, text: str) -> list[str]:
        tokens = [x.lower() for x in self._pattern.findall(text)]
        cjk = [x for x in tokens if len(x) == 1 and "\u4e00" <= x <= "\u9fff"]
        return tokens + [cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1)]


@dataclass
class RetrievalResult:
    chunk_id: str
    document_id: str
    score: float
    rank: int
    text: str
    source_name: str = "policy-registry"
    section_title: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    rule_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    def __getitem__(self, key):
        if key == "rule":
            return {"rule_id": self.rule_id, "title": self.section_title, "content": self.text}
        return getattr(self, key)


class Retriever(Protocol):
    retriever_id: str
    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]: ...


def _chunks(registry: PolicyRegistry) -> list[RetrievalResult]:
    result = []
    for rule in registry.rules:
        text = rule.description + (f"\n关键词：{' '.join(rule.keywords)}" if rule.keywords else "")
        result.append(RetrievalResult(rule.rule_id, rule.rule_id, 0.0, 0, text,
            section_title=rule.title, metadata={"kind": "policy_rule"}, rule_id=rule.rule_id))
    return result


class KeywordRetrieverV1:
    retriever_id = "keyword-v1"
    def __init__(self, registry: PolicyRegistry = policy_registry):
        self.registry = registry
        self.rule_chunks = _chunks(registry)

    def search(self, query: str, top_k: int = 5) -> list[RetrievalResult]:
        keywords = [x.strip().lower() for x in query.split() if x.strip()]
        scored = []
        for chunk in self.rule_chunks:
            searchable = f"{chunk.rule_id} {chunk.section_title}\n{chunk.text}".lower()
            score = sum(searchable.count(k) for k in keywords)
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._result(c, float(score), rank) for rank, (score, c) in enumerate(scored[:top_k], 1)]

    @staticmethod
    def _result(c, score, rank):
        return RetrievalResult(c.chunk_id, c.document_id, score, rank, c.text,
            c.source_name, c.section_title, c.page_start, c.page_end,
            {**c.metadata, "legacy": True}, c.rule_id)


class BM25RetrieverV1:
    retriever_id = "bm25-v1"
    def __init__(self, chunks=None, tokenizer: Tokenizer | None = None):
        self.chunks = chunks or _chunks(policy_registry)
        self.tokenizer = tokenizer or SimpleChineseTokenizer()
        self.docs = [self.tokenizer.tokenize(c.text + " " + (c.section_title or "") + " " + c.chunk_id) for c in self.chunks]
        self.df = {}
        for doc in self.docs:
            for token in set(doc): self.df[token] = self.df.get(token, 0) + 1
        self.avgdl = sum(map(len, self.docs)) / max(1, len(self.docs))

    def search(self, query, top_k=5):
        q, n = self.tokenizer.tokenize(query), len(self.docs); scored = []
        for index, doc in enumerate(self.docs):
            counts = {t: doc.count(t) for t in set(doc)}; score = 0.0
            for token in q:
                if token not in counts: continue
                df = self.df[token]
                idf = math.log(1 + (n - df + .5) / (df + .5))
                score += idf * counts[token] * 2.2 / (counts[token] + 1.2 * (.25 + .75 * len(doc) / self.avgdl))
            if score > 0: scored.append((score, index))
        scored.sort(key=lambda x: (-x[0], self.chunks[x[1]].chunk_id))
        return [self._copy(self.chunks[i], score, rank) for rank, (score, i) in enumerate(scored[:top_k], 1)]

    @staticmethod
    def _copy(c, score, rank):
        return RetrievalResult(c.chunk_id, c.document_id, score, rank, c.text, c.source_name, c.section_title, c.page_start, c.page_end, dict(c.metadata), c.rule_id)


class EmbeddingRetrieverV1:
    retriever_id = "embedding-v1"
    def __init__(self, chunks=None, dimensions=512):
        self.chunks = chunks or _chunks(policy_registry); self.dimensions = dimensions
        self.embeddings = [self._embed(c.text + " " + (c.section_title or "") + " " + c.chunk_id) for c in self.chunks]

    def _embed(self, text):
        vector = [0.0] * self.dimensions
        for token in SimpleChineseTokenizer().tokenize(text):
            index = int.from_bytes(hashlib.sha256(token.encode()).digest()[:8], "big") % self.dimensions
            vector[index] += 1
        norm = math.sqrt(sum(x * x for x in vector)) or 1
        return [x / norm for x in vector]

    def search(self, query, top_k=5):
        q = self._embed(query); scored = [(sum(a*b for a,b in zip(q, v)), i) for i,v in enumerate(self.embeddings)]
        # Hash vectors always have a nearest neighbour.  This conservative
        # floor prevents unrelated queries from becoming false evidence.
        scored = [(s, i) for s, i in scored if s >= 0.08]; scored.sort(key=lambda x: (-x[0], self.chunks[x[1]].chunk_id))
        return [BM25RetrieverV1._copy(self.chunks[i], score, rank) for rank, (score, i) in enumerate(scored[:top_k], 1)]


class HybridRetrieverV1:
    retriever_id = "hybrid-v1"
    def __init__(self, bm25=None, embedding=None, rrf_k=60):
        self.bm25 = bm25 or BM25RetrieverV1(); self.embedding = embedding or EmbeddingRetrieverV1(self.bm25.chunks); self.rrf_k = rrf_k

    def search(self, query, top_k=5):
        rankings = [self.bm25.search(query, max(20, top_k)), self.embedding.search(query, max(20, top_k))]
        if not rankings[0] and not rankings[1]:
            return []
        by_id = {x.chunk_id: x for results in rankings for x in results}; scores = {}
        for results in rankings:
            for item in results: scores[item.chunk_id] = scores.get(item.chunk_id, 0) + 1 / (self.rrf_k + item.rank)
        ordered = sorted(by_id, key=lambda x: (-scores[x], x))
        return [RetrievalResult(by_id[i].chunk_id, by_id[i].document_id, scores[i], rank, by_id[i].text,
            by_id[i].source_name, by_id[i].section_title, by_id[i].page_start, by_id[i].page_end,
            {**by_id[i].metadata, "component_ranks": {"bm25_rank": next((x.rank for x in rankings[0] if x.chunk_id == i), None), "embedding_rank": next((x.rank for x in rankings[1] if x.chunk_id == i), None)}}, by_id[i].rule_id) for rank, i in enumerate(ordered[:top_k], 1)]


rule_rag = KeywordRetrieverV1()
RETRIEVERS = {"keyword-v1": rule_rag, "bm25-v1": BM25RetrieverV1(), "embedding-v1": EmbeddingRetrieverV1(), "hybrid-v1": HybridRetrieverV1()}

def get_retriever(retriever_id="keyword-v1"):
    if retriever_id not in RETRIEVERS: raise ValueError(f"Unknown retriever: {retriever_id}")
    return RETRIEVERS[retriever_id]
