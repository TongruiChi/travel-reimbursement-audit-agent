import pytest

from evals.runner import _approved_records


def test_runner_scores_only_approved_records_and_counts_skips():
    records = [
        {"case_id": "approved", "label": {"status": "APPROVED"}},
        {"case_id": "pending", "label": {"status": "PENDING_REVIEW"}},
        {
            "case_id": "clarification",
            "label": {"status": "PENDING_POLICY_CLARIFICATION"},
        },
    ]

    approved, skipped_count = _approved_records(records)

    assert [record["case_id"] for record in approved] == ["approved"]
    assert skipped_count == 2


def test_runner_fails_fast_when_no_record_is_approved():
    records = [
        {"case_id": "pending", "label": {"status": "PENDING_REVIEW"}},
    ]

    with pytest.raises(ValueError, match="no APPROVED records"):
        _approved_records(records)
