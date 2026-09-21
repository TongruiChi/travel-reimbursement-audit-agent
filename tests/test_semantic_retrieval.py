import builtins
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.rag import (
    BM25RetrieverV1,
    HybridRetrieverV2,
    RetrievalResult,
    SemanticPolicyRetriever,
    _chunks,
    get_retriever,
)
from app.semantic import (
    BGE_CONFIG,
    E5_CONFIG,
    SemanticRetrieverUnavailableError,
    SentenceTransformerEmbedder,
    build_semantic_index,
)


class FakeSemanticEmbedder:
    model_id = "fake/model"
    model_revision = "test"
    dimension = 2

    def embed_query(self, text):
        return [1.0, 0.0]

    def embed_documents(self, texts):
        return [[1.0, 0.0] if index == 0 else [0.0, 1.0] for index, _ in enumerate(texts)]


def test_model_specific_formatting_contracts():
    assert BGE_CONFIG.query_prefix.startswith("为这个句子生成表示")
    assert BGE_CONFIG.document_prefix == ""
    assert E5_CONFIG.query_prefix == "query: "
    assert E5_CONFIG.document_prefix == "passage: "


def test_semantic_index_identity_and_ranking_are_stable():
    chunks = _chunks(__import__("app.policy", fromlist=["policy_registry"]).policy_registry)[:2]
    retriever = SemanticPolicyRetriever(FakeSemanticEmbedder(), "candidate", chunks)
    assert retriever.index.dimension == 2
    assert retriever.index.policy_id == "company-travel-reimbursement"
    assert retriever.index.policy_version == "1.0.0"
    assert len(retriever.index.cache_identity) == 64
    assert math.isclose(math.sqrt(sum(x * x for x in retriever.index.vectors[0])), 1.0)
    results = retriever.search("anything", 2)
    assert results[0].rule_id == chunks[0].rule_id
    assert results[0].score == 1.0
    assert results[0].metadata["semantic_embedding"] is True


@pytest.mark.parametrize(
    ("config", "expected_query", "expected_document"),
    [
        (BGE_CONFIG, BGE_CONFIG.query_prefix + "问题", "政策正文"),
        (E5_CONFIG, "query: 问题", "passage: 政策正文"),
    ],
)
def test_sentence_transformer_adapter_applies_model_format_and_normalization(
    monkeypatch, config, expected_query, expected_document
):
    calls = []

    class Encoded(list):
        pass

    class FakeModel:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_embedding_dimension(self):
            return config.expected_dimension

        def encode(self, texts, **kwargs):
            calls.append((texts, kwargs))
            return Encoded([[1.0] + [0.0] * (config.expected_dimension - 1)
                            for _ in texts])

    monkeypatch.setitem(sys.modules, "sentence_transformers",
                        SimpleNamespace(SentenceTransformer=FakeModel))
    embedder = SentenceTransformerEmbedder(config)
    embedder.embed_query("问题")
    embedder.embed_documents(["政策正文"])
    assert calls[0][0] == [expected_query]
    assert calls[1][0] == [expected_document]
    assert all(call[1]["normalize_embeddings"] is True for call in calls)


def test_missing_sentence_transformers_has_clear_error(monkeypatch):
    original_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ImportError("blocked for test")
        return original_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "sentence_transformers", raising=False)
    monkeypatch.setattr(builtins, "__import__", blocked_import)
    with pytest.raises(SemanticRetrieverUnavailableError, match="requirements-semantic"):
        SentenceTransformerEmbedder(E5_CONFIG)


def test_hybrid_v2_uses_same_rrf_k_and_combines_component_ranks():
    chunks = _chunks(__import__("app.policy", fromlist=["policy_registry"]).policy_registry)[:2]

    class FixedRetriever:
        def __init__(self, ordered):
            self.ordered = ordered

        def search(self, _query, _top_k=5):
            return [BM25RetrieverV1._copy(chunks[index], 1.0, rank)
                    for rank, index in enumerate(self.ordered, 1)]

    hybrid = HybridRetrieverV2(FixedRetriever([0, 1]), FixedRetriever([1, 0]))
    results = hybrid.search("anything", 2)
    assert hybrid.rrf_k == 60
    assert results[0].score == pytest.approx(1 / 61 + 1 / 62)
    assert results[0].metadata["component_ranks"] == {
        "bm25_rank": 1, "embedding_rank": 2,
    }


def test_legacy_retrievers_do_not_load_optional_semantic_runtime(monkeypatch):
    monkeypatch.setattr("app.rag.load_selected_semantic_retrievers",
                        lambda: (_ for _ in ()).throw(AssertionError("must not load")))
    assert get_retriever("keyword-v1").retriever_id == "keyword-v1"
    assert get_retriever("bm25-v1").retriever_id == "bm25-v1"


def test_semantic_threshold_can_return_no_result():
    chunks = _chunks(__import__("app.policy", fromlist=["policy_registry"]).policy_registry)[:2]
    retriever = SemanticPolicyRetriever(FakeSemanticEmbedder(), "candidate", chunks, 1.1)
    assert retriever.search("anything") == []


def test_api_reports_unavailable_semantic_runtime(client, monkeypatch):
    def unavailable(_retriever_id):
        raise SemanticRetrieverUnavailableError("semantic retrieval is unavailable")

    monkeypatch.setattr("app.main.get_retriever", unavailable)
    response = client.get("/knowledge/search", params={"q": "酒店", "retriever": "embedding-v2"})
    assert response.status_code == 503
    assert "semantic retrieval" in response.json()["detail"]


def test_versioned_semantic_baseline_preserves_regressions_and_selection():
    baseline_path = Path(__file__).resolve().parents[1] / "evals/baselines/semantic-retrieval-pilot-v1.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert baseline["baseline_schema_version"] == "semantic-retrieval-baseline.v1"
    assert baseline["selected_model"]["model_id"] == E5_CONFIG.model_id
    assert baseline["negative_behavior"]["threshold_tuning_performed"] is False
    assert baseline["negative_behavior"]["embedding_v2_negative_accuracy"] == 0.0
    assert baseline["negative_behavior"]["hybrid_v2_negative_accuracy"] == 0.0
    assert baseline["hybrid_v1_vs_v2_delta"]["hybrid_v1_set_recall_at_3"] == 100.0
    assert baseline["hybrid_v1_vs_v2_delta"]["hybrid_v2_set_recall_at_3"] == 95.45
    assert baseline["retrievers"]["hybrid-v2"]["selected_as_default"] is False
