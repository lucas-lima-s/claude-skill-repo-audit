from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse
import concurrent.futures
import glob as glob_module
import os

from auditlib import registry
from auditlib.checks.artifacts import scorecard as artifact_scorecard_fn
from auditlib.config import load_config, load_profile
from auditlib.context import build_context
from auditlib.report import build_dashboard, build_report, write_report
from auditlib.runner import build_layer2_targets, run_layer1
from auditlib.severity import CheckResult, Severity

TOOL_ROOT = Path(__file__).resolve().parent.parent
TOOL_VERSION = "0.1.0"


def _audit_one(
    repo_path_str: str,
    profile_name: str,
    config_path_str: str | None,
    offline: bool,
    run_tests: bool,
) -> dict:
    repo_path = Path(repo_path_str)
    tool_root = TOOL_ROOT

    if not repo_path.exists() or not repo_path.is_dir():
        missing = CheckResult(
            check="runner.missing_repo",
            severity=Severity.FAIL,
            message=f"repo path does not exist: {repo_path}",
        )
        return build_report(
            tool_version=TOOL_VERSION,
            target_path=str(repo_path),
            target_name=repo_path.name,
            profile_name=profile_name,
            findings_layer1=[missing],
            targets_for_layer2=[],
            artifact_scorecard={"present": 0, "total": 0},
        )

    registry.discover("auditlib.checks")
    registry.discover("checks")

    profile = load_profile(tool_root / "profiles", profile_name)
    config = load_config(
        repo_path=repo_path,
        tool_root=tool_root,
        cli_config_path=Path(config_path_str).resolve() if config_path_str else None,
    )

    ctx = build_context(
        repo_path=repo_path,
        profile=profile,
        config=config,
        offline=offline,
        run_tests=run_tests,
    )

    findings_layer1 = run_layer1(ctx, profile)
    artifact_results = [r for r in findings_layer1 if r.check.startswith("artifacts.")]
    artifact_scorecard = artifact_scorecard_fn(artifact_results)

    prompt_dirs = [tool_root / "scripts" / "prompts", tool_root / "scripts" / "auditlib" / "prompts"]
    targets_for_layer2 = build_layer2_targets(ctx, profile, prompt_dirs)

    return build_report(
        tool_version=TOOL_VERSION,
        target_path=str(repo_path),
        target_name=repo_path.name,
        profile_name=profile.name,
        findings_layer1=findings_layer1,
        targets_for_layer2=targets_for_layer2,
        artifact_scorecard=artifact_scorecard,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="scan.py", description="Audit multiple repositories and build a dashboard.")
    parser.add_argument("--repos", default=None)
    parser.add_argument("--repos-glob", default=None)
    parser.add_argument("--repo", action="append", default=None)
    parser.add_argument("--jobs", type=int, default=None)
    parser.add_argument("--profile", default="portfolio")
    parser.add_argument("--config", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--run-tests", dest="run_tests", action="store_true", default=True)
    parser.add_argument("--no-run-tests", dest="run_tests", action="store_false")
    return parser.parse_args(argv)


def _normalize_msys_path(raw: str) -> str:
    if os.name != "nt" or Path(raw).exists():
        return raw
    if len(raw) > 2 and raw.startswith("/") and raw[1].isalpha() and raw[2] == "/":
        candidate = f"{raw[1].upper()}:/{raw[3:]}"
        if Path(candidate).exists():
            return candidate
    if raw.startswith("/tmp/"):
        base = os.environ.get("TEMP") or os.environ.get("TMP")
        if base:
            candidate = str(Path(base) / raw[len("/tmp/") :])
            if Path(candidate).exists():
                return candidate
    return raw


def _collect_repo_paths(args: argparse.Namespace) -> list[str]:
    paths: list[str] = []
    if args.repos:
        text = Path(args.repos).read_text(encoding="utf-8")
        paths.extend(_normalize_msys_path(line.strip()) for line in text.splitlines() if line.strip())
    if args.repos_glob:
        paths.extend(sorted(glob_module.glob(args.repos_glob)))
    if args.repo:
        paths.extend(args.repo)
    return paths


def run_scan(argv: list[str]) -> int:
    args = parse_args(argv)
    repo_paths = _collect_repo_paths(args)
    if not repo_paths:
        print("scan.py: no repos given (use --repos, --repos-glob, or --repo)", file=sys.stderr)
        return 2

    jobs = args.jobs or min(8, os.cpu_count() or 1)

    reports: list[dict] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as executor:
        futures = {
            executor.submit(_audit_one, path, args.profile, args.config, args.offline, args.run_tests): path
            for path in repo_paths
        }
        for future in concurrent.futures.as_completed(futures):
            reports.append(future.result())

    order = {str(Path(path)): i for i, path in enumerate(repo_paths)}
    reports.sort(key=lambda r: order.get(r["target_path"], len(order)))

    dashboard = build_dashboard(tool_version=TOOL_VERSION, profile_name=args.profile, repo_reports=reports)
    json_path = write_report(dashboard, args.out, prefix="repo-audit-dashboard")

    print(f"repo-audit: scanned {dashboard['totals']['repos']} repo(s) -> {dashboard['gate']}", file=sys.stderr)
    print(f"JSON_PATH={json_path}")

    if os.environ.get("REPO_AUDIT_NEVER_EXIT_NONZERO") == "1":
        return 0
    return 0 if dashboard["gate"] == "PASS" else 1


def main() -> None:
    sys.exit(run_scan(sys.argv[1:]))


if __name__ == "__main__":
    main()
