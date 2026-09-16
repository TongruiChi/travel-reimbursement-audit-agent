import pytest

from evals.metrics import (
    FINAL_STATES,
    RULE_STATES,
    appropriate_abstention_rate,
    automation_coverage,
    categorical_metrics,
    determinate_accuracy,
    exact_match_metrics,
    mean_reciprocal_rank,
    negative_no_result_accuracy,
    recall_at_k,
    set_recall_at_k,
    violation_metrics,
)


def test_violation_metrics_count_tp_fp_and_fn():
    expected = ["VIOLATION", "PASS", "INDETERMINATE", "VIOLATION"]
    actual = ["VIOLATION", "VIOLATION", "PASS", "PASS"]

    result = violation_metrics(expected, actual)

    assert result["tp"] == 1
    assert result["fp"] == 1
    assert result["fn"] == 1
    assert result["tn"] == 1
    assert result["total_rule_units"] == 4
    assert result["expected_violation_support"] == 2
    assert result["predicted_violation_support"] == 2
    assert result["precision"] == pytest.approx(0.5)
    assert result["recall"] == pytest.approx(0.5)
    assert result["f1"] == pytest.approx(0.5)


def test_violation_metric_zero_denominators_are_not_fabricated():
    no_positive = violation_metrics(["PASS", "INDETERMINATE"], ["PASS", "PASS"])
    missed_positive = violation_metrics(["VIOLATION"], ["PASS"])

    assert no_positive["precision"] is None
    assert no_positive["recall"] is None
    assert no_positive["f1"] is None
    assert missed_positive["precision"] is None
    assert missed_positive["recall"] == 0.0
    assert missed_positive["f1"] is None


def test_four_state_confusion_matrix_and_support():
    expected = ["PASS", "VIOLATION", "INDETERMINATE", "NOT_APPLICABLE"]
    actual = ["PASS", "PASS", "VIOLATION", "NOT_APPLICABLE"]

    result = categorical_metrics(expected, actual, RULE_STATES)

    assert result["support"] == 4
    assert result["correct"] == 2
    assert result["accuracy"] == pytest.approx(0.5)
    assert result["confusion_matrix"]["PASS"]["PASS"] == 1
    assert result["confusion_matrix"]["VIOLATION"]["PASS"] == 1
    assert result["confusion_matrix"]["INDETERMINATE"]["VIOLATION"] == 1
    assert result["confusion_matrix"]["NOT_APPLICABLE"]["NOT_APPLICABLE"] == 1
    assert all(
        set(row) == set(RULE_STATES)
        for row in result["confusion_matrix"].values()
    )


def test_final_status_class_without_support_is_na():
    result = categorical_metrics(
        ["NEEDS_REVIEW", "REJECTED"],
        ["NEEDS_REVIEW", "REJECTED"],
        FINAL_STATES,
    )

    assert result["per_class"]["APPROVED"]["support"] == 0
    assert result["per_class"]["APPROVED"]["accuracy"] is None
    assert result["accuracy"] == 1.0


def test_exact_match_rate_handles_true_false_and_empty_inputs():
    assert exact_match_metrics([True, False, True]) == {
        "support": 3,
        "match_count": 2,
        "rate": pytest.approx(2 / 3),
    }
    assert exact_match_metrics([]) == {
        "support": 0,
        "match_count": 0,
        "rate": None,
    }


def test_coverage_determinate_accuracy_and_abstention_use_correct_denominators():
    expected = ["PASS", "VIOLATION", "INDETERMINATE", "NOT_APPLICABLE"]
    actual = ["PASS", "INDETERMINATE", "PASS", "VIOLATION"]

    coverage = automation_coverage(expected, actual)
    determinate = determinate_accuracy(expected, actual)
    abstention = appropriate_abstention_rate(expected, actual)

    assert coverage == {
        "applicable_support": 3,
        "automated_count": 2,
        "rate": pytest.approx(2 / 3),
    }
    assert determinate == {
        "determinate_support": 2,
        "correct": 1,
        "accuracy": pytest.approx(0.5),
    }
    assert abstention == {
        "expected_indeterminate_support": 1,
        "correct_abstentions": 0,
        "rate": 0.0,
    }


def test_expected_indeterminate_actual_determinate_is_incorrect():
    result = determinate_accuracy(["INDETERMINATE"], ["PASS"])

    assert result["determinate_support"] == 1
    assert result["correct"] == 0
    assert result["accuracy"] == 0.0


def test_recall_set_recall_and_mrr_support_multi_relevant_queries():
    relevant = [["A"], ["B", "C"], []]
    retrieved = [["X", "A"], ["C", "X"], []]

    recall_1 = recall_at_k(relevant, retrieved, 1)
    recall_3 = recall_at_k(relevant, retrieved, 3)
    set_recall_3 = set_recall_at_k(relevant, retrieved, 3)
    mrr = mean_reciprocal_rank(relevant, retrieved)

    assert recall_1["positive_query_support"] == 2
    assert recall_1["rate"] == pytest.approx(0.5)
    assert recall_3["rate"] == 1.0
    assert set_recall_3["per_query"] == [1.0, 0.5]
    assert set_recall_3["mean"] == pytest.approx(0.75)
    assert mrr["reciprocal_ranks"] == [0.5, 1.0]
    assert mrr["mean"] == pytest.approx(0.75)


def test_negative_no_result_accuracy_excludes_positive_queries():
    relevant = [[], ["A"], []]
    retrieved = [[], ["A"], ["UNEXPECTED"]]

    result = negative_no_result_accuracy(relevant, retrieved)

    assert result == {
        "negative_query_support": 2,
        "success_count": 1,
        "accuracy": pytest.approx(0.5),
    }


def test_rag_metrics_return_na_without_relevant_denominator():
    relevant = [[], []]
    retrieved = [[], []]

    assert recall_at_k(relevant, retrieved, 1)["rate"] is None
    assert set_recall_at_k(relevant, retrieved, 3)["mean"] is None
    assert mean_reciprocal_rank(relevant, retrieved)["mean"] is None
