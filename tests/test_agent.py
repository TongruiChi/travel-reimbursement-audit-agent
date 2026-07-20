import pytest
from datetime import date

from app import models
from app.agent import (
    AGENT_NAME,
    AgentNoExpensesFoundError,
    AgentTripNotFoundError,
    run_reimbursement_audit_agent,
)


def test_agent_runs_fixed_six_step_flow_and_saves_report(db_session, seeded_db):
    result = run_reimbursement_audit_agent(db_session, seeded_db)
    step_names = [step["step"] for step in result["steps"]]

    assert result["agent_name"] == AGENT_NAME
    assert result["trip_id"] == seeded_db
    assert result["final_decision"]["status"] == "REJECTED"
    assert len(result["steps"]) == 6
    assert len(result["retrieved_rules"]) == 6
    assert len(result["audit_report"]["detail"]["items"]) == 6
    assert step_names == [
        "LOAD_TRIP",
        "LOAD_EXPENSES",
        "RETRIEVE_RULES",
        "RUN_DETERMINISTIC_AUDIT",
        "SAVE_AUDIT_REPORT",
        "RETURN_FINAL_DECISION",
    ]
    assert db_session.query(models.AuditReport).count() == 1


def test_agent_raises_for_missing_trip(db_session):
    with pytest.raises(AgentTripNotFoundError):
        run_reimbursement_audit_agent(db_session, 999999)


def test_agent_raises_for_trip_without_expenses(db_session):
    trip = models.Trip(
        employee_name="No Expense User",
        department="Finance",
        origin="Beijing",
        destination="Shanghai",
        start_date=date(2026, 5, 20),
        end_date=date(2026, 5, 21),
        purpose="No expense test",
    )
    db_session.add(trip)
    db_session.commit()
    db_session.refresh(trip)

    with pytest.raises(AgentNoExpensesFoundError):
        run_reimbursement_audit_agent(db_session, trip.id)
