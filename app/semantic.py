from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from typing import Any, Protocol, Sequence


POLICY_ID = "company-travel-reimbursement"
POLICY_VERSION = "1.0.0"


class SemanticRetrieverUnavailableError(RuntimeError):
    pass


class SemanticEmbedder(Protocol):
    model_id: str
    dimension: int
    model_revision: str | None

    def embed_query(self, text: str) -> Sequence[float]: ...
    def embed_documents(self, texts: list[str]) -> Sequence[Sequence[float]]: ...


@dataclass(frozen=True)
class SemanticEmbeddingConfig:
    model_id: str
    expected_dimension: int
    model_revision: str | None = None
    query_prefix: str = ""
    document_prefix: str = ""
    normalize_embeddings: bool = True
    similarity_threshold: float | None = None


BGE_CONFIG = SemanticEmbeddingConfig(
    model_id="BAAI/bge-small-zh-v1.5",
    expected_dimension=512,
    model_revision="7999e1d3359715c523056ef9478215996d62a620",
    query_prefix="为这个句子生成表示以用于检索相关文章：",
)
E5_CONFIG = SemanticEmbeddingConfig(
    model_id="intfloat/multilingual-e5-small",
    expected_dimension=384,
    model_revision="614241f622f53c4eeff9890bdc4f31cfecc418b3",
    query_prefix="query: ",
    document_prefix="passage: ",
)


class SentenceTransformerEmbedder:
    def __init__(self, config: SemanticEmbeddingConfig, device: str = "cpu"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise SemanticRetrieverUnavailableError(
                "semantic retrieval dependencies are not installed; "
                "install requirements-semantic.txt"
            ) from exc
        start = time.perf_counter()
        self.config = config
        self.model_id = config.model_id
        self.model = SentenceTransformer(config.model_id, device=device,
                                         revision=config.model_revision)
        self.model_load_ms = (time.perf_counter() - start) * 1000
        self.dimension = self.model.get_embedding_dimension()
        if self.dimension != config.expected_dimension:
            raise ValueError(f"Unexpected dimension {self.dimension} for {config.model_id}")
        self.model_revision = config.model_revision

    def _encode(self, texts: list[str]):
        return self.model.encode(
            texts,
            normalize_embeddings=self.config.normalize_embeddings,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

    def embed_query(self, text: str):
        return self._encode([self.config.query_prefix + text])[0]

    def embed_documents(self, texts: list[str]):
        return self._encode([self.config.document_prefix + text for text in texts])


@dataclass
class SemanticIndex:
    model_id: str
    model_revision: str | None
    dimension: int
    policy_id: str
    policy_version: str
    corpus_sha256: str
    rule_ids: list[str]
    vectors: Any
    index_build_ms: float

    @property
    def cache_identity(self) -> str:
        payload = (
            f"{self.model_id}|{self.model_revision}|{self.dimension}|"
            f"{self.policy_id}|{self.policy_version}|{self.corpus_sha256}"
        )
        return hashlib.sha256(payload.encode()).hexdigest()


def corpus_sha256(chunks: Sequence[object]) -> str:
    payload = [{"rule_id": c.rule_id, "title": c.section_title, "text": c.text} for c in chunks]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_semantic_index(embedder: SemanticEmbedder, chunks: Sequence[object]) -> SemanticIndex:
    start = time.perf_counter()
    texts = [f"{c.rule_id} {c.section_title}\n{c.text}" for c in chunks]
    vectors = embedder.embed_documents(texts)
    elapsed = (time.perf_counter() - start) * 1000
    return SemanticIndex(
        model_id=embedder.model_id,
        model_revision=embedder.model_revision,
        dimension=embedder.dimension,
        policy_id=POLICY_ID,
        policy_version=POLICY_VERSION,
        corpus_sha256=corpus_sha256(chunks),
        rule_ids=[c.rule_id for c in chunks],
        vectors=vectors,
        index_build_ms=elapsed,
    )


def normalized_dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
