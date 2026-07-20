import json

from fastapi import FastAPI, Depends, HTTPException, Query, status

from typing import List

from contextlib import asynccontextmanager

from sqlalchemy.orm import Session

from app import crud, schemas
from app.agent import (
    AgentNoExpensesFoundError,
    AgentTripNotFoundError,
    run_reimbursement_audit_agent,
)
from app.audit_engine import audit_trip as run_audit_trip
from app.config import settings
from app.database import get_db, init_db
from app.models import Expense
from app.rag import rule_rag
from app.reporting import format_audit_report, format_audit_report_summary



@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用生命周期管理器
    # 在应用启动时执行初始化数据库等操作，后续可以增加更多的生命周期事件处理
    init_db()  # 初始化数据库，确保 MVP 所需数据表已创建
    yield
    # 应用关闭时可以执行清理资源等操作，当前mvp版本不需要特殊处理



app = FastAPI(
    title=settings.project_name,
    debug=settings.debug,
    version="0.1.0",
    description="MVP backend for enterprise travel reimbursement collection and audit agent.",
    lifespan=lifespan
)


@app.get("/health")
def health_check():
    return {"status": "ok",
            "service": settings.project_name,
            "version": "0.1.0"
            }



@app.post(
    "/trips/",
    response_model=schemas.TripRead,
    status_code=status.HTTP_201_CREATED
    )
def create_trip(
    trip_in: schemas.TripCreate,
    db: Session = Depends(get_db)
    ):
    # 创建出差行程
    if trip_in.end_date < trip_in.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date cannot be before start date."
        )

    return crud.create_trip(db=db, trip_in=trip_in)



@app.get(
    "/trips/{trip_id}",
    response_model=schemas.TripRead
    )
def get_trip(
    trip_id: int,
    db: Session = Depends(get_db)
    ):
    # 查询单个出差行程
    trip = crud.get_trip(db=db, trip_id=trip_id)
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found."
        )
    return trip



@app.post(
    "/expenses/",
    response_model=schemas.ExpenseRead,
    status_code=status.HTTP_201_CREATED
    )
def create_expense(
    expense_in: schemas.ExpenseCreate,
    db: Session = Depends(get_db)
    ):
    # 创建消费记录
    trip = crud.get_trip(db=db, trip_id=expense_in.trip_id)
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found."
        )
    if expense_in.expense_date < trip.start_date or expense_in.expense_date > trip.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expense date must be within the trip dates."
        )
    return crud.create_expense(db=db, expense_in=expense_in)



@app.get(
    "/trips/{trip_id}/expenses",
    response_model=List[schemas.ExpenseRead]
    )
def list_expenses_by_trip(
    trip_id: int,
    db: Session = Depends(get_db)
    ):
    # 查询某次出差下的全部消费记录
    trip = crud.get_trip(db=db, trip_id=trip_id)
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found."
        )

    return crud.list_expenses_by_trip(db=db, trip_id=trip_id)



@app.post(
    "/receipts/",
    response_model=schemas.ReceiptRead,
    status_code=status.HTTP_201_CREATED
    )
def create_receipt(
    receipt_in: schemas.ReceiptCreate,
    db: Session = Depends(get_db)
    ):
    # 创建凭证信息
    # mvp：一笔消费最多对应一条凭证记录，后续版本可以支持一笔消费对应多条凭证记录的场景
    expense = crud.get_expense(db=db, expense_id=receipt_in.expense_id)

    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found."
        )

    existing_receipt = crud.get_receipt_by_expense(db=db, expense_id=receipt_in.expense_id)
    if existing_receipt is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A receipt for this expense already exists."
        )

    return crud.create_receipt(db=db, receipt_in=receipt_in)


@app.post(
    "/audit/trips/{trip_id}",
    status_code=status.HTTP_201_CREATED
    )
def audit_trip(
    trip_id: int,
    db: Session = Depends(get_db)
    ):
    trip = crud.get_trip(db=db, trip_id=trip_id)
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found."
        )

    expenses = crud.list_expenses_by_trip(db=db, trip_id=trip_id)
    if not expenses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No expenses found for this trip"
        )

    detail = run_audit_trip(trip=trip, expenses=expenses)
    report = crud.create_audit_report(db=db, report=detail)

    return {
        "report_id": report.id,
        "trip_id": report.trip_id,
        "status": report.status,
        "total_amount": report.total_amount,
        "summary": json.loads(report.summary) if report.summary else None,
        "detail": json.loads(report.detail_json)
    }


@app.post(
    "/agent/audit/trips/{trip_id}",
    status_code=status.HTTP_201_CREATED
    )
def agent_audit_trip(
    trip_id: int,
    db: Session = Depends(get_db)
    ):
    try:
        return run_reimbursement_audit_agent(db=db, trip_id=trip_id)
    except AgentTripNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found"
        )
    except AgentNoExpensesFoundError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No expenses found for this trip"
        )


@app.get("/audit/reports/{report_id}")
def get_audit_report(
    report_id: int,
    db: Session = Depends(get_db)
    ):
    report = crud.get_audit_report(db=db, report_id=report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit report not found"
        )

    return format_audit_report(report)


@app.get("/trips/{trip_id}/audit-reports")
def list_audit_reports_by_trip(
    trip_id: int,
    db: Session = Depends(get_db)
    ):
    trip = crud.get_trip(db=db, trip_id=trip_id)
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found"
        )

    reports = crud.list_audit_reports_by_trip(db=db, trip_id=trip_id)
    return {
        "trip_id": trip_id,
        "count": len(reports),
        "reports": [
            format_audit_report_summary(report)
            for report in reports
        ]
    }


@app.get("/trips/{trip_id}/audit-reports/latest")
def get_latest_audit_report_by_trip(
    trip_id: int,
    db: Session = Depends(get_db)
    ):
    trip = crud.get_trip(db=db, trip_id=trip_id)
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found"
        )

    report = crud.get_latest_audit_report_by_trip(db=db, trip_id=trip_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No audit report found for this trip"
        )

    return format_audit_report(report)



@app.get("/rules/search")
def search_rules(
    query: str = Query(..., min_length = 1),
    top_k: int = Query(5, ge=1, le=20)
    ):
    # 关键词版规则检索接口

    results = rule_rag.search(
        query=query,
        top_k=top_k
    )

    return {
        "query": query,
        "count": len(results),
        "results": results
    }

