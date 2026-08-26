from __future__ import annotations

import re
from pathlib import Path

from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity

OS_TOKENS = ("ubuntu-", "windows-", "macos-")
VERSION_KEY_RE = re.compile(r"(python-version|node-version|go-version|rust-version)")
INCLUDE_RE = re.compile(r"^\s*include\s*:", re.MULTILINE)
ANCHOR_RE = re.compile(r"<<:\s*\*")
CHECKOUT_RE = re.compile(r"uses:\s*actions/checkout@")
FETCH_DEPTH_RE = re.compile(r"fetch-depth:\s*0")
HISTORY_SCANNING_CHECKS = ("git_history", "secrets")


@register("ci_workflow")
def run(ctx: CheckContext) -> list[CheckResult]:
    workflows = list(ctx.iter_tracked(".github/workflows/*.yml", ".github/workflows/*.yaml"))
    if not workflows:
        return []

    base = Path(ctx.repo_path)
    results: list[CheckResult] = []
    has_os = False
    has_version = False
    scans_history = any(name in ctx.profile.enabled_checks for name in HISTORY_SCANNING_CHECKS)

    for workflow in workflows:
        text = workflow.read_text(encoding="utf-8", errors="replace")
        rel = str(workflow.relative_to(base)).replace("\\", "/")

        if any(token in text for token in OS_TOKENS):
            has_os = True
        if VERSION_KEY_RE.search(text):
            has_version = True

        if INCLUDE_RE.search(text) or ANCHOR_RE.search(text):
            results.append(
                CheckResult(
                    check="ci_workflow.parser_limit",
                    severity=Severity.WARN,
                    message=f"{rel} uses matrix 'include:' or a YAML anchor, which this scanner does not expand",
                    file=rel,
                    remediation="keep the primary os/version matrix free of include/anchors, or document the gap",
                )
            )

        if scans_history and CHECKOUT_RE.search(text) and not FETCH_DEPTH_RE.search(text):
            results.append(
                CheckResult(
                    check="ci_workflow.shallow_clone",
                    severity=Severity.WARN,
                    message=f"{rel} checks out with actions/checkout without fetch-depth: 0, "
                    "but this repo runs a history-scanning check",
                    file=rel,
                    remediation="add 'with: { fetch-depth: 0 }' to actions/checkout",
                )
            )

    missing = []
    if not has_os:
        missing.append("an OS runner token (ubuntu-*/windows-*/macos-*)")
    if not has_version:
        missing.append("a language-version token (python-version/node-version/...)")

    if missing:
        results.append(
            CheckResult(
                check="ci_workflow.matrix",
                severity=Severity.WARN,
                message=f"CI matrix is missing {' and '.join(missing)}",
                remediation="add an os x language-version matrix strategy to the workflow",
            )
        )
    else:
        results.append(
            CheckResult(
                check="ci_workflow.matrix",
                severity=Severity.OK,
                message="CI matrix declares both an OS runner and a language version",
            )
        )

    return results
