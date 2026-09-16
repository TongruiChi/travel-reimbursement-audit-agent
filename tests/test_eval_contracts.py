import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVALS_ROOT = PROJECT_ROOT / "evals"
AUDIT_SCHEMA_PATH = EVALS_ROOT / "contracts" / "audit_case.schema.json"
RAG_SCHEMA_PATH = EVALS_ROOT / "contracts" / "rag_query.schema.json"
AUDIT_DATA_PATH = EVALS_ROOT / "data" / "audit_pilot.jsonl"
RAG_DATA_PATH = EVALS_ROOT / "data" / "rag_pilot.jsonl"
POLICY_PATH = PROJECT_ROOT / "data" / "rules" / "policy_rules.json"
BASELINE_PATH = EVALS_ROOT / "baselines" / "pilot-v1.json"

POLICY_REF = {
    "policy_id": "company-travel-reimbursement",
    "policy_version": "1.0.0",
}
AUDIT_ROOT_KEYS = {
    "schema_version",
    "case_id",
    "name",
    "description",
    "tags",
    "policy",
    "input",
    "label",
}
RAG_ROOT_KEYS = {
    "schema_version",
    "query_id",
    "description",
    "tags",
    "policy",
    "input",
    "label",
}
LABEL_KEYS = {
    "status",
    "candidate_expected",
    "reviewer",
    "reviewed_at",
    "review_notes",
}
AUDIT_STATUSES = {"APPROVED", "NEEDS_REVIEW", "REJECTED"}
EVALUATION_RESULTS = {
    "PASS",
    "VIOLATION",
    "INDETERMINATE",
    "NOT_APPLICABLE",
}


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path):
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    assert raw_lines
    assert all(line.strip() for line in raw_lines)
    return [json.loads(line) for line in raw_lines]


def _semantic_hash(value):
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _policy_rule_ids():
    policy = _load_json(POLICY_PATH)
    return {rule["rule_id"] for rule in policy["rules"]}


def _assert_approved_label(label):
    assert set(label) == LABEL_KEYS
    assert label["status"] == "APPROVED"
    assert isinstance(label["reviewer"], str)
    assert label["reviewer"].strip()
    assert isinstance(label["reviewed_at"], str)
    reviewed_at = datetime.fromisoformat(
        label["reviewed_at"].replace("Z", "+00:00")
    )
    assert reviewed_at.tzinfo is not None
    assert reviewed_at.utcoffset() == timezone.utc.utcoffset(reviewed_at)
    assert isinstance(label["review_notes"], str)
    assert label["review_notes"].strip()


def test_evaluation_schemas_are_strict_approved_label_contracts():
    audit_schema = _load_json(AUDIT_SCHEMA_PATH)
    rag_schema = _load_json(RAG_SCHEMA_PATH)

    for schema in (audit_schema, rag_schema):
        assert schema["$schema"] == (
            "https://json-schema.org/draft/2020-12/schema"
        )
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False

    for schema, label_definition in (
        (audit_schema, "auditLabel"),
        (rag_schema, "ragLabel"),
    ):
        label_contract = schema["$defs"][label_definition]
        properties = label_contract["properties"]
        assert label_contract["additionalProperties"] is False
        assert properties["status"] == {"const": "APPROVED"}
        assert properties["reviewer"] == {
            "type": "string",
            "minLength": 1,
        }
        assert properties["reviewed_at"] == {
            "type": "string",
            "format": "date-time",
        }
        assert properties["review_notes"] == {
            "type": "string",
            "minLength": 1,
        }


def test_audit_pilot_has_twelve_well_formed_approved_cases():
    cases = _load_jsonl(AUDIT_DATA_PATH)
    rule_ids = _policy_rule_ids()

    assert len(cases) == 12
    assert [case["case_id"] for case in cases] == [
        f"AUD-PILOT-{index:03d}" for index in range(1, 13)
    ]

    for case in cases:
        assert set(case) == AUDIT_ROOT_KEYS
        assert case["schema_version"] == "audit_case.v1"
        assert re.fullmatch(r"AUD-PILOT-[0-9]{3}", case["case_id"])
        assert case["name"].strip()
        assert case["description"].strip()
        assert case["tags"] and len(case["tags"]) == len(set(case["tags"]))
        assert case["policy"] == POLICY_REF
        _assert_approved_label(case["label"])

        trip = case["input"]["trip"]
        assert trip["employee_name"].startswith("测试员工")
        assert date.fromisoformat(trip["start_date"]) <= date.fromisoformat(
            trip["end_date"]
        )

        expenses = case["input"]["expenses"]
        expected = case["label"]["candidate_expected"]
        expected_items = expected["items"]
        assert expenses
        assert expected["report_status"] in AUDIT_STATUSES
        assert [expense["id"] for expense in expenses] == [
            item["expense_id"] for item in expected_items
        ]

        for expense in expenses:
            date.fromisoformat(expense["expense_date"])
            assert re.fullmatch(r"[A-Z]{3}", expense["currency"])
            receipt = expense["receipt"]
            if receipt is not None:
                assert receipt["receipt_number"].startswith("SYN-AUD-")

        for item in expected_items:
            assert item["status"] in AUDIT_STATUSES
            assert len(item["flags"]) == len(set(item["flags"]))
            assert set(item["rule_results"]) == rule_ids
            assert set(item["rule_results"].values()) <= EVALUATION_RESULTS


def test_audit_pilot_covers_planned_boundary_and_review_risks():
    cases = _load_jsonl(AUDIT_DATA_PATH)
    tags = {tag for case in cases for tag in case["tags"]}

    assert {
        "boundary:meal:at-limit",
        "boundary:meal:over-limit",
        "boundary:local-traffic:at-limit",
        "boundary:local-traffic:over-limit",
        "boundary:hotel-per-night:at-limit",
        "boundary:hotel-per-night:over-limit",
        "ambiguity:generic-traffic",
        "indeterminate:missing-night-count",
        "indeterminate:foreign-currency",
        "violation:trip-date",
        "violation:missing-receipt",
        "manual-review:other",
    } <= tags


def test_rag_pilot_has_twelve_well_formed_approved_queries():
    queries = _load_jsonl(RAG_DATA_PATH)
    rule_ids = _policy_rule_ids()

    assert len(queries) == 12
    assert [query["query_id"] for query in queries] == [
        f"RAG-PILOT-{index:03d}" for index in range(1, 13)
    ]

    for query in queries:
        assert set(query) == RAG_ROOT_KEYS
        assert query["schema_version"] == "rag_query.v1"
        assert re.fullmatch(r"RAG-PILOT-[0-9]{3}", query["query_id"])
        assert query["description"].strip()
        assert query["tags"] and len(query["tags"]) == len(set(query["tags"]))
        assert query["policy"] == POLICY_REF
        assert query["input"]["query"].strip()
        assert query["input"]["top_k"] > 0
        _assert_approved_label(query["label"])

        candidate = query["label"]["candidate_expected"]
        relevant = candidate["relevant_rule_ids"]
        primary = candidate["primary_rule_id"]
        assert len(relevant) == len(set(relevant))
        assert set(relevant) <= rule_ids
        if primary is None:
            assert relevant == []
        else:
            assert primary in relevant


def test_rag_pilot_covers_every_rule_and_required_query_forms():
    queries = _load_jsonl(RAG_DATA_PATH)
    rule_ids = _policy_rule_ids()
    tags = {tag for query in queries for tag in query["tags"]}
    target_rule_ids = {
        tag.removeprefix("target:")
        for tag in tags
        if tag.startswith("target:")
    }

    assert target_rule_ids == rule_ids
    assert {"form:rule-id", "form:no-space", "outcome:no-relevant-rule"} <= tags
    assert any(
        query["input"]["query"] == "R-HOTEL-001" for query in queries
    )
    assert any(query["input"]["query"] == "住宿超标" for query in queries)
    assert any(
        query["label"]["candidate_expected"]["relevant_rule_ids"] == []
        for query in queries
    )


def test_all_twenty_four_pilot_labels_are_approved():
    records = _load_jsonl(AUDIT_DATA_PATH) + _load_jsonl(RAG_DATA_PATH)

    assert len(records) == 24
    assert {record["label"]["status"] for record in records} == {"APPROVED"}


def test_pilot_v1_baseline_is_versioned_and_matches_datasets():
    baseline = _load_json(BASELINE_PATH)
    audit_cases = _load_jsonl(AUDIT_DATA_PATH)
    rag_queries = _load_jsonl(RAG_DATA_PATH)

    assert baseline["baseline_schema_version"] == "pilot-baseline-summary.v1"
    assert baseline["baseline_id"] == "pilot-v1"
    assert {
        "policy_id": baseline["policy_id"],
        "policy_version": baseline["policy_version"],
    } == POLICY_REF
    assert baseline["audit_dataset"]["path"] == (
        "evals/data/audit_pilot.jsonl"
    )
    assert baseline["rag_dataset"]["path"] == "evals/data/rag_pilot.jsonl"
    assert baseline["audit_dataset"]["approved_cases"] == 12
    assert baseline["rag_dataset"]["approved_queries"] == 12
    assert baseline["audit_dataset"]["sha256"] == hashlib.sha256(
        AUDIT_DATA_PATH.read_bytes()
    ).hexdigest()
    assert baseline["rag_dataset"]["sha256"] == hashlib.sha256(
        RAG_DATA_PATH.read_bytes()
    ).hexdigest()
    assert baseline["golden_semantic_hashes"] == {
        "audit_candidate_expected": (
            "48a1145b51e6018410db88dd6908661a17e899065872b35c274f0514a7cb3b9c"
        ),
        "audit_final_statuses": (
            "083c1283af6235713c6467be268183f164a8734cb66fb72ccef5edf01444a735"
        ),
        "rag_primary_rules": (
            "48270a5e6c1bb41a293353a168859ad1f35fff5b1c702ace75f264c60c95683a"
        ),
        "rag_relevant_rule_sets": (
            "a6107da09a6306f69c09b522029a0c3a4a0b727df9856f00aa992bfb9a73bee2"
        ),
    }
    assert baseline["golden_semantic_hashes"] == {
        "audit_candidate_expected": _semantic_hash(
            [
                {
                    "case_id": case["case_id"],
                    "candidate_expected": case["label"]["candidate_expected"],
                }
                for case in audit_cases
            ]
        ),
        "audit_final_statuses": _semantic_hash(
            [
                {
                    "case_id": case["case_id"],
                    "report_status": case["label"]["candidate_expected"][
                        "report_status"
                    ],
                    "item_statuses": [
                        item["status"]
                        for item in case["label"]["candidate_expected"][
                            "items"
                        ]
                    ],
                }
                for case in audit_cases
            ]
        ),
        "rag_primary_rules": _semantic_hash(
            [
                {
                    "query_id": query["query_id"],
                    "primary_rule_id": query["label"]["candidate_expected"][
                        "primary_rule_id"
                    ],
                }
                for query in rag_queries
            ]
        ),
        "rag_relevant_rule_sets": _semantic_hash(
            [
                {
                    "query_id": query["query_id"],
                    "relevant_rule_ids": query["label"]["candidate_expected"][
                        "relevant_rule_ids"
                    ],
                }
                for query in rag_queries
            ]
        ),
    }
