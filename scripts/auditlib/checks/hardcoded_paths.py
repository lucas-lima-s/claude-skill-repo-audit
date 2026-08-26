from __future__ import annotations

import re
from pathlib import Path

from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity

PATTERNS = (
    re.compile(r"\b[a-z]:/users/[a-z0-9._-]+(/|$)"),
    re.compile(r"(?<!/usr)/users/[a-z0-9._-]+(/|$)"),
    re.compile(r"/home/[a-z0-9._-]+(/|$)"),
    re.compile(r"\b[a-z]:/(projects|dev|work|repos)/"),
)

SUPPRESSORS = (
    "$home",
    "$userprofile",
    "$temp",
    "$env:temp",
    "$env:userprofile",
    "%userprofile%",
    "%temp%",
    "%homepath%",
    "${{ runner.temp }}",
    "repo-audit: allow-path",
)

SCAN_GLOBS = ("*.py", "*.md", "*.toml", "*.yml", "*.yaml", "*.json", "*.ps1", "*.sh")
MAX_FILE_BYTES = 2 * 1024 * 1024


@register("hardcoded_paths")
def run(ctx: CheckContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    base = Path(ctx.repo_path)

    for path in ctx.iter_tracked(*SCAN_GLOBS):
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        rel = str(path.relative_to(base)).replace("\\", "/")

        for lineno, line in enumerate(text.splitlines(), start=1):
            normalized = line.replace("\\", "/").lower()
            if any(marker in normalized for marker in SUPPRESSORS):
                continue
            if any(pattern.search(normalized) for pattern in PATTERNS):
                results.append(
                    CheckResult(
                        check="hardcoded_paths.literal",
                        severity=Severity.FAIL,
                        message="literal machine-specific path found",
                        file=rel,
                        line=lineno,
                        remediation="replace with an env var, a relative path, or a CI-provided temp dir",
                    )
                )

    return results
