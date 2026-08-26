from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity


def _is_python_repo(ctx: CheckContext) -> bool:
    return ctx.exists("pyproject.toml") or ctx.exists("setup.py") or any(True for _ in ctx.iter_tracked("*.py"))


class Family(NamedTuple):
    name: str
    patterns: tuple[str, ...]
    applicable: Callable[[CheckContext], bool]


FAMILIES: tuple[Family, ...] = (
    Family("python bytecode cache", ("__pycache__/", "*.py[cod]"), _is_python_repo),
    Family("python virtualenv", (".venv/", "venv/"), _is_python_repo),
    Family("dotenv secrets file", (".env",), lambda ctx: True),
    Family("node_modules", ("node_modules/",), lambda ctx: ctx.exists("package.json")),
    Family("log files", ("*.log",), lambda ctx: True),
    Family("history directory", (".history/",), lambda ctx: True),
)


@register("gitignore")
def run(ctx: CheckContext) -> list[CheckResult]:
    text = ctx.read_text(".gitignore") or ""
    lines = {line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")}

    results: list[CheckResult] = []
    for family in FAMILIES:
        if not family.applicable(ctx):
            continue
        if any(pattern in lines for pattern in family.patterns):
            continue
        results.append(
            CheckResult(
                check="gitignore.coverage",
                severity=Severity.WARN,
                message=f".gitignore is missing coverage for {family.name} (e.g. '{family.patterns[0]}')",
                file=".gitignore",
                remediation=f"add '{family.patterns[0]}' to .gitignore",
            )
        )
    return results
