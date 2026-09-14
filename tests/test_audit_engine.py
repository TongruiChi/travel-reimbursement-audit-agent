from datetime import date
from types import SimpleNamespace

from app import models
from app.audit_engine import audit_expense, audit_trip


LEGACY_FLAG_KEYS = {"rule_id", "flag", "severity", "message"}


def _rule_result(item, rule_id):
    return next(
        result for result in item["rule_results"] if result["rule_id"] == rule_id
    )


def _manual_review_trip_and_expense(*, receipt):
    trip = SimpleNamespace(
        id=1,
        start_date=date(2026, 5, 20),
        end_date=date(2026, 5, 23),
    )
    expense = SimpleNamespace(
        id=1,
        expense_date=date(2026, 5, 21),
        category="其他",
        amount=100.0,
        currency="CNY",
        merchant="测试商户",
        description="测试费用",
        receipt=receipt,
    )
    return trip, expense


def test_audit_trip_with_mock_data_returns_rejected_report(db_session, seeded_db):
    trip = db_session.query(models.Trip).filter(models.Trip.id == seeded_db).first()
    expenses = (
        db_session.query(models.Expense)
        .filter(models.Expense.trip_id == trip.id)
        .order_by(models.Expense.id.asc())
        .all()
    )

    report = audit_trip(trip, expenses)
    flags = set(report["summary"]["flags"])

    assert report["policy_id"] == "company-travel-reimbursement"
    assert report["policy_version"] == "1.0.0"
    assert report["status"] == "REJECTED"
    assert len(report["items"]) == 6
    assert report["total_amount"] == 1663.5
    assert "HOTEL_AMOUNT_EXCEED_LIMIT" not in flags
    assert "MEAL_AMOUNT_EXCEED_LIMIT" in flags
    assert "EXPENSE_OUT_OF_TRIP_DATE" in flags
    assert "RECEIPT_MISSING" in flags
    assert "OTHER_EXPENSE_NEED_REVIEW" in flags
    legacy_flags = [flag for item in report["items"] for flag in item["flags"]]
    assert legacy_flags
    assert all(isinstance(item["flags"], list) for item in report["items"])
    assert all(isinstance(flag, dict) for flag in legacy_flags)
    assert all(set(flag) == LEGACY_FLAG_KEYS for flag in legacy_flags)
    assert all(
        all(isinstance(flag[key], str) for key in LEGACY_FLAG_KEYS)
        for flag in legacy_flags
    )
    assert all(len(item["rule_results"]) == 10 for item in report["items"])


def test_audit_expense_marks_ambiguous_traffic_for_review(db_session, seeded_db):
    trip = db_session.query(models.Trip).filter(models.Trip.id == seeded_db).first()
    expense = db_session.query(models.Expense).filter(models.Expense.id == 1).first()

    item = audit_expense(trip, expense)

    assert item["status"] == "NEEDS_REVIEW"
    assert item["flags"] == []
    traffic_result = next(
        result
        for result in item["rule_results"]
        if result["rule_id"] == "R-TRAFFIC-002"
    )
    assert traffic_result["result"] == "INDETERMINATE"


def test_other_expense_manual_review_is_indeterminate_and_needs_review():
    trip, expense = _manual_review_trip_and_expense(receipt=object())

    report = audit_trip(trip, [expense])
    item = report["items"][0]

    assert _rule_result(item, "R-OTHER-001")["result"] == "INDETERMINATE"
    assert item["status"] == "NEEDS_REVIEW"
    assert report["status"] == "NEEDS_REVIEW"
    assert item["flags"] == [
        {
            "rule_id": "R-OTHER-001",
            "flag": "OTHER_EXPENSE_NEED_REVIEW",
            "severity": "low",
            "message": "其他费用需人工确认是否与出差相关。",
        }
    ]


def test_other_expense_with_high_violation_is_rejected():
    trip, expense = _manual_review_trip_and_expense(receipt=None)

    report = audit_trip(trip, [expense])
    item = report["items"][0]

    assert _rule_result(item, "R-OTHER-001")["result"] == "INDETERMINATE"
    assert _rule_result(item, "R-GEN-002")["result"] == "VIOLATION"
    assert item["status"] == "REJECTED"
    assert report["status"] == "REJECTED"
    assert {flag["flag"] for flag in item["flags"]} == {
        "RECEIPT_MISSING",
        "OTHER_EXPENSE_NEED_REVIEW",
    }
