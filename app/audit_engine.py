from typing import Any, Callable, Dict, List, Optional

from app.policy import (
    Enforcement,
    EvaluationResult,
    EvaluatorName,
    PolicyDocument,
    PolicyRegistry,
    PolicyRule,
    PolicyThreshold,
    Severity,
    ThresholdBasis,
    ThresholdComparison,
    policy_registry,
)


APPROVED = "APPROVED"
NEEDS_REVIEW = "NEEDS_REVIEW"
REJECTED = "REJECTED"


def _has_receipt(expense: Any) -> bool:
    receipt = getattr(expense, "receipt", None)
    if receipt is None:
        return False
    if isinstance(receipt, list):
        return len(receipt) > 0
    return True


def _matches_threshold(value: float, threshold: PolicyThreshold) -> bool:
    if threshold.comparison == ThresholdComparison.GT:
        return value > threshold.amount
    if threshold.comparison == ThresholdComparison.LTE:
        return value <= threshold.amount
    raise ValueError(f"Unsupported threshold comparison: {threshold.comparison}")


def evaluate_expense_date_within_trip(
    rule: PolicyRule,
    policy: PolicyDocument,
    trip: Any,
    expense: Any,
) -> EvaluationResult:
    del rule, policy
    if trip.start_date <= expense.expense_date <= trip.end_date:
        return EvaluationResult.PASS
    return EvaluationResult.VIOLATION


def evaluate_positive_amount(
    rule: PolicyRule,
    policy: PolicyDocument,
    trip: Any,
    expense: Any,
) -> EvaluationResult:
    del policy, trip
    if rule.threshold is None:
        raise ValueError(f"Rule {rule.rule_id} requires a threshold")
    if _matches_threshold(float(expense.amount), rule.threshold):
        return EvaluationResult.PASS
    return EvaluationResult.VIOLATION


def evaluate_amount_threshold(
    rule: PolicyRule,
    policy: PolicyDocument,
    trip: Any,
    expense: Any,
) -> EvaluationResult:
    del trip
    if rule.threshold is None:
        raise ValueError(f"Rule {rule.rule_id} requires a threshold")

    if getattr(expense, "currency", None) != policy.currency:
        return EvaluationResult.INDETERMINATE

    if rule.applicable_cities is not None:
        expense_city = getattr(expense, "city", None)
        if expense_city is None:
            return EvaluationResult.INDETERMINATE
        if expense_city not in rule.applicable_cities:
            return EvaluationResult.NOT_APPLICABLE

    amount = float(expense.amount)
    if rule.threshold.basis == ThresholdBasis.PER_NIGHT:
        night_count = getattr(expense, "night_count", None)
        if night_count is None or night_count <= 0:
            return EvaluationResult.INDETERMINATE
        amount = amount / night_count

    if _matches_threshold(amount, rule.threshold):
        return EvaluationResult.PASS
    return EvaluationResult.VIOLATION


def evaluate_receipt_presence(
    rule: PolicyRule,
    policy: PolicyDocument,
    trip: Any,
    expense: Any,
) -> EvaluationResult:
    del policy, trip
    if not _has_receipt(expense):
        return EvaluationResult.VIOLATION

    # Presence is only one part of the current receipt policies. A record does not
    # prove authenticity, validity, or that the receipt has not been reimbursed.
    if rule.enforcement == Enforcement.PARTIAL:
        return EvaluationResult.INDETERMINATE
    return EvaluationResult.PASS


def evaluate_manual_review(
    rule: PolicyRule,
    policy: PolicyDocument,
    trip: Any,
    expense: Any,
) -> EvaluationResult:
    del rule, policy, trip, expense
    return EvaluationResult.INDETERMINATE


Evaluator = Callable[
    [PolicyRule, PolicyDocument, Any, Any],
    EvaluationResult,
]

EVALUATORS: Dict[EvaluatorName, Evaluator] = {
    EvaluatorName.EXPENSE_DATE_WITHIN_TRIP: evaluate_expense_date_within_trip,
    EvaluatorName.POSITIVE_AMOUNT: evaluate_positive_amount,
    EvaluatorName.AMOUNT_THRESHOLD: evaluate_amount_threshold,
    EvaluatorName.RECEIPT_PRESENCE: evaluate_receipt_presence,
    EvaluatorName.MANUAL_REVIEW: evaluate_manual_review,
}

missing_evaluators = set(EvaluatorName) - set(EVALUATORS)
if missing_evaluators:
    missing_names = ", ".join(sorted(item.value for item in missing_evaluators))
    raise RuntimeError(f"Evaluator registry is incomplete: {missing_names}")


def _evaluate_rule(
    rule: PolicyRule,
    policy: PolicyDocument,
    trip: Any,
    expense: Any,
) -> EvaluationResult:
    category = getattr(expense, "category", "")
    if "ALL" not in rule.category and category not in rule.category:
        return EvaluationResult.NOT_APPLICABLE

    if (
        rule.evaluable_categories is not None
        and category not in rule.evaluable_categories
    ):
        return EvaluationResult.INDETERMINATE

    if rule.evaluator is None:
        return EvaluationResult.INDETERMINATE

    try:
        evaluator = EVALUATORS[rule.evaluator]
    except KeyError as exc:
        raise ValueError(f"Unknown evaluator: {rule.evaluator}") from exc
    return evaluator(rule, policy, trip, expense)


def _build_rule_result(
    rule: PolicyRule,
    policy_version: str,
    result: EvaluationResult,
) -> Dict[str, Any]:
    is_violation = result == EvaluationResult.VIOLATION
    return {
        "rule_id": rule.rule_id,
        "policy_version": policy_version,
        "result": result.value,
        "severity": rule.severity.value if rule.severity is not None else None,
        "flag": rule.flag if is_violation else None,
        "message": rule.violation_message if is_violation else None,
    }


def _determine_item_status(rule_results: List[Dict[str, Any]]) -> str:
    violations = [
        result
        for result in rule_results
        if result["result"] == EvaluationResult.VIOLATION.value
    ]
    if any(result["severity"] == Severity.HIGH.value for result in violations):
        return REJECTED
    if violations:
        return NEEDS_REVIEW
    if any(
        result["result"] == EvaluationResult.INDETERMINATE.value
        for result in rule_results
    ):
        return NEEDS_REVIEW
    return APPROVED


def _build_legacy_flags(
    rules: List[PolicyRule],
    rule_results: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    flags: List[Dict[str, str]] = []

    for rule, result in zip(rules, rule_results):
        is_violation = result["result"] == EvaluationResult.VIOLATION.value
        is_manual_review_marker = (
            rule.evaluator == EvaluatorName.MANUAL_REVIEW
            and result["result"] == EvaluationResult.INDETERMINATE.value
        )
        if not (is_violation or is_manual_review_marker):
            continue

        # The legacy API contract requires four string fields. Rules without a
        # legacy severity or message remain available through rule_results only.
        if (
            rule.flag is None
            or rule.severity is None
            or rule.violation_message is None
        ):
            continue

        flags.append(
            {
                "rule_id": rule.rule_id,
                "flag": rule.flag,
                "severity": rule.severity.value,
                "message": rule.violation_message,
            }
        )

    return flags


def determine_report_status(items: List[Dict[str, Any]]) -> str:
    if any(item["status"] == REJECTED for item in items):
        return REJECTED
    if any(item["status"] == NEEDS_REVIEW for item in items):
        return NEEDS_REVIEW
    return APPROVED


def audit_expense(
    trip: Any,
    expense: Any,
    registry: Optional[PolicyRegistry] = None,
) -> Dict[str, Any]:
    selected_registry = registry or policy_registry
    policy = selected_registry.document
    rules = list(selected_registry.rules)
    rule_results = [
        _build_rule_result(
            rule=rule,
            policy_version=policy.policy_version,
            result=_evaluate_rule(rule, policy, trip, expense),
        )
        for rule in rules
    ]
    flags = _build_legacy_flags(rules, rule_results)

    return {
        "expense_id": expense.id,
        "category": expense.category,
        "amount": float(expense.amount),
        "expense_date": expense.expense_date.isoformat(),
        "merchant": expense.merchant,
        "status": _determine_item_status(rule_results),
        "flags": flags,
        "rule_hits": [flag["rule_id"] for flag in flags],
        "rule_results": rule_results,
    }


def audit_trip(
    trip: Any,
    expenses: List[Any],
    registry: Optional[PolicyRegistry] = None,
) -> Dict[str, Any]:
    selected_registry = registry or policy_registry
    items = [
        audit_expense(trip, expense, registry=selected_registry)
        for expense in expenses
    ]

    total_amount = sum(item["amount"] for item in items)
    approved_amount = sum(
        item["amount"] for item in items if item["status"] == APPROVED
    )
    rejected_amount = sum(
        item["amount"] for item in items if item["status"] == REJECTED
    )
    needs_review_amount = sum(
        item["amount"] for item in items if item["status"] == NEEDS_REVIEW
    )
    all_flags = [
        flag["flag"]
        for item in items
        for flag in item["flags"]
    ]

    return {
        "policy_id": selected_registry.policy_id,
        "policy_version": selected_registry.policy_version,
        "trip_id": trip.id,
        "status": determine_report_status(items),
        "total_amount": round(total_amount, 2),
        "approved_amount": round(approved_amount, 2),
        "rejected_amount": round(rejected_amount, 2),
        "needs_review_amount": round(needs_review_amount, 2),
        "summary": {
            "expense_count": len(items),
            "approved_expense_count": sum(
                1 for item in items if item["status"] == APPROVED
            ),
            "flagged_expense_count": sum(1 for item in items if item["flags"]),
            "flags": list(dict.fromkeys(all_flags)),
        },
        "items": items,
    }
