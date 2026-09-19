import math
import os

import pytest

from app.rag import SemanticPolicyRetriever
from app.semantic import BGE_CONFIG, E5_CONFIG, SentenceTransformerEmbedder


pytestmark = [
    pytest.mark.semantic_model,
    pytest.mark.skipif(
        os.getenv("RUN_SEMANTIC_MODEL_TESTS") != "1",
        reason="set RUN_SEMANTIC_MODEL_TESTS=1 to load pretrained models",
    ),
]


@pytest.mark.parametrize("config", [BGE_CONFIG, E5_CONFIG])
def test_real_model_loads_and_indexes_policy_registry(config):
    embedder = SentenceTransformerEmbedder(config, device="cpu")
    retriever = SemanticPolicyRetriever(embedder, "integration-candidate")
    vector = embedder.embed_query("北京出差住宿费标准")
    assert len(vector) == config.expected_dimension
    assert all(math.isfinite(float(value)) for value in vector)
    assert math.sqrt(sum(float(value) ** 2 for value in vector)) == pytest.approx(1.0, abs=1e-5)
    assert len(retriever.index.rule_ids) == 10
    assert len(retriever.search("北京出差住宿费标准", 3)) == 3
