import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings
from app.policy import PolicyDocument, PolicyRegistry


GENERATED_NOTICE = (
    "This file is generated from policy_rules.json. Do not edit manually."
)


def _format_amount(amount: float) -> str:
    return f"{amount:g}"


def render_policy_markdown(document: PolicyDocument) -> str:
    effective_date = (
        document.effective_date.isoformat()
        if document.effective_date is not None
        else "未提供"
    )
    lines = [
        "# 企业差旅报销管理制度 MVP 版",
        "",
        f"> {GENERATED_NOTICE}",
        "",
        "## Policy Metadata",
        "",
        f"- Policy ID：`{document.policy_id}`",
        f"- Policy Version：`{document.policy_version}`",
        f"- Effective Date：`{effective_date}`",
        f"- Currency：`{document.currency}`",
        "",
        "## Rules",
        "",
    ]

    for rule in document.rules:
        severity = rule.severity.value if rule.severity is not None else "未定义"
        evaluator = rule.evaluator.value if rule.evaluator is not None else "无"
        lines.extend(
            [
                f"### {rule.rule_id} {rule.title}",
                "",
                f"- 适用类别：{', '.join(rule.category)}",
                f"- Enforcement：`{rule.enforcement.value}`",
                f"- Severity：`{severity}`",
                f"- Evaluator：`{evaluator}`",
                f"- 规则内容：{rule.description}",
                f"- Keywords：{', '.join(rule.keywords)}",
            ]
        )

        if rule.threshold is not None:
            lines.append(
                "- Threshold："
                f"`{rule.threshold.comparison.value} "
                f"{_format_amount(rule.threshold.amount)} "
                f"{document.currency} / {rule.threshold.basis.value}`"
            )
        if rule.applicable_cities is not None:
            lines.append(f"- 适用城市：{', '.join(rule.applicable_cities)}")
        if rule.flag is not None:
            lines.append(f"- 异常标记：`{rule.flag}`")
        if rule.violation_message is not None:
            lines.append(f"- 异常说明：{rule.violation_message}")
        lines.append("")

    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the human-readable policy Markdown projection."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare generated output without modifying the Markdown file.",
    )
    parser.add_argument(
        "--policy-path",
        default=settings.policy_rules_path,
        help="Path to policy_rules.json.",
    )
    parser.add_argument(
        "--output-path",
        default=settings.rules_markdown_path,
        help="Path to company_travel_policy.md.",
    )
    args = parser.parse_args(argv)

    document = PolicyRegistry(args.policy_path).document
    generated_bytes = render_policy_markdown(document).encode("utf-8")
    output_path = Path(args.output_path)

    if args.check:
        if not output_path.exists() or output_path.read_bytes() != generated_bytes:
            print(f"Policy Markdown is out of date: {output_path}")
            return 1
        print(f"Policy Markdown is up to date: {output_path}")
        return 0

    output_path.write_bytes(generated_bytes)
    print(f"Generated policy Markdown: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
