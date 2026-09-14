import json
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import settings


class Enforcement(str, Enum):
    ENFORCED = "ENFORCED"
    PARTIAL = "PARTIAL"
    EVIDENCE_ONLY = "EVIDENCE_ONLY"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvaluationResult(str, Enum):
    PASS = "PASS"
    VIOLATION = "VIOLATION"
    INDETERMINATE = "INDETERMINATE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ThresholdComparison(str, Enum):
    GT = "GT"
    LTE = "LTE"


class ThresholdBasis(str, Enum):
    PER_EXPENSE = "PER_EXPENSE"
    PER_NIGHT = "PER_NIGHT"


class EvaluatorName(str, Enum):
    EXPENSE_DATE_WITHIN_TRIP = "expense_date_within_trip"
    POSITIVE_AMOUNT = "positive_amount"
    AMOUNT_THRESHOLD = "amount_threshold"
    RECEIPT_PRESENCE = "receipt_presence"
    MANUAL_REVIEW = "manual_review"


class PolicyThreshold(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    amount: float = Field(..., ge=0)
    comparison: ThresholdComparison
    basis: ThresholdBasis


class PolicyRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str = Field(..., min_length=1)
    category: list[str] = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    enforcement: Enforcement
    severity: Optional[Severity] = None
    evaluator: Optional[EvaluatorName] = None
    keywords: list[str] = Field(default_factory=list)
    flag: Optional[str] = None
    violation_message: Optional[str] = None
    threshold: Optional[PolicyThreshold] = None
    applicable_cities: Optional[list[str]] = None
    evaluable_categories: Optional[list[str]] = None

    @model_validator(mode="after")
    def validate_execution_contract(self) -> "PolicyRule":
        if self.enforcement == Enforcement.ENFORCED and self.evaluator is None:
            raise ValueError("ENFORCED rules must define an evaluator")

        threshold_evaluators = {
            EvaluatorName.POSITIVE_AMOUNT,
            EvaluatorName.AMOUNT_THRESHOLD,
        }
        if self.evaluator in threshold_evaluators and self.threshold is None:
            raise ValueError(
                f"Rule {self.rule_id} uses {self.evaluator.value} without a threshold"
            )

        if self.evaluable_categories is not None:
            unknown_categories = set(self.evaluable_categories) - set(self.category)
            if unknown_categories:
                raise ValueError(
                    f"Rule {self.rule_id} has evaluable categories outside category"
                )

        return self


class PolicyDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str = Field(..., min_length=1)
    policy_version: str = Field(..., min_length=1)
    effective_date: Optional[date] = None
    currency: str = Field(..., min_length=3, max_length=3)
    rules: list[PolicyRule] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_unique_rule_ids(self) -> "PolicyDocument":
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Policy rule IDs must be unique")
        return self


class PolicyRegistry:
    def __init__(self, policy_path: str | Path):
        self.policy_path = Path(policy_path)
        if not self.policy_path.exists():
            raise FileNotFoundError(f"Policy file not found: {self.policy_path}")

        raw_document = json.loads(self.policy_path.read_text(encoding="utf-8"))
        self.document = PolicyDocument.model_validate(raw_document)
        self._rules_by_id = {rule.rule_id: rule for rule in self.document.rules}

    @property
    def policy_id(self) -> str:
        return self.document.policy_id

    @property
    def policy_version(self) -> str:
        return self.document.policy_version

    @property
    def rules(self) -> tuple[PolicyRule, ...]:
        return tuple(self.document.rules)

    def get(self, rule_id: str) -> PolicyRule:
        try:
            return self._rules_by_id[rule_id]
        except KeyError as exc:
            raise KeyError(f"Unknown policy rule: {rule_id}") from exc

    def rules_for_category(self, category: str) -> tuple[PolicyRule, ...]:
        return tuple(
            rule
            for rule in self.document.rules
            if "ALL" in rule.category or category in rule.category
        )


policy_registry = PolicyRegistry(settings.policy_rules_path)
