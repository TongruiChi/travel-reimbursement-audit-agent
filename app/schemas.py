import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TripBase(BaseModel):
    employee_name: str = Field(..., min_length=1, max_length=100)
    department: Optional[str] = Field(default=None, max_length=100)

    origin: str = Field(..., min_length=1, max_length=100)
    destination: str = Field(..., min_length=1, max_length=100)

    start_date: datetime.date
    end_date: datetime.date

    purpose: Optional[str] = Field(default=None, max_length=1000)


class TripCreate(TripBase):
    pass


class TripRead(TripBase):
    id: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class ExpenseBase(BaseModel):
    trip_id: int
    expense_date: datetime.date
    category: str = Field(..., min_length=1, max_length=50)
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=20)

    merchant: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseRead(ExpenseBase):
    id: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class ReceiptBase(BaseModel):
    expense_id: int

    receipt_type: str = Field(..., min_length=1, max_length=50)
    receipt_number: Optional[str] = Field(default=None, max_length=100)
    file_url: Optional[str] = Field(default=None, max_length=500)

    issued_date: Optional[datetime.date] = None
    seller_name: Optional[str] = Field(default=None, max_length=200)

    amount: float = Field(..., gt=0)
    merchant: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)


class ReceiptCreate(ReceiptBase):
    pass


class ReceiptRead(ReceiptBase):
    id: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class AuditReportBase(BaseModel):
    trip_id: int
    status: str = Field(..., min_length=1, max_length=50)
    total_amount: float = Field(default=0.0, ge=0)
    summary: Optional[str] = None
    detail_json: str


class AuditReportCreate(AuditReportBase):
    pass


class AuditReportRead(AuditReportBase):
    id: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True
