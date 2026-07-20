import json
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import models
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def seeded_db(db_session):
    mock_path = PROJECT_ROOT / "data" / "mock" / "mock_trip_expenses.json"
    payload = json.loads(mock_path.read_text(encoding="utf-8"))

    trip_data = payload["trip"]
    trip = models.Trip(
        employee_name=trip_data["employee_name"],
        department=trip_data["department"],
        origin=trip_data["origin"],
        destination=trip_data["destination"],
        start_date=date.fromisoformat(trip_data["start_date"]),
        end_date=date.fromisoformat(trip_data["end_date"]),
        purpose=trip_data["purpose"],
    )
    db_session.add(trip)
    db_session.flush()

    for expense_data in payload["expenses"]:
        expense = models.Expense(
            trip_id=trip.id,
            expense_date=date.fromisoformat(expense_data["expense_date"]),
            category=expense_data["category"],
            amount=expense_data["amount"],
            currency=expense_data.get("currency", "CNY"),
            merchant=expense_data.get("merchant"),
            description=expense_data.get("description"),
        )
        db_session.add(expense)
        db_session.flush()

        receipt_data = expense_data.get("receipt")
        if receipt_data:
            issued_date = receipt_data.get("issued_date")
            receipt = models.Receipt(
                expense_id=expense.id,
                receipt_type=receipt_data["receipt_type"],
                receipt_number=receipt_data.get("receipt_number"),
                file_url=receipt_data.get("file_url"),
                issued_date=date.fromisoformat(issued_date) if issued_date else None,
                seller_name=receipt_data.get("seller_name"),
                amount=receipt_data.get("amount", expense.amount),
                merchant=receipt_data.get("merchant") or receipt_data.get("seller_name"),
                description=receipt_data.get("description") or "",
            )
            db_session.add(receipt)

    db_session.commit()
    return trip.id


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
