from typing import Any, Dict, List


HIGH = "high"
MEDIUM = "medium"
LOW = "low"

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


def _flag(
    rule_id: str,
    flag: str,
    severity: str,
    message: str,
) -> Dict[str, str]:
    return {
        "rule_id": rule_id,
        "flag": flag,
        "severity": severity,
        "message": message,
    }


def _determine_item_status(flags: List[Dict[str, str]]) -> str:
    if any(flag["severity"] == HIGH for flag in flags):
        return REJECTED
    if flags:
        return NEEDS_REVIEW
    return APPROVED


def determine_report_status(items: List[Dict[str, Any]]) -> str:
    if any(item["status"] == REJECTED for item in items):
        return REJECTED
    if any(item["status"] == NEEDS_REVIEW for item in items):
        return NEEDS_REVIEW
    return APPROVED


def audit_expense(trip: Any, expense: Any) -> Dict[str, Any]:
    flags: List[Dict[str, str]] = []

    if not (trip.start_date <= expense.expense_date <= trip.end_date):
        flags.append(
            _flag(
                "R-GEN-001",
                "EXPENSE_OUT_OF_TRIP_DATE",
                HIGH,
                "消费日期不在出差期间内，需人工复核。",
            )
        )

    if expense.amount <= 0:
        flags.append(
            _flag(
                "R-GEN-003",
                "INVALID_AMOUNT",
                HIGH,
                "报销金额必须大于 0。",
            )
        )

    if not _has_receipt(expense):
        flags.append(
            _flag(
                "R-GEN-002",
                "RECEIPT_MISSING",
                HIGH,
                "该笔费用缺少报销凭证。",
            )
        )

    if expense.category == "住宿" and expense.amount > 800:
        flags.append(
            _flag(
                "R-HOTEL-001",
                "HOTEL_AMOUNT_EXCEED_LIMIT",
                MEDIUM,
                "住宿费用超过 800 元标准，需补充审批说明。",
            )
        )

    if expense.category == "餐饮" and expense.amount > 150:
        flags.append(
            _flag(
                "R-MEAL-001",
                "MEAL_AMOUNT_EXCEED_LIMIT",
                MEDIUM,
                "单笔餐饮费用超过 150 元标准，需人工复核。",
            )
        )

    if expense.category in {"交通", "市内出行"} and expense.amount > 300:
        flags.append(
            _flag(
                "R-TRAFFIC-002",
                "LOCAL_TRAFFIC_AMOUNT_HIGH",
                MEDIUM,
                "单笔市内出行费用超过 300 元，需人工复核。",
            )
        )

    if expense.category == "其他":
        flags.append(
            _flag(
                "R-OTHER-001",
                "OTHER_EXPENSE_NEED_REVIEW",
                LOW,
                "其他费用需人工确认是否与出差相关。",
            )
        )

    return {
        "expense_id": expense.id,
        "category": expense.category,
        "amount": float(expense.amount),
        "expense_date": expense.expense_date.isoformat(),
        "merchant": expense.merchant,
        "status": _determine_item_status(flags),
        "flags": flags,
        "rule_hits": [flag["rule_id"] for flag in flags],
    }


def audit_trip(trip: Any, expenses: List[Any]) -> Dict[str, Any]:
    items = [audit_expense(trip, expense) for expense in expenses]

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
            "flagged_expense_count": sum(
                1 for item in items if item["flags"]
            ),
            "flags": list(dict.fromkeys(all_flags)),
        },
        "items": items,
    }
