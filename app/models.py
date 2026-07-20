import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, TEXT
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class Trip(Base):
    # 出差行程表
    # 表示一次完整的出差行程，包括多个报销项
    __tablename__ = "trips"

    # id = Column(Integer, primary_key=True, index=True)
    # start_date = Column(Date, nullable=False)
    # end_date = Column(Date, nullable=False)

    id:Mapped[int] = mapped_column(Integer, primary_key=True)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    employee_name = Column(String(100), nullable=False, index=True)
    department = Column(String(100), nullable=True)

    origin = Column(String(100), nullable=False)
    destination = Column(String(100), nullable=False)



    purpose = Column(TEXT, nullable=True)

    created_at = Column(DateTime, default=_utc_now, nullable=False)

    expenses = relationship(
        "Expense",
        back_populates="trip",
        cascade="all, delete-orphan"
        )

    audit_reports = relationship(
        "AuditReport",
        back_populates="trip",
        cascade="all, delete-orphan"
        )



class Expense(Base):
    # 报销项表
    # 表示一次出差行程中的一个具体的报销项，如机票、酒店、餐饮等
    __tablename__ = "expenses"

    # id = Column(Integer, primary_key=True, index=True)
    # expense_date = Column(Date, nullable=False)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expense_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)

    currency = Column(String(20), default="CNY", nullable=False)
    category = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)

    merchant = Column(String(200), nullable=True)
    description = Column(TEXT, nullable=True)

    created_at = Column(DateTime, default=_utc_now, nullable=False)

    trip = relationship(
        "Trip",
        back_populates="expenses",
        uselist=False
        )
    receipt = relationship(
        "Receipt",
        back_populates="expenses",
    )



class Receipt(Base):
    # 凭证信息表
    # 表示某笔消费的凭证信息，如支付截图、电子凭证发票号码、日期、金额等
    # 当前mvp版本不处理真实图片上传，只保存mock凭证信息，后续版本可以增加图片上传和存储功能


    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)

    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=False, unique=True)

    receipt_type = Column(String(50), nullable=False)  # 支付截图、电子发票等
    receipt_number = Column(String(100), nullable=True)  # 电子发票号码等凭证编号
    file_url = Column(String(500), nullable=True)  # 凭证图片URL，mvp阶段不处理真实图片上传，后续版本可以增加图片上传和存储功能


    issued_date = Column(Date, nullable=True)  # 电子发票的开具日期等凭证相关日期
    seller_name = Column(String(200), nullable=True)  # 销售方名称等凭证相关信息

    amount = Column(Float, nullable=False)

    merchant = Column(String(200), nullable=True)
    description = Column(TEXT, nullable=True)

    created_at = Column(DateTime, default=_utc_now, nullable=False)

    expenses = relationship(
        "Expense",
        back_populates="receipt",
        uselist=False
        )



class AuditReport(Base):
    # 审核报告表
    # 表示一次出差行程的审核结果，包括审核意见、风险提示等信息
    # mvp阶段先将审核报告内容保存为文本，后续版本可以增加结构化的审核结果字段，如风险等级、违规类型等，以便更好地支持后续的数据分析和风险管理功能


    __tablename__ = "audit_reports"

    id = Column(Integer, primary_key=True, index=True)

    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False, index=True)

    status = Column(String(50), nullable=False)  # 审核状态，如approved、rejected、pending等
    total_amount = Column(Float, nullable=False, default=0.0)  # 出差行程的总金额

    # report_content = Column(TEXT, nullable=False)  # 审核报告内容，包含审核意见、风险提示等信息
    summary = Column(TEXT, nullable=True)
    detail_json = Column(TEXT, nullable=False)  # detail_json字段保存结构化的审核结果数据，包含审核意见、风险提示等信息，以JSON格式存储，便于后续的数据分析和风险管理功能


    created_at = Column(DateTime, default=_utc_now, nullable=False)

    trip = relationship(
        "Trip",
        back_populates="audit_reports",
        uselist=False
        )
