import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app import models, schemas



def get_trip(db: Session, trip_id: int) -> Optional[models.Trip]:
    return db.query(models.Trip).filter(models.Trip.id == trip_id).first()



def create_trip(db: Session, trip_in: schemas.TripCreate) -> models.Trip:
    db_trip = models.Trip(
        **trip_in.model_dump()
    )
    db.add(db_trip)
    db.commit()
    db.refresh(db_trip)
    return db_trip



def get_expense(db: Session, expense_id: int) -> Optional[models.Expense]:
    return db.query(models.Expense).filter(models.Expense.id == expense_id).first()



def list_expenses_by_trip(db: Session, trip_id: int) -> List[models.Expense]:
    return (
        db.query(models.Expense)
        .filter(models.Expense.trip_id == trip_id)
        .order_by(models.Expense.expense_date.asc(), models.Expense.id.asc())
        .all()
    )



def create_expense(
        db: Session,
        expense_in: schemas.ExpenseCreate
        ) -> models.Expense:
        db_expense = models.Expense(
             **expense_in.model_dump())
        db.add(db_expense)
        db.commit()
        db.refresh(db_expense)
        return db_expense

def get_receipt_by_expense(
    db: Session,
    expense_id: int
    ) -> Optional[models.Receipt]:
    return (
        db.query(models.Receipt)
        .filter(models.Receipt.expense_id == expense_id)
        .first()
    )



def create_receipt(
    db: Session,
    receipt_in: schemas.ReceiptCreate
    ) -> models.Receipt:
    db_receipt = models.Receipt(
        **receipt_in.model_dump())
    db.add(db_receipt)
    db.commit()
    db.refresh(db_receipt)

    return db_receipt


def create_audit_report(
    db: Session,
    report: Dict[str, Any]
) -> models.AuditReport:
    db_report = models.AuditReport(
        trip_id=report["trip_id"],
        status=report["status"],
        total_amount=report["total_amount"],
        summary=json.dumps(report.get("summary", {}), ensure_ascii=False),
        detail_json=json.dumps(report, ensure_ascii=False),
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


def get_audit_report(
    db: Session,
    report_id: int
) -> Optional[models.AuditReport]:
    return (
        db.query(models.AuditReport)
        .filter(models.AuditReport.id == report_id)
        .first()
    )


def list_audit_reports_by_trip(
    db: Session,
    trip_id: int
) -> List[models.AuditReport]:
    return (
        db.query(models.AuditReport)
        .filter(models.AuditReport.trip_id == trip_id)
        .order_by(models.AuditReport.created_at.desc(), models.AuditReport.id.desc())
        .all()
    )


def get_latest_audit_report_by_trip(
    db: Session,
    trip_id: int
) -> Optional[models.AuditReport]:
    return (
        db.query(models.AuditReport)
        .filter(models.AuditReport.trip_id == trip_id)
        .order_by(models.AuditReport.created_at.desc(), models.AuditReport.id.desc())
        .first()
    )




