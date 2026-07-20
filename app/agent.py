import json
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app import crud
from app.audit_engine import audit_trip
from app.rag import rule_rag


AGENT_NAME = "TravelReimbursementAuditAgent"


class AgentTripNotFoundError(Exception):
    pass


class AgentNoExpensesFoundError(Exception):
    pass


def _step(step: str, status: str, message: str) -> Dict[str, str]:
    return {
        "step": step,
        "status": status,
        "message": message,
    }


def build_rule_query_for_expense(expense: Any) -> str:
    category = getattr(expense, "category", "")

    if category == "住宿":
        return "住宿 金额 凭证 超标"
    if category == "餐饮":
        return "餐饮 金额 凭证 超标"
    if category in {"交通", "市内出行"}:
        return "交通 市内出行 金额 出差期间"
    if category == "其他":
        return "其他 费用 人工复核 凭证"
    return "报销 凭证 出差期间 金额"


def retrieve_rules_for_expenses(expenses: List[Any]) -> List[Dict[str, Any]]:
    retrieved_rules = []

    for expense in expenses:
        query = build_rule_query_for_expense(expense)
        results = rule_rag.search(query=query, top_k=3)
        retrieved_rules.append(
            {
                "expense_id": expense.id,
                "category": expense.category,
                "query": query,
                "rules": [
                    {
                        "rule_id": item["rule"]["rule_id"],
                        "title": item["rule"]["title"],
                        "score": item["score"],
                    }
                    for item in results
                ],
            }
        )

    return retrieved_rules


def build_final_decision(status: str) -> Dict[str, str]:
    if status == "APPROVED":
        message = "All expenses passed the automatic reimbursement audit."
    elif status == "NEEDS_REVIEW":
        message = "Some expenses require manual review before reimbursement approval."
    elif status == "REJECTED":
        message = (
            "This reimbursement request contains high-severity compliance issues "
            "and should be rejected or manually reviewed."
        )
    else:
        message = "Unknown reimbursement audit status."

    return {
        "status": status,
        "message": message,
    }


def _format_audit_report(report: Any) -> Dict[str, Any]:
    return {
        "report_id": report.id,
        "trip_id": report.trip_id,
        "status": report.status,
        "total_amount": report.total_amount,
        "summary": json.loads(report.summary) if report.summary else None,
        "detail": json.loads(report.detail_json),
    }


def run_reimbursement_audit_agent(db: Session, trip_id: int) -> Dict[str, Any]:
    steps: List[Dict[str, str]] = []

    trip = crud.get_trip(db=db, trip_id=trip_id)
    if trip is None:
        steps.append(_step("LOAD_TRIP", "failed", "Trip not found."))
        raise AgentTripNotFoundError("Trip not found")
    steps.append(_step("LOAD_TRIP", "success", f"Loaded trip {trip_id}."))

    expenses = crud.list_expenses_by_trip(db=db, trip_id=trip_id)
    if not expenses:
        steps.append(
            _step("LOAD_EXPENSES", "failed", "No expenses found for this trip.")
        )
        raise AgentNoExpensesFoundError("No expenses found for this trip")
    steps.append(
        _step("LOAD_EXPENSES", "success", f"Loaded {len(expenses)} expenses.")
    )

    retrieved_rules = retrieve_rules_for_expenses(expenses)
    steps.append(
        _step(
            "RETRIEVE_RULES",
            "success",
            f"Retrieved rules for {len(retrieved_rules)} expenses.",
        )
    )

    detail = audit_trip(trip=trip, expenses=expenses)
    steps.append(
        _step(
            "RUN_DETERMINISTIC_AUDIT",
            "success",
            f"Audit status: {detail['status']}.",
        )
    )

    db_report = crud.create_audit_report(db=db, report=detail)
    steps.append(
        _step(
            "SAVE_AUDIT_REPORT",
            "success",
            f"Saved audit report {db_report.id}.",
        )
    )

    final_decision = build_final_decision(db_report.status)
    steps.append(
        _step(
            "RETURN_FINAL_DECISION",
            "success",
            f"Final decision: {final_decision['status']}.",
        )
    )

    return {
        "agent_name": AGENT_NAME,
        "trip_id": trip_id,
        "steps": steps,
        "retrieved_rules": retrieved_rules,
        "audit_report": _format_audit_report(db_report),
        "final_decision": final_decision,
    }
