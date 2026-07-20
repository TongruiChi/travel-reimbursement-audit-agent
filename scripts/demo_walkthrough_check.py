import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from app import models
from app.agent import run_reimbursement_audit_agent
from app.database import SessionLocal, init_db
from app.rag import rule_rag
from scripts.seed_mock_data import load_mock_data, reset_database_data, seed_data


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    init_db()
    reset_database_data()
    payload = load_mock_data(PROJECT_ROOT / "data" / "mock" / "mock_trip_expenses.json")
    trip_id = seed_data(payload)

    rule_count = len(rule_rag.rule_chunks)
    require(rule_count == 10, f"Expected 10 rule chunks, got {rule_count}.")
    print(f"[OK] Rule chunks loaded: {rule_count}")

    db = SessionLocal()
    try:
        trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
        require(trip is not None, f"Mock trip {trip_id} was not loaded.")
        print(f"[OK] Mock trip loaded: {trip.id}")

        expenses = (
            db.query(models.Expense)
            .filter(models.Expense.trip_id == trip.id)
            .order_by(models.Expense.expense_date.asc(), models.Expense.id.asc())
            .all()
        )
        require(len(expenses) == 6, f"Expected 6 expenses, got {len(expenses)}.")
        print(f"[OK] Expenses loaded: {len(expenses)}")

        result = run_reimbursement_audit_agent(db, trip.id)
        status = result["final_decision"]["status"]
        require(status == "REJECTED", f"Expected REJECTED, got {status}.")
        print(f"[OK] Agent status: {status}")

        retrieved_count = len(result["retrieved_rules"])
        require(
            retrieved_count == 6,
            f"Expected 6 retrieved rule groups, got {retrieved_count}.",
        )
        print(f"[OK] Retrieved rule groups: {retrieved_count}")

        report_id = result["audit_report"]["report_id"]
        require(report_id is not None, "Audit report was not saved.")
        print(f"[OK] Audit report saved: report_id={report_id}")

        item_count = len(result["audit_report"]["detail"]["items"])
        require(item_count == 6, f"Expected 6 audit items, got {item_count}.")
        print(f"[OK] Audit items: {item_count}")
    finally:
        db.close()

    print()
    print("Demo walkthrough check passed.")


if __name__ == "__main__":
    main()
