from __future__ import annotations

import json
import subprocess
import sys

from auditlib.checks.dev_deps import dev_dependency_names
from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity


def _resolve_command(ctx: CheckContext) -> list[str] | None:
    if ctx.config.tests.command:
        return list(ctx.config.tests.command)
    if ctx.exists("uv.lock"):
        return ["uv", "run", "--frozen", "pytest", "-q"]
    if "pytest" in dev_dependency_names(ctx):
        return [sys.executable, "-m", "pytest", "-q"]
    if ctx.exists("package.json"):
        try:
            data = json.loads(ctx.read_text("package.json") or "{}")
        except json.JSONDecodeError:
            data = {}
        if data.get("scripts", {}).get("test"):
            return ["npm", "test", "--silent"]
    return None


def _tail(text: str, lines: int = 40) -> str:
    return "\n".join(text.splitlines()[-lines:])


@register("test_execution")
def run(ctx: CheckContext) -> list[CheckResult]:
    command = _resolve_command(ctx)

    if not ctx.run_tests:
        return [
            CheckResult(
                check="tests.execution",
                severity=Severity.INFO,
                message="skipped (--no-run-tests)",
                evidence={"command": command or []},
            )
        ]

    if not ctx.trust_target:
        return [
            CheckResult(
                check="tests.execution",
                severity=Severity.INFO,
                message="skipped: running the suite executes code from the audited repository (pass --trust-target)",
                remediation="re-run with --trust-target only for a repository you own or have reviewed",
                evidence={"command": command or []},
            )
        ]

    if command is None:
        return [
            CheckResult(
                check="tests.execution",
                severity=Severity.WARN,
                message="no test command could be resolved",
                remediation="add a pytest/npm test command, or set [tests].command in repo-audit.toml",
                evidence={"command": []},
            )
        ]

    timeout = ctx.config.tests.timeout_seconds
    try:
        proc = subprocess.run(
            command,
            cwd=ctx.repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        combined = (exc.stdout or "") + (exc.stderr or "")
        return [
            CheckResult(
                check="tests.execution",
                severity=Severity.FAIL,
                message=f"test command timed out after {timeout}s",
                remediation="fix the hang, or raise [tests].timeout_seconds",
                evidence={"command": command, "tail": _tail(combined)},
            )
        ]
    except OSError as exc:
        return [
            CheckResult(
                check="tests.execution",
                severity=Severity.FAIL,
                message=f"failed to launch test command: {exc}",
                evidence={"command": command},
            )
        ]

    output = (proc.stdout or "") + (proc.stderr or "")
    tail = _tail(output)

    if proc.returncode == 0:
        return [
            CheckResult(
                check="tests.execution",
                severity=Severity.OK,
                message="test suite passed",
                evidence={"command": command, "tail": tail},
            )
        ]

    return [
        CheckResult(
            check="tests.execution",
            severity=Severity.FAIL,
            message=f"test suite failed (exit {proc.returncode})",
            remediation="fix the failing tests before publishing",
            evidence={"command": command, "tail": tail},
        )
    ]
