import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evals.runner import (
    DEFAULT_AUDIT_CASES,
    audit_markdown,
    build_audit_report,
    make_run_id,
    print_audit_summary,
    resolve_output_directory,
    write_report_pair,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate the deterministic audit engine against approved labels."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_AUDIT_CASES,
        help="Audit JSONL dataset path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory. Defaults to artifacts/evals/<run-id>.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_id = args.output.name if args.output is not None else make_run_id()
    output_directory = resolve_output_directory(args.output, run_id)
    report = build_audit_report(args.cases, run_id=run_id)
    json_path, _ = write_report_pair(
        report,
        output_directory,
        "audit_eval_report",
        audit_markdown,
    )
    print_audit_summary(report, json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
