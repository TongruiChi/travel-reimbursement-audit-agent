from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from app.audit_engine import audit_trip
from app.policy import policy_registry
from app.rag import rule_rag
from evals.metrics import (
    FINAL_STATES,
    RULE_STATES,
    appropriate_abstention_rate,
    automation_coverage,
    categorical_metrics,
    determinate_accuracy,
    exact_match_metrics,
    mean_reciprocal_rank,
    negative_no_result_accuracy,
    recall_at_k,
    set_recall_at_k,
    violation_metrics,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_CASES = PROJECT_ROOT / "evals" / "data" / "audit_pilot.jsonl"
DEFAULT_RAG_QUERIES = PROJECT_ROOT / "evals" / "data" / "rag_pilot.jsonl"
DEFAULT_ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "evals"
EVAL_VERSION = "golden-eval-v1"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def resolve_output_directory(output: str | Path | None, run_id: str) -> Path:
    if output is None:
        return DEFAULT_ARTIFACT_ROOT / run_id
    output_path = Path(output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    return output_path


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
    return records


def _review_status(record: dict[str, Any]) -> str | None:
    label = record.get("label", {})
    return label.get("review_status", label.get("status"))


def _approved_records(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    approved = [record for record in records if _review_status(record) == "APPROVED"]
    skipped_count = len(records) - len(approved)
    if not approved:
        raise ValueError("Evaluation dataset contains no APPROVED records")
    return approved, skipped_count


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _dataset_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _base_metadata(
    *,
    report_schema_version: str,
    run_id: str,
    dataset_path: Path,
    records: list[dict[str, Any]],
    scored_count: int,
    skipped_count: int,
) -> dict[str, Any]:
    return {
        "eval_version": EVAL_VERSION,
        "schema_version": report_schema_version,
        "dataset_schema_versions": sorted(
            {record["schema_version"] for record in records}
        ),
        "policy_id": policy_registry.policy_id,
        "policy_version": policy_registry.policy_version,
        "git_commit": _run_git("rev-parse", "HEAD"),
        "worktree_dirty": bool(_run_git("status", "--porcelain")),
        "timestamp_utc": utc_timestamp(),
        "run_id": run_id,
        "dataset_path": _dataset_path(dataset_path),
        "dataset_sha256": _file_sha256(dataset_path),
        "python_version": platform.python_version(),
        "scored_count": scored_count,
        "skipped_count": skipped_count,
    }


def _audit_objects(case: dict[str, Any]) -> tuple[Any, list[Any]]:
    trip_data = dict(case["input"]["trip"])
    trip_data["start_date"] = date.fromisoformat(trip_data["start_date"])
    trip_data["end_date"] = date.fromisoformat(trip_data["end_date"])
    trip = SimpleNamespace(**trip_data)

    expenses = []
    for source in case["input"]["expenses"]:
        expense_data = dict(source)
        expense_data["expense_date"] = date.fromisoformat(
            expense_data["expense_date"]
        )
        receipt = expense_data.get("receipt")
        if receipt is not None:
            expense_data["receipt"] = SimpleNamespace(**receipt)
        expenses.append(SimpleNamespace(**expense_data))
    return trip, expenses


def build_audit_report(
    dataset_path: str | Path = DEFAULT_AUDIT_CASES,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    path = Path(dataset_path).resolve()
    records = _load_jsonl(path)
    approved, skipped_count = _approved_records(records)
    selected_run_id = run_id or make_run_id()

    expected_results: list[str] = []
    actual_results: list[str] = []
    per_rule_values: dict[str, dict[str, list[str]]] = {
        rule.rule_id: {"expected": [], "actual": []}
        for rule in policy_registry.rules
    }
    expected_final_statuses: list[str] = []
    actual_final_statuses: list[str] = []
    case_exact_matches: list[bool] = []
    case_results = []
    rule_mismatches = []
    final_status_mismatches = []

    for case in approved:
        trip, expenses = _audit_objects(case)
        actual_report = audit_trip(trip, expenses)
        expected_report = case["label"]["candidate_expected"]
        actual_items = {
            item["expense_id"]: item for item in actual_report["items"]
        }

        case_rule_match = True
        for expected_item in expected_report["items"]:
            expense_id = expected_item["expense_id"]
            if expense_id not in actual_items:
                raise ValueError(
                    f"Missing actual expense {expense_id} for {case['case_id']}"
                )
            actual_by_rule = {
                result["rule_id"]: result["result"]
                for result in actual_items[expense_id]["rule_results"]
            }
            if set(actual_by_rule) != set(expected_item["rule_results"]):
                raise ValueError(
                    f"Rule ID set differs for {case['case_id']} expense {expense_id}"
                )

            for rule_id, expected_value in expected_item["rule_results"].items():
                actual_value = actual_by_rule[rule_id]
                expected_results.append(expected_value)
                actual_results.append(actual_value)
                per_rule_values[rule_id]["expected"].append(expected_value)
                per_rule_values[rule_id]["actual"].append(actual_value)
                if expected_value != actual_value:
                    case_rule_match = False
                    rule_mismatches.append(
                        {
                            "case_id": case["case_id"],
                            "expense_id": expense_id,
                            "rule_id": rule_id,
                            "expected": expected_value,
                            "actual": actual_value,
                        }
                    )

        expected_status = expected_report["report_status"]
        actual_status = actual_report["status"]
        expected_final_statuses.append(expected_status)
        actual_final_statuses.append(actual_status)
        final_match = expected_status == actual_status
        if not final_match:
            final_status_mismatches.append(
                {
                    "case_id": case["case_id"],
                    "expected_status": expected_status,
                    "actual_status": actual_status,
                }
            )

        exact_match = case_rule_match and final_match
        case_exact_matches.append(exact_match)
        case_results.append(
            {
                "case_id": case["case_id"],
                "expected_status": expected_status,
                "actual_status": actual_status,
                "exact_match": exact_match,
            }
        )

    per_rule = []
    for rule in policy_registry.rules:
        values = per_rule_values[rule.rule_id]
        categorical = categorical_metrics(
            values["expected"],
            values["actual"],
            RULE_STATES,
        )
        violation = violation_metrics(values["expected"], values["actual"])
        per_rule.append(
            {
                "rule_id": rule.rule_id,
                "support": categorical["support"],
                "four_state_accuracy": categorical["accuracy"],
                "violation_precision": violation["precision"],
                "violation_recall": violation["recall"],
                "violation_f1": violation["f1"],
                "violation_counts": {
                    key: violation[key] for key in ("tp", "fp", "fn", "tn")
                },
            }
        )

    metadata = _base_metadata(
        report_schema_version="audit-eval-report.v1",
        run_id=selected_run_id,
        dataset_path=path,
        records=records,
        scored_count=len(approved),
        skipped_count=skipped_count,
    )
    metadata["evaluator_id"] = "deterministic-audit-v1"

    return {
        "metadata": metadata,
        "metrics": {
            "violation": violation_metrics(expected_results, actual_results),
            "four_state_rule_accuracy": categorical_metrics(
                expected_results,
                actual_results,
                RULE_STATES,
            ),
            "final_decision_accuracy": categorical_metrics(
                expected_final_statuses,
                actual_final_statuses,
                FINAL_STATES,
            ),
            "exact_match_rate": exact_match_metrics(case_exact_matches),
            "automation_coverage": automation_coverage(
                expected_results,
                actual_results,
            ),
            "determinate_accuracy": determinate_accuracy(
                expected_results,
                actual_results,
            ),
            "appropriate_abstention_rate": appropriate_abstention_rate(
                expected_results,
                actual_results,
            ),
            "per_rule": per_rule,
        },
        "failures": {
            "rule_mismatches": rule_mismatches,
            "final_status_mismatches": final_status_mismatches,
        },
        "cases": case_results,
    }


def build_rag_report(
    dataset_path: str | Path = DEFAULT_RAG_QUERIES,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    path = Path(dataset_path).resolve()
    records = _load_jsonl(path)
    approved, skipped_count = _approved_records(records)
    selected_run_id = run_id or make_run_id()
    requested_ranking_depth = len(policy_registry.rules)

    relevant_sets: list[list[str]] = []
    retrieved_rankings: list[list[str]] = []
    query_results = []
    failures = []

    for record in approved:
        query = record["input"]["query"]
        relevant = list(
            record["label"]["candidate_expected"]["relevant_rule_ids"]
        )
        search_results = rule_rag.search(query, top_k=requested_ranking_depth)
        retrieved = [item["rule"]["rule_id"] for item in search_results]
        relevant_sets.append(relevant)
        retrieved_rankings.append(retrieved)

        if relevant:
            relevant_set = set(relevant)
            hit_at_1 = bool(relevant_set.intersection(retrieved[:1]))
            hit_at_3 = bool(relevant_set.intersection(retrieved[:3]))
            query_set_recall = (
                len(relevant_set.intersection(retrieved[:3])) / len(relevant_set)
            )
            first_rank = next(
                (
                    index
                    for index, rule_id in enumerate(retrieved, start=1)
                    if rule_id in relevant_set
                ),
                None,
            )
            reciprocal_rank = 0.0 if first_rank is None else 1 / first_rank
            negative_success = None
            failed = not hit_at_3 or query_set_recall < 1.0
        else:
            hit_at_1 = None
            hit_at_3 = None
            query_set_recall = None
            reciprocal_rank = None
            negative_success = retrieved == []
            failed = not negative_success

        detail = {
            "query_id": record["query_id"],
            "query": query,
            "configured_top_k": record["input"]["top_k"],
            "requested_ranking_depth": requested_ranking_depth,
            "relevant_rule_ids": relevant,
            "retrieved_rule_ids": retrieved,
            "hit_at_1": hit_at_1,
            "hit_at_3": hit_at_3,
            "set_recall_at_3": query_set_recall,
            "reciprocal_rank": reciprocal_rank,
            "negative_success": negative_success,
        }
        query_results.append(detail)
        if failed:
            failures.append(detail)

    recall_1 = recall_at_k(relevant_sets, retrieved_rankings, 1)
    recall_3 = recall_at_k(relevant_sets, retrieved_rankings, 3)
    set_recall_3 = set_recall_at_k(relevant_sets, retrieved_rankings, 3)
    mrr = mean_reciprocal_rank(relevant_sets, retrieved_rankings)
    negative_accuracy = negative_no_result_accuracy(
        relevant_sets,
        retrieved_rankings,
    )

    metadata = _base_metadata(
        report_schema_version="rag-eval-report.v1",
        run_id=selected_run_id,
        dataset_path=path,
        records=records,
        scored_count=len(approved),
        skipped_count=skipped_count,
    )
    metadata["retriever_id"] = "keyword-v1"
    metadata["positive_query_count"] = sum(bool(item) for item in relevant_sets)
    metadata["negative_query_count"] = sum(not item for item in relevant_sets)
    metadata["requested_ranking_depth"] = requested_ranking_depth

    return {
        "metadata": metadata,
        "metrics": {
            "recall_at_1": recall_1,
            "recall_at_3": recall_3,
            "set_recall_at_3": set_recall_3,
            "mrr": mrr,
            "negative_no_result_accuracy": negative_accuracy,
        },
        "failures": failures,
        "queries": query_results,
    }


def _metric(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.4f} ({value:.2%})"


def _markdown_matrix(metric: dict[str, Any]) -> list[str]:
    labels = metric["labels"]
    lines = [
        "| Expected \\ Actual | " + " | ".join(labels) + " | Support |",
        "|---|" + "---:|" * (len(labels) + 1),
    ]
    matrix = metric["confusion_matrix"]
    for expected_label in labels:
        row = matrix[expected_label]
        support = sum(row.values())
        values = " | ".join(str(row[actual_label]) for actual_label in labels)
        lines.append(f"| {expected_label} | {values} | {support} |")
    return lines


def audit_markdown(report: dict[str, Any]) -> str:
    metadata = report["metadata"]
    metrics = report["metrics"]
    violation = metrics["violation"]
    lines = [
        "# Audit Golden Evaluation Report",
        "",
        "## Metadata",
        "",
        f"- Run ID: `{metadata['run_id']}`",
        f"- Timestamp UTC: `{metadata['timestamp_utc']}`",
        f"- Evaluator: `{metadata['evaluator_id']}`",
        f"- Policy: `{metadata['policy_id']}` v`{metadata['policy_version']}`",
        f"- Git commit: `{metadata['git_commit']}`",
        f"- Worktree dirty: `{str(metadata['worktree_dirty']).lower()}`",
        f"- Dataset: `{metadata['dataset_path']}`",
        f"- Dataset SHA-256: `{metadata['dataset_sha256']}`",
        f"- Cases scored: {metadata['scored_count']}",
        f"- Cases skipped: {metadata['skipped_count']}",
        "",
        "## Summary",
        "",
        "| Metric | Value | Support |",
        "|---|---:|---:|",
        f"| Violation Precision | {_metric(violation['precision'])} | {violation['predicted_violation_support']} |",
        f"| Violation Recall | {_metric(violation['recall'])} | {violation['expected_violation_support']} |",
        f"| Violation F1 | {_metric(violation['f1'])} | {violation['expected_violation_support']} expected / {violation['predicted_violation_support']} predicted violations |",
        f"| Four-state Accuracy | {_metric(metrics['four_state_rule_accuracy']['accuracy'])} | {metrics['four_state_rule_accuracy']['support']} |",
        f"| Final Decision Accuracy | {_metric(metrics['final_decision_accuracy']['accuracy'])} | {metrics['final_decision_accuracy']['support']} |",
        f"| Exact Match Rate | {_metric(metrics['exact_match_rate']['rate'])} | {metrics['exact_match_rate']['support']} |",
        f"| Automation Coverage | {_metric(metrics['automation_coverage']['rate'])} | {metrics['automation_coverage']['applicable_support']} |",
        f"| Determinate Accuracy | {_metric(metrics['determinate_accuracy']['accuracy'])} | {metrics['determinate_accuracy']['determinate_support']} |",
        f"| Appropriate Abstention Rate | {_metric(metrics['appropriate_abstention_rate']['rate'])} | {metrics['appropriate_abstention_rate']['expected_indeterminate_support']} |",
        "",
        "## Violation Unit Counts",
        "",
        f"- Total rule units: {violation['total_rule_units']}",
        f"- Expected violation units: {violation['expected_violation_support']}",
        f"- Predicted violation units: {violation['predicted_violation_support']}",
        "",
        "## Four-state Confusion Matrix",
        "",
        *_markdown_matrix(metrics["four_state_rule_accuracy"]),
        "",
        "## Final Decision Confusion Matrix",
        "",
        *_markdown_matrix(metrics["final_decision_accuracy"]),
        "",
        "## Per-rule Metrics",
        "",
        "| Rule ID | Support | Four-state Accuracy | Violation Precision | Violation Recall | Violation F1 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in metrics["per_rule"]:
        lines.append(
            f"| {item['rule_id']} | {item['support']} | "
            f"{_metric(item['four_state_accuracy'])} | "
            f"{_metric(item['violation_precision'])} | "
            f"{_metric(item['violation_recall'])} | "
            f"{_metric(item['violation_f1'])} |"
        )

    lines.extend(["", "## Failure Details", ""])
    rule_failures = report["failures"]["rule_mismatches"]
    status_failures = report["failures"]["final_status_mismatches"]
    if not rule_failures and not status_failures:
        lines.append("No mismatches.")
    else:
        for item in rule_failures:
            lines.append(
                "- Rule mismatch: "
                f"case `{item['case_id']}`, expense `{item['expense_id']}`, "
                f"rule `{item['rule_id']}`, expected `{item['expected']}`, "
                f"actual `{item['actual']}`."
            )
        for item in status_failures:
            lines.append(
                "- Final status mismatch: "
                f"case `{item['case_id']}`, expected `{item['expected_status']}`, "
                f"actual `{item['actual_status']}`."
            )
    return "\n".join(lines) + "\n"


def rag_markdown(report: dict[str, Any]) -> str:
    metadata = report["metadata"]
    metrics = report["metrics"]
    lines = [
        "# RAG Golden Evaluation Report",
        "",
        "## Metadata",
        "",
        f"- Run ID: `{metadata['run_id']}`",
        f"- Timestamp UTC: `{metadata['timestamp_utc']}`",
        f"- Retriever: `{metadata['retriever_id']}`",
        f"- Policy: `{metadata['policy_id']}` v`{metadata['policy_version']}`",
        f"- Git commit: `{metadata['git_commit']}`",
        f"- Worktree dirty: `{str(metadata['worktree_dirty']).lower()}`",
        f"- Dataset: `{metadata['dataset_path']}`",
        f"- Dataset SHA-256: `{metadata['dataset_sha256']}`",
        f"- Queries scored: {metadata['scored_count']}",
        f"- Queries skipped: {metadata['skipped_count']}",
        f"- Positive queries: {metadata['positive_query_count']}",
        f"- Negative queries: {metadata['negative_query_count']}",
        f"- Requested ranking depth: {metadata['requested_ranking_depth']}",
        "",
        "## Summary",
        "",
        "| Metric | Value | Support |",
        "|---|---:|---:|",
        f"| Recall@1 | {_metric(metrics['recall_at_1']['rate'])} | {metrics['recall_at_1']['positive_query_support']} |",
        f"| Recall@3 | {_metric(metrics['recall_at_3']['rate'])} | {metrics['recall_at_3']['positive_query_support']} |",
        f"| Set Recall@3 | {_metric(metrics['set_recall_at_3']['mean'])} | {metrics['set_recall_at_3']['positive_query_support']} |",
        f"| MRR | {_metric(metrics['mrr']['mean'])} | {metrics['mrr']['positive_query_support']} |",
        f"| Negative No-result Accuracy | {_metric(metrics['negative_no_result_accuracy']['accuracy'])} | {metrics['negative_no_result_accuracy']['negative_query_support']} |",
        "",
        "## Query Details",
        "",
        "| Query ID | Query | Relevant | Retrieved | Hit@1 | Hit@3 | Set Recall@3 | RR | Negative Success |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for item in report["queries"]:
        relevant = ", ".join(item["relevant_rule_ids"]) or "[]"
        retrieved = ", ".join(item["retrieved_rule_ids"]) or "[]"
        lines.append(
            f"| {item['query_id']} | {item['query']} | {relevant} | {retrieved} | "
            f"{item['hit_at_1']} | {item['hit_at_3']} | "
            f"{_metric(item['set_recall_at_3'])} | "
            f"{_metric(item['reciprocal_rank'])} | {item['negative_success']} |"
        )

    lines.extend(["", "## Failure Details", ""])
    if not report["failures"]:
        lines.append("No retrieval failures under the reported diagnostics.")
    else:
        for item in report["failures"]:
            lines.append(
                f"- `{item['query_id']}` query `{item['query']}`: "
                f"relevant={item['relevant_rule_ids']}, "
                f"retrieved={item['retrieved_rule_ids']}, "
                f"hit@1={item['hit_at_1']}, hit@3={item['hit_at_3']}, "
                f"set_recall@3={item['set_recall_at_3']}, "
                f"rr={item['reciprocal_rank']}, "
                f"negative_success={item['negative_success']}."
            )
    return "\n".join(lines) + "\n"


def write_report_pair(
    report: dict[str, Any],
    output_directory: Path,
    stem: str,
    markdown_renderer: Callable[[dict[str, Any]], str],
) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / f"{stem}.json"
    markdown_path = output_directory / f"{stem}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    persisted_report = json.loads(json_path.read_text(encoding="utf-8"))
    markdown_path.write_text(
        markdown_renderer(persisted_report),
        encoding="utf-8",
    )
    return json_path, markdown_path


def print_audit_summary(report: dict[str, Any], json_path: Path) -> None:
    metadata = report["metadata"]
    metrics = report["metrics"]
    print("Audit Golden Evaluation")
    print()
    print(f"Cases scored: {metadata['scored_count']}")
    print(f"Cases skipped: {metadata['skipped_count']}")
    print()
    print(f"Violation Precision: {_metric(metrics['violation']['precision'])}")
    print(f"Violation Recall: {_metric(metrics['violation']['recall'])}")
    print(f"Violation F1: {_metric(metrics['violation']['f1'])}")
    print()
    print(
        "Four-state Accuracy: "
        f"{_metric(metrics['four_state_rule_accuracy']['accuracy'])}"
    )
    print(
        "Final Decision Accuracy: "
        f"{_metric(metrics['final_decision_accuracy']['accuracy'])}"
    )
    print(f"Exact Match Rate: {_metric(metrics['exact_match_rate']['rate'])}")
    print(
        "Automation Coverage: "
        f"{_metric(metrics['automation_coverage']['rate'])}"
    )
    print(
        "Determinate Accuracy: "
        f"{_metric(metrics['determinate_accuracy']['accuracy'])}"
    )
    print()
    print(f"Report: {json_path}")


def print_rag_summary(report: dict[str, Any], json_path: Path) -> None:
    metadata = report["metadata"]
    metrics = report["metrics"]
    print("RAG Golden Evaluation")
    print()
    print(f"Queries scored: {metadata['scored_count']}")
    print(f"Positive queries: {metadata['positive_query_count']}")
    print(f"Negative queries: {metadata['negative_query_count']}")
    print()
    print(f"Recall@1: {_metric(metrics['recall_at_1']['rate'])}")
    print(f"Recall@3: {_metric(metrics['recall_at_3']['rate'])}")
    print(f"Set Recall@3: {_metric(metrics['set_recall_at_3']['mean'])}")
    print(f"MRR: {_metric(metrics['mrr']['mean'])}")
    print(
        "Negative No-result Accuracy: "
        f"{_metric(metrics['negative_no_result_accuracy']['accuracy'])}"
    )
    print()
    print(f"Report: {json_path}")
