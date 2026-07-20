import argparse
import json
import sys
from datetime import date
from typing import Any, Dict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import models
from app.database import SessionLocal, init_db

DEFAULT_MOCK_FILE = Path("data/mock/mock_trip_expenses.json")

def parse_date(value: str) -> date:
    return date.fromisoformat(value)

def load_mock_data(file_path: Path) -> Dict[str, Any]:

    if not file_path.exists():
        raise FileNotFoundError(f"Mock data file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as file:
        return json.load(file)



def reset_database_data() -> None:
    db = SessionLocal()

    try:
        db.query(models.AuditReport).delete()
        db.query(models.Receipt).delete()
        db.query(models.Expense).delete()
        db.query(models.Trip).delete()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()



def seed_data(payload: Dict[str, Any]) -> int:
    # 将mock行程、消费、凭证写入数据库
    # 返回创建出来的trip_id

    db = SessionLocal()

    try:
        trip_data = payload["trip"]
        trip = models.Trip(
            employee_name=trip_data["employee_name"],
            department=trip_data.get("department"),
            origin=trip_data.get("origin"),
            destination=trip_data["destination"],
            start_date=parse_date(trip_data["start_date"]),
            end_date=parse_date(trip_data["end_date"]),
            purpose=trip_data["purpose"],
        )

        db.add(trip)
        db.flush()  # 获取trip.id


        for expense_data in payload.get("expenses", []):
            expense = models.Expense(
                trip_id=trip.id,
                expense_date=parse_date(expense_data["expense_date"]),
                category=expense_data["category"],
                amount=expense_data["amount"],
                currency=expense_data.get("currency", "CNY"),
                merchant=expense_data.get("merchant"),
                description=expense_data.get("description"),
            )

            db.add(expense)
            db.flush()  # 获取expense.id

            receipt_data = expense_data.get("receipt")

            if receipt_data:
                receipt = models.Receipt(
                    # expense_id=expense.id,
                    # receipt_type=receipt_data["receipt_type"],
                    # receipt_number=receipt_data.get("receipt_number"),
                    # file_url=receipt_data.get("file_url"),
                    # issued_date=parse_date(receipt_data["issued_date"])
                    # if receipt_data.get("issued_date")
                    # else None,
                    # seller_name=receipt_data.get("seller_name"),
                    expense_id=expense.id,
                    receipt_type=receipt_data.get("receipt_type"),
                    receipt_number=receipt_data.get("receipt_number"),
                    file_url=receipt_data.get("file_url"),
                    issued_date=parse_date(receipt_data.get("issued_date")),
                    seller_name=receipt_data.get("seller_name"),
                    amount=receipt_data.get("amount", expense.amount),
                    merchant=receipt_data.get("merchant") or receipt_data.get("seller_name"),
                    description=receipt_data.get("description") or "",
                )
                db.add(receipt)

        db.commit()
        db.refresh(trip)

        return trip.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()



def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed mock data into the database."
        )

    parser.add_argument(
        "--file",
        type=str,
        default=str(DEFAULT_MOCK_FILE),
        help="Clear existing MVP data before seeding."
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear existing MVP data before seeding."
    )

    args = parser.parse_args()

    init_db()

    if args.reset:
        reset_database_data()
        print("Existing MVP data cleared successfully.")

    payload = load_mock_data(Path(args.file))
    trip_id = seed_data(payload)

    print(f"Mock data seeded successfully with trip_id: {trip_id}")

if __name__ == "__main__":
    main()
