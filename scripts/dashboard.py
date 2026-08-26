from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse
import json

from auditlib.report import load_and_validate, render_markdown


def _render_dashboard_markdown(report: dict) -> str:
    lines = [f"repo-audit dashboard (profile={report.get('profile')})"]
    totals = report.get("totals", {})
    lines.append(
        f"Totals: {totals.get('repos', 0)} repos, {totals.get('blocked', 0)} blocked, "
        f"{totals.get('fail', 0)} fail, {totals.get('warn', 0)} warn, "
        f"{totals.get('info', 0)} info, {totals.get('ok', 0)} ok"
    )
    lines.append("")
    lines.append("| repo | gate | fail | warn | info | ok |")
    lines.append("|---|---|---|---|---|---|")
    for repo in report.get("repos", []):
        scorecard = repo.get("scorecard", {})
        lines.append(
            f"| {repo.get('target_name')} | {repo.get('gate')} | {scorecard.get('fail', 0)} | "
            f"{scorecard.get('warn', 0)} | {scorecard.get('info', 0)} | {scorecard.get('ok', 0)} |"
        )
    lines.append("")
    lines.append(f"Summary: {report.get('gate')}")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="dashboard.py", description="Render a repo-audit JSON report.")
    parser.add_argument("--json", required=True, dest="json_path")
    parser.add_argument("--format", choices=["md", "json"], default="md")
    parser.add_argument("--fail-on", choices=["fail", "warn"], default="fail")
    return parser.parse_args(argv)


def _has_warn_or_worse(report: dict) -> bool:
    if report.get("kind") == "dashboard":
        totals = report.get("totals", {})
        return bool(totals.get("blocked", 0) or totals.get("warn", 0) or totals.get("fail", 0))
    scorecard = report.get("scorecard", {})
    return bool(scorecard.get("fail", 0) or scorecard.get("warn", 0))


def run_dashboard(argv: list[str]) -> int:
    args = parse_args(argv)
    report = load_and_validate(args.json_path)

    if args.format == "json":
        print(json.dumps(report, indent=2))
    elif report.get("kind") == "dashboard":
        print(_render_dashboard_markdown(report))
    else:
        print(render_markdown(report))

    if args.fail_on == "warn":
        return 1 if _has_warn_or_worse(report) else 0
    return 1 if report.get("gate") == "BLOCK" else 0


def main() -> None:
    sys.exit(run_dashboard(sys.argv[1:]))


if __name__ == "__main__":
    main()
