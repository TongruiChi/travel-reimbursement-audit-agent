import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.audit_engine import EVALUATORS, audit_expense
from app.config import settings
from app.policy import (
    Enforcement,
    EvaluationResult,
    PolicyRegistry,
    PolicyThreshold,
    Severity,
    ThresholdBasis,
    ThresholdComparison,
    policy_registry,
)
from app.rag import rule_rag
from scripts.generate_policy_markdown import main as generator_main
from scripts.generate_policy_markdown import render_policy_markdown


POLICY_PATH = Path(settings.policy_rules_path)


def _trip():
    return SimpleNamespace(
        id=1,
        start_date=date(2026, 5, 20),
        end_date=date(2026, 5, 23),
        destination="上海",
    )


def _expense(
    *,
    category="餐饮",
    amount=100.0,
    currency="CNY",
    receipt=object(),
):
    return SimpleNamespace(
        id=1,
        expense_date=date(2026, 5, 21),
        category=category,
        amount=amount,
        currency=currency,
        merchant="测试商户",
        description="测试费用",
        receipt=receipt,
    )


def _rule_result(item, rule_id):
    return next(
        result for result in item["rule_results"] if result["rule_id"] == rule_id
    )


def _legacy_flag_names(item):
    return {flag["flag"] for flag in item["flags"]}


def _registry_with_threshold(tmp_path, rule_id, amount):
    policy_data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    target_rule = next(
        rule for rule in policy_data["rules"] if rule["rule_id"] == rule_id
    )
    target_rule["threshold"]["amount"] = amount
    custom_path = tmp_path / "policy_rules.json"
    custom_path.write_text(
        json.dumps(policy_data, ensure_ascii=False),
        encoding="utf-8",
    )
    return PolicyRegistry(custom_path)


def _write_policy_data(tmp_path, policy_data):
    custom_path = tmp_path / "invalid_policy_rules.json"
    custom_path.write_text(
        json.dumps(policy_data, ensure_ascii=False),
        encoding="utf-8",
    )
    return custom_path


def test_policy_contains_exactly_ten_unique_rules():
    rule_ids = [rule.rule_id for rule in policy_registry.rules]

    assert len(rule_ids) == 10
    assert len(rule_ids) == len(set(rule_ids))


def test_policy_document_metadata_and_nullable_effective_date():
    assert policy_registry.policy_id == "company-travel-reimbursement"
    assert policy_registry.policy_version == "1.0.0"
    assert policy_registry.document.effective_date is None
    assert policy_registry.document.currency == "CNY"


def test_enforcement_mapping_matches_audited_capabilities():
    grouped = {
        enforcement: {
            rule.rule_id
            for rule in policy_registry.rules
            if rule.enforcement == enforcement
        }
        for enforcement in Enforcement
    }

    assert grouped[Enforcement.ENFORCED] == {
        "R-GEN-001",
        "R-GEN-003",
        "R-MEAL-001",
    }
    assert grouped[Enforcement.PARTIAL] == {
        "R-GEN-002",
        "R-TRAFFIC-002",
        "R-HOTEL-001",
        "R-HOTEL-002",
        "R-MEAL-002",
        "R-OTHER-001",
    }
    assert grouped[Enforcement.EVIDENCE_ONLY] == {"R-TRAFFIC-001"}


def test_severity_is_valid_and_nullable_when_source_has_no_basis():
    valid_severities = set(Severity)
    assert all(
        rule.severity is None or rule.severity in valid_severities
        for rule in policy_registry.rules
    )
    assert policy_registry.get("R-TRAFFIC-001").severity is None
    assert policy_registry.get("R-HOTEL-002").severity is None
    assert policy_registry.get("R-MEAL-002").severity is None


def test_threshold_validation_and_business_values():
    thresholds = {
        rule.rule_id: rule.threshold.amount
        for rule in policy_registry.rules
        if rule.threshold is not None
    }
    assert thresholds == {
        "R-GEN-003": 0,
        "R-TRAFFIC-002": 300,
        "R-HOTEL-001": 800,
        "R-MEAL-001": 150,
    }

    with pytest.raises(ValidationError):
        PolicyThreshold(
            amount=-1,
            comparison=ThresholdComparison.LTE,
            basis=ThresholdBasis.PER_EXPENSE,
        )


def test_enforced_rules_have_registered_evaluators():
    enforced_rules = [
        rule
        for rule in policy_registry.rules
        if rule.enforcement == Enforcement.ENFORCED
    ]

    assert all(rule.evaluator is not None for rule in enforced_rules)
    assert all(
        rule.evaluator is None or rule.evaluator in EVALUATORS
        for rule in policy_registry.rules
    )


def test_unknown_evaluator_fails_policy_loading(tmp_path):
    policy_data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    policy_data["rules"][0]["evaluator"] = "unknown_evaluator"

    with pytest.raises(ValidationError):
        PolicyRegistry(_write_policy_data(tmp_path, policy_data))


def test_rag_uses_policy_registry_and_exact_rule_id_search():
    assert rule_rag.registry is policy_registry
    exact_ids = [
        item["rule"]["rule_id"]
        for item in rule_rag.search("R-HOTEL-001", top_k=3)
    ]

    assert exact_ids == ["R-HOTEL-001"]
    assert rule_rag.search("长途客运", top_k=3)[0]["rule"]["rule_id"] == (
        "R-TRAFFIC-001"
    )


def test_amount_threshold_originates_from_registry(tmp_path):
    expense = _expense(amount=175)
    default_item = audit_expense(_trip(), expense)
    custom_registry = _registry_with_threshold(tmp_path, "R-MEAL-001", 200)
    custom_item = audit_expense(_trip(), expense, registry=custom_registry)

    assert _rule_result(default_item, "R-MEAL-001")["result"] == (
        EvaluationResult.VIOLATION.value
    )
    assert _rule_result(custom_item, "R-MEAL-001")["result"] == (
        EvaluationResult.PASS.value
    )


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (150, EvaluationResult.PASS.value),
        (150.01, EvaluationResult.VIOLATION.value),
    ],
)
def test_meal_boundary_comes_from_policy(amount, expected):
    item = audit_expense(_trip(), _expense(category="餐饮", amount=amount))
    assert _rule_result(item, "R-MEAL-001")["result"] == expected


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (300, EvaluationResult.PASS.value),
        (300.01, EvaluationResult.VIOLATION.value),
    ],
)
def test_local_transport_boundary_comes_from_policy(amount, expected):
    item = audit_expense(_trip(), _expense(category="市内出行", amount=amount))
    assert _rule_result(item, "R-TRAFFIC-002")["result"] == expected


def test_generic_transport_does_not_apply_local_transport_threshold():
    item = audit_expense(_trip(), _expense(category="交通", amount=999))

    assert _rule_result(item, "R-TRAFFIC-002")["result"] == (
        EvaluationResult.INDETERMINATE.value
    )
    assert "LOCAL_TRAFFIC_AMOUNT_HIGH" not in _legacy_flag_names(item)


def test_hotel_without_night_count_is_indeterminate():
    item = audit_expense(_trip(), _expense(category="住宿", amount=920))

    assert _rule_result(item, "R-HOTEL-001")["result"] == (
        EvaluationResult.INDETERMINATE.value
    )
    assert "HOTEL_AMOUNT_EXCEED_LIMIT" not in _legacy_flag_names(item)


def test_foreign_currency_threshold_is_indeterminate():
    item = audit_expense(
        _trip(),
        _expense(category="餐饮", amount=999, currency="USD"),
    )

    assert _rule_result(item, "R-MEAL-001")["result"] == (
        EvaluationResult.INDETERMINATE.value
    )
    assert "MEAL_AMOUNT_EXCEED_LIMIT" not in _legacy_flag_names(item)


def test_missing_receipt_is_a_violation():
    item = audit_expense(_trip(), _expense(receipt=None))

    assert _rule_result(item, "R-GEN-002")["result"] == (
        EvaluationResult.VIOLATION.value
    )
    assert "RECEIPT_MISSING" in _legacy_flag_names(item)


def test_existing_receipt_does_not_prove_validity():
    item = audit_expense(_trip(), _expense(receipt=object()))

    assert _rule_result(item, "R-GEN-002")["result"] == (
        EvaluationResult.INDETERMINATE.value
    )
    assert "RECEIPT_MISSING" not in _legacy_flag_names(item)
    assert all(
        result["policy_version"] == policy_registry.policy_version
        for result in item["rule_results"]
    )


def test_markdown_generation_is_deterministic_and_contains_all_rules():
    first = render_policy_markdown(policy_registry.document)
    second = render_policy_markdown(policy_registry.document)

    assert first.encode("utf-8") == second.encode("utf-8")
    assert all(rule.rule_id in first for rule in policy_registry.rules)


def test_generator_check_matches_committed_markdown():
    assert generator_main(["--check"]) == 0
