import json
from typing import Any, Dict, Optional


def _parse_json_field(value: Optional[str], fallback_key: str) -> Any:
    if value is None:
        return None

    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        return {
            fallback_key: value,
            "parse_error": str(exc),
        }


def parse_report_detail(detail_json: str) -> Dict[str, Any]:
    detail = _parse_json_field(detail_json, "raw_detail_json")
    if isinstance(detail, dict):
        return detail
    return {
        "raw_detail_json": detail_json,
        "parse_error": "Parsed detail_json is not a JSON object.",
    }


def _parse_report_summary(summary: Optional[str]) -> Any:
    return _parse_json_field(summary, "raw_summary")


def _format_created_at(report: Any) -> Optional[str]:
    created_at = getattr(report, "created_at", None)
    if created_at is None:
        return None
    return created_at.isoformat()


def format_audit_report(report: Any) -> Dict[str, Any]:
    return {
        "report_id": report.id,
        "trip_id": report.trip_id,
        "status": report.status,
        "total_amount": report.total_amount,
        "summary": _parse_report_summary(report.summary),
        "detail": parse_report_detail(report.detail_json),
        "created_at": _format_created_at(report),
    }


def format_audit_report_summary(report: Any) -> Dict[str, Any]:
    return {
        "report_id": report.id,
        "trip_id": report.trip_id,
        "status": report.status,
        "total_amount": report.total_amount,
        "summary": _parse_report_summary(report.summary),
        "created_at": _format_created_at(report),
    }
