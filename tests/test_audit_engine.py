from app import models
from app.audit_engine import audit_expense, audit_trip


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

    assert report["status"] == "REJECTED"
    assert len(report["items"]) == 6
    assert report["total_amount"] == 1663.5
    assert "HOTEL_AMOUNT_EXCEED_LIMIT" in flags
    assert "MEAL_AMOUNT_EXCEED_LIMIT" in flags
    assert "EXPENSE_OUT_OF_TRIP_DATE" in flags
    assert "RECEIPT_MISSING" in flags
    assert "OTHER_EXPENSE_NEED_REVIEW" in flags


def test_audit_expense_approves_normal_expense(db_session, seeded_db):
    trip = db_session.query(models.Trip).filter(models.Trip.id == seeded_db).first()
    expense = db_session.query(models.Expense).filter(models.Expense.id == 1).first()

    item = audit_expense(trip, expense)

    assert item["status"] == "APPROVED"
    assert item["flags"] == []
