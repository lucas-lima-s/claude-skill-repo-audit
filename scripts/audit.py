from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse
import os
import tomllib

from auditlib import registry
from auditlib.checks.artifacts import scorecard as artifact_scorecard_fn
from auditlib.config import load_config, load_profile
from auditlib.context import build_context
from auditlib.report import build_report, render_markdown, write_report
from auditlib.runner import build_layer2_targets, run_layer1

TOOL_ROOT = Path(__file__).resolve().parent.parent
TOOL_VERSION = "0.1.0"


def _default_profile_name(repo_path: Path) -> str:
    config_path = repo_path / "repo-audit.toml"
    if not config_path.exists():
        return "portfolio"
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return "portfolio"
    return data.get("profile", "portfolio")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="audit.py", description="Audit a single repository against publish-ready standards."
    )
    parser.add_argument("repo_path")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--profile-file", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--run-tests", dest="run_tests", action="store_true", default=None)
    parser.add_argument("--no-run-tests", dest="run_tests", action="store_false")
    parser.add_argument("--trust-target", action="store_true")
    parser.add_argument("--history-secrets", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--render", action="store_true", help="also print a markdown render to stderr")
    return parser.parse_args(argv)


def run_audit(argv: list[str]) -> int:
    args = parse_args(argv)

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        print(f"repo-audit: repo path does not exist: {repo_path}", file=sys.stderr)
        return 2

    profile_name = args.profile or _default_profile_name(repo_path)

    if args.profile_file:
        profile_file = Path(args.profile_file).resolve()
        profile = load_profile(profile_file.parent, profile_file.stem)
    else:
        profile = load_profile(TOOL_ROOT / "profiles", profile_name)

    config = load_config(
        repo_path=repo_path,
        tool_root=TOOL_ROOT,
        cli_config_path=Path(args.config).resolve() if args.config else None,
    )

    run_tests = args.run_tests
    if run_tests is None:
        run_tests = profile.name == "portfolio"

    ctx = build_context(
        repo_path=repo_path,
        profile=profile,
        config=config,
        offline=args.offline,
        run_tests=run_tests,
        history_secrets=args.history_secrets,
        trust_target=args.trust_target,
    )

    registry.discover("auditlib.checks")
    registry.discover("checks")

    findings_layer1 = run_layer1(ctx, profile)
    artifact_results = [r for r in findings_layer1 if r.check.startswith("artifacts.")]
    artifact_scorecard = artifact_scorecard_fn(artifact_results)

    prompt_dirs = [TOOL_ROOT / "scripts" / "prompts", TOOL_ROOT / "scripts" / "auditlib" / "prompts"]
    targets_for_layer2 = build_layer2_targets(ctx, profile, prompt_dirs)

    report = build_report(
        tool_version=TOOL_VERSION,
        target_path=str(repo_path),
        target_name=repo_path.name,
        profile_name=profile.name,
        findings_layer1=findings_layer1,
        targets_for_layer2=targets_for_layer2,
        artifact_scorecard=artifact_scorecard,
    )

    json_path = write_report(report, args.json_out, prefix="repo-audit")

    if not args.quiet:
        print(f"repo-audit: {report['target_name']} (profile={report['profile']}) -> {report['gate']}", file=sys.stderr)

    if args.render:
        print(render_markdown(report), file=sys.stderr)

    print(f"JSON_PATH={json_path}")

    if os.environ.get("REPO_AUDIT_NEVER_EXIT_NONZERO") == "1":
        return 0
    return 0 if report["gate"] == "PASS" else 1


def main() -> None:
    sys.exit(run_audit(sys.argv[1:]))


if __name__ == "__main__":
    main()
