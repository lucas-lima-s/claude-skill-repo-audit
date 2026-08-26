from __future__ import annotations

import re
import tomllib

from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity

NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+")
SUPPORTED_LINE_RE = re.compile(
    r"^(-r\s|-c\s|-i\s|--index-url\b|--extra-index-url\b|"
    r"[A-Za-z0-9_.-]+(\[[A-Za-z0-9_,.-]+\])?([<>=!~]=?[A-Za-z0-9_.*+-]+(,[<>=!~]=?[A-Za-z0-9_.*+-]+)*)?\s*(;.*)?)$"
)


def _package_name(entry: str) -> str:
    match = NAME_RE.match(entry.strip())
    return match.group(0).lower() if match else ""


def dev_dependency_names(ctx: CheckContext) -> set[str]:
    names: set[str] = set()

    if ctx.exists("pyproject.toml"):
        try:
            data = tomllib.loads(ctx.read_text("pyproject.toml") or "")
        except tomllib.TOMLDecodeError:
            data = {}
        dev_group = data.get("dependency-groups", {}).get("dev", [])
        if not dev_group:
            dev_group = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
        for entry in dev_group:
            name = _package_name(entry)
            if name:
                names.add(name)

    if not names and ctx.exists("requirements-dev.txt"):
        text = ctx.read_text("requirements-dev.txt") or ""
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith(("-r", "-c", "-i", "--")):
                continue
            name = _package_name(stripped)
            if name:
                names.add(name)

    return names


@register("dev_deps")
def run(ctx: CheckContext) -> list[CheckResult]:
    is_python = ctx.exists("pyproject.toml") or any(True for _ in ctx.iter_tracked("*.py"))
    if not is_python:
        return []

    results: list[CheckResult] = []
    names = dev_dependency_names(ctx)

    if not names:
        results.append(
            CheckResult(
                check="dev_deps.declared",
                severity=Severity.INFO,
                message="no dev dependency group was found",
                remediation="declare [dependency-groups].dev in pyproject.toml",
            )
        )

    if ctx.exists("tests") and "pytest" not in names:
        results.append(
            CheckResult(
                check="dev_deps.declared",
                severity=Severity.WARN,
                message="tests/ exists but pytest is not declared as a dev dependency",
                remediation='add "pytest" to the dev dependency group',
            )
        )

    if ctx.exists("requirements-dev.txt"):
        text = ctx.read_text("requirements-dev.txt") or ""
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not SUPPORTED_LINE_RE.match(stripped):
                results.append(
                    CheckResult(
                        check="dev_deps.declared",
                        severity=Severity.WARN,
                        message="requirements-dev.txt line is outside the supported subset",
                        file="requirements-dev.txt",
                        line=lineno,
                        remediation="use pkg[extras]<spec>; marker, -r, -c, -i, --index-url or --extra-index-url lines",
                    )
                )

    if not results:
        results.append(
            CheckResult(check="dev_deps.declared", severity=Severity.OK, message="dev dependency set looks complete")
        )

    return results
