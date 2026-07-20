import json
from datetime import datetime, timezone
from types import SimpleNamespace

from app.reporting import (
    format_audit_report,
    format_audit_report_summary,
    parse_report_detail,
)


def test_parse_report_detail_with_valid_json():
    detail = parse_report_detail('{"status": "REJECTED", "items": []}')

    assert detail["status"] == "REJECTED"
    assert detail["items"] == []


def test_parse_report_detail_with_invalid_json_does_not_raise():
    detail = parse_report_detail("{invalid json")

    assert detail["raw_detail_json"] == "{invalid json"
    assert "parse_error" in detail


def test_format_audit_report_and_summary():
    report = SimpleNamespace(
        id=1,
        trip_id=1,
        status="REJECTED",
        total_amount=1663.5,
        summary=json.dumps({"expense_count": 6}),
        detail_json=json.dumps({"status": "REJECTED", "items": []}),
        created_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
    )

    full = format_audit_report(report)
    summary = format_audit_report_summary(report)

    assert set(full.keys()) >= {
        "report_id",
        "trip_id",
        "status",
        "total_amount",
        "summary",
        "detail",
        "created_at",
    }
    assert full["detail"]["status"] == "REJECTED"
    assert summary["report_id"] == 1
    assert "detail" not in summary
