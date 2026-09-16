from __future__ import annotations

from collections.abc import Sequence
from typing import Any


RULE_STATES = (
    "PASS",
    "VIOLATION",
    "INDETERMINATE",
    "NOT_APPLICABLE",
)
FINAL_STATES = (
    "APPROVED",
    "NEEDS_REVIEW",
    "REJECTED",
)
DETERMINATE_STATES = {"PASS", "VIOLATION"}


def _validate_parallel(expected: Sequence[Any], actual: Sequence[Any]) -> None:
    if len(expected) != len(actual):
        raise ValueError(
            f"Expected and actual lengths differ: {len(expected)} != {len(actual)}"
        )


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def violation_metrics(
    expected: Sequence[str],
    actual: Sequence[str],
) -> dict[str, int | float | None]:
    """Return binary metrics with VIOLATION as the positive class."""
    _validate_parallel(expected, actual)
    tp = sum(
        expected_value == "VIOLATION" and actual_value == "VIOLATION"
        for expected_value, actual_value in zip(expected, actual)
    )
    fp = sum(
        expected_value != "VIOLATION" and actual_value == "VIOLATION"
        for expected_value, actual_value in zip(expected, actual)
    )
    fn = sum(
        expected_value == "VIOLATION" and actual_value != "VIOLATION"
        for expected_value, actual_value in zip(expected, actual)
    )
    tn = len(expected) - tp - fp - fn
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = None
    if precision is not None and recall is not None:
        f1 = _ratio(2 * tp, 2 * tp + fp + fn)

    return {
        "total_rule_units": len(expected),
        "expected_violation_support": tp + fn,
        "predicted_violation_support": tp + fp,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def categorical_metrics(
    expected: Sequence[str],
    actual: Sequence[str],
    labels: Sequence[str],
) -> dict[str, Any]:
    """Return accuracy, support, per-class accuracy, and a full matrix."""
    _validate_parallel(expected, actual)
    label_set = set(labels)
    unknown_expected = set(expected) - label_set
    unknown_actual = set(actual) - label_set
    if unknown_expected or unknown_actual:
        raise ValueError(
            "Unknown categorical values: "
            f"expected={sorted(unknown_expected)}, actual={sorted(unknown_actual)}"
        )

    matrix = {
        expected_label: {actual_label: 0 for actual_label in labels}
        for expected_label in labels
    }
    for expected_value, actual_value in zip(expected, actual):
        matrix[expected_value][actual_value] += 1

    correct = sum(
        expected_value == actual_value
        for expected_value, actual_value in zip(expected, actual)
    )
    per_class = {}
    for label in labels:
        support = sum(matrix[label].values())
        class_correct = matrix[label][label]
        per_class[label] = {
            "support": support,
            "correct": class_correct,
            "accuracy": _ratio(class_correct, support),
        }

    return {
        "support": len(expected),
        "correct": correct,
        "accuracy": _ratio(correct, len(expected)),
        "labels": list(labels),
        "confusion_matrix": matrix,
        "per_class": per_class,
    }


def exact_match_metrics(matches: Sequence[bool]) -> dict[str, int | float | None]:
    match_count = sum(matches)
    return {
        "support": len(matches),
        "match_count": match_count,
        "rate": _ratio(match_count, len(matches)),
    }


def automation_coverage(
    expected: Sequence[str],
    actual: Sequence[str],
) -> dict[str, int | float | None]:
    _validate_parallel(expected, actual)
    applicable = [
        actual_value
        for expected_value, actual_value in zip(expected, actual)
        if expected_value != "NOT_APPLICABLE"
    ]
    automated_count = sum(value in DETERMINATE_STATES for value in applicable)
    return {
        "applicable_support": len(applicable),
        "automated_count": automated_count,
        "rate": _ratio(automated_count, len(applicable)),
    }


def determinate_accuracy(
    expected: Sequence[str],
    actual: Sequence[str],
) -> dict[str, int | float | None]:
    _validate_parallel(expected, actual)
    scored_pairs = [
        (expected_value, actual_value)
        for expected_value, actual_value in zip(expected, actual)
        if expected_value != "NOT_APPLICABLE"
        and actual_value in DETERMINATE_STATES
    ]
    correct = sum(
        expected_value == actual_value
        for expected_value, actual_value in scored_pairs
    )
    return {
        "determinate_support": len(scored_pairs),
        "correct": correct,
        "accuracy": _ratio(correct, len(scored_pairs)),
    }


def appropriate_abstention_rate(
    expected: Sequence[str],
    actual: Sequence[str],
) -> dict[str, int | float | None]:
    _validate_parallel(expected, actual)
    expected_indeterminate = [
        actual_value
        for expected_value, actual_value in zip(expected, actual)
        if expected_value == "INDETERMINATE"
    ]
    correct_abstentions = sum(
        value == "INDETERMINATE" for value in expected_indeterminate
    )
    return {
        "expected_indeterminate_support": len(expected_indeterminate),
        "correct_abstentions": correct_abstentions,
        "rate": _ratio(correct_abstentions, len(expected_indeterminate)),
    }


def recall_at_k(
    relevant_rule_ids: Sequence[Sequence[str]],
    retrieved_rule_ids: Sequence[Sequence[str]],
    k: int,
) -> dict[str, int | float | None]:
    if k < 1:
        raise ValueError("k must be at least 1")
    _validate_parallel(relevant_rule_ids, retrieved_rule_ids)
    positive_pairs = [
        (set(relevant), list(retrieved))
        for relevant, retrieved in zip(relevant_rule_ids, retrieved_rule_ids)
        if relevant
    ]
    hits = sum(
        bool(relevant.intersection(retrieved[:k]))
        for relevant, retrieved in positive_pairs
    )
    return {
        "positive_query_support": len(positive_pairs),
        "hit_count": hits,
        "rate": _ratio(hits, len(positive_pairs)),
    }


def set_recall_at_k(
    relevant_rule_ids: Sequence[Sequence[str]],
    retrieved_rule_ids: Sequence[Sequence[str]],
    k: int,
) -> dict[str, int | float | None]:
    if k < 1:
        raise ValueError("k must be at least 1")
    _validate_parallel(relevant_rule_ids, retrieved_rule_ids)
    per_query = [
        len(set(relevant).intersection(retrieved[:k])) / len(set(relevant))
        for relevant, retrieved in zip(relevant_rule_ids, retrieved_rule_ids)
        if relevant
    ]
    return {
        "positive_query_support": len(per_query),
        "per_query": per_query,
        "mean": (
            sum(per_query) / len(per_query)
            if per_query
            else None
        ),
    }


def mean_reciprocal_rank(
    relevant_rule_ids: Sequence[Sequence[str]],
    retrieved_rule_ids: Sequence[Sequence[str]],
) -> dict[str, int | float | None | list[float]]:
    _validate_parallel(relevant_rule_ids, retrieved_rule_ids)
    reciprocal_ranks = []
    for relevant, retrieved in zip(relevant_rule_ids, retrieved_rule_ids):
        if not relevant:
            continue
        relevant_set = set(relevant)
        first_rank = next(
            (
                index
                for index, rule_id in enumerate(retrieved, start=1)
                if rule_id in relevant_set
            ),
            None,
        )
        reciprocal_ranks.append(0.0 if first_rank is None else 1 / first_rank)

    return {
        "positive_query_support": len(reciprocal_ranks),
        "reciprocal_ranks": reciprocal_ranks,
        "mean": (
            sum(reciprocal_ranks) / len(reciprocal_ranks)
            if reciprocal_ranks
            else None
        ),
    }


def negative_no_result_accuracy(
    relevant_rule_ids: Sequence[Sequence[str]],
    retrieved_rule_ids: Sequence[Sequence[str]],
) -> dict[str, int | float | None]:
    _validate_parallel(relevant_rule_ids, retrieved_rule_ids)
    negative_results = [
        retrieved
        for relevant, retrieved in zip(relevant_rule_ids, retrieved_rule_ids)
        if not relevant
    ]
    successes = sum(not retrieved for retrieved in negative_results)
    return {
        "negative_query_support": len(negative_results),
        "success_count": successes,
        "accuracy": _ratio(successes, len(negative_results)),
    }
