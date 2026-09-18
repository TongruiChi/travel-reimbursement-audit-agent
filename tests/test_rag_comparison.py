import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from compare_rag_retrievers import classify_query


def result(hit, complete, negative=None):
    return {"hit_at_3": hit, "set_recall_at_3": 1.0 if complete else 0.5,
            "negative_success": negative}


def row(relevant, keyword, bm25, embedding, hybrid):
    return {"relevant_rule_ids": relevant, "keyword-v1": keyword,
            "bm25-v1": bm25, "embedding-v1": embedding, "hybrid-v1": hybrid}


def test_classifies_fixed_by_retriever():
    tags = classify_query(row(["A"], result(False, False), result(True, True), result(True, True), result(True, True)))
    assert {"fixed_by_bm25", "fixed_by_embedding", "fixed_by_hybrid"} <= set(tags)


def test_classifies_completed_multi_rule_without_calling_it_fixed():
    tags = classify_query(row(["A", "B"], result(True, False), result(True, True), result(True, True), result(True, True)))
    assert "multi_rule_partial" in tags
    assert {"completed_by_bm25", "completed_by_embedding", "completed_by_hybrid"} <= set(tags)
    assert "fixed_by_bm25" not in tags


def test_classifies_regression_and_set_recall_regression():
    tags = classify_query(row(["A", "B"], result(True, True), result(False, False), result(True, False), result(True, True)))
    assert "bm25_regression" in tags
    assert "embedding_set_recall_regression" in tags


def test_classifies_all_failed_and_negative_cases():
    positive = row(["A"], result(False, False), result(False, False), result(False, False), result(False, False))
    assert "still_failed" in classify_query(positive)
    negative = row([], result(False, False, True), result(False, False, True), result(False, False, False), result(False, False, True))
    tags = classify_query(negative)
    assert "negative_correct" not in tags
    assert "embedding_negative_regression" in tags
