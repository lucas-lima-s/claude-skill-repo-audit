from __future__ import annotations

import re
import tomllib

from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity

FORMATTER_INVOCATION = re.compile(r"\b(ruff format|black)\b")


def _workflows_invoke_formatter(ctx: CheckContext) -> bool:
    for workflow in ctx.iter_tracked(".github/workflows/*.yml", ".github/workflows/*.yaml"):
        text = workflow.read_text(encoding="utf-8", errors="replace")
        if FORMATTER_INVOCATION.search(text):
            return True
    return False


@register("pyproject")
def run(ctx: CheckContext) -> list[CheckResult]:
    if not ctx.exists("pyproject.toml"):
        return []

    raw_text = ctx.read_text("pyproject.toml") or ""
    try:
        data = tomllib.loads(raw_text)
    except tomllib.TOMLDecodeError as exc:
        return [
            CheckResult(
                check="pyproject.format",
                severity=Severity.FAIL,
                message=f"pyproject.toml is not valid TOML: {exc}",
                file="pyproject.toml",
                remediation="fix the TOML syntax error",
            )
        ]

    results: list[CheckResult] = []
    tool = data.get("tool", {})
    has_ruff = "ruff" in tool
    has_black = "black" in tool

    if not has_ruff and not has_black:
        results.append(
            CheckResult(
                check="pyproject.format",
                severity=Severity.FAIL,
                message="neither [tool.ruff] nor [tool.black] is configured",
                file="pyproject.toml",
                remediation="add [tool.ruff] (used as both linter and formatter) or [tool.black]",
            )
        )
    else:
        has_formatter_signal = "format" in tool.get("ruff", {}) or has_black or _workflows_invoke_formatter(ctx)
        if not has_formatter_signal:
            results.append(
                CheckResult(
                    check="pyproject.format",
                    severity=Severity.WARN,
                    message="a linter is configured but no formatter signal was found",
                    file="pyproject.toml",
                    remediation="add [tool.ruff.format] or [tool.black], or invoke one in CI",
                )
            )

    if "requires-python" not in data.get("project", {}):
        results.append(
            CheckResult(
                check="pyproject.format",
                severity=Severity.INFO,
                message="project.requires-python is not declared",
                file="pyproject.toml",
                remediation='add requires-python = ">=3.11" (or your floor) under [project]',
            )
        )

    if "uv" not in tool and ctx.exists("uv.lock") and "build-system" not in data:
        results.append(
            CheckResult(
                check="pyproject.format",
                severity=Severity.WARN,
                message="uv.lock is committed but [tool.uv] is absent and no [build-system] is declared",
                file="pyproject.toml",
                remediation="add [tool.uv]\npackage = false",
            )
        )

    if not results:
        results.append(
            CheckResult(
                check="pyproject.format",
                severity=Severity.OK,
                message="pyproject.toml tooling looks complete",
                file="pyproject.toml",
            )
        )

    return results
