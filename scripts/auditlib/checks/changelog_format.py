from __future__ import annotations

from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity


@register("changelog_format")
def run(ctx: CheckContext) -> list[CheckResult]:
    if not ctx.exists("CHANGELOG.md"):
        return []

    text = ctx.read_text("CHANGELOG.md") or ""
    lines = text.splitlines()
    head = lines[:10]

    has_header = any(line.strip().startswith("# Changelog") for line in head)
    has_unreleased = any(line.strip().startswith("## [Unreleased]") for line in lines)

    if has_header and has_unreleased:
        return [
            CheckResult(
                check="changelog.format",
                severity=Severity.OK,
                message="CHANGELOG.md follows the Keep a Changelog format",
                file="CHANGELOG.md",
            )
        ]

    missing = []
    if not has_header:
        missing.append("a '# Changelog' header in the first 10 lines")
    if not has_unreleased:
        missing.append("a '## [Unreleased]' section")

    return [
        CheckResult(
            check="changelog.format",
            severity=Severity.WARN,
            message=f"CHANGELOG.md is missing {' and '.join(missing)}",
            file="CHANGELOG.md",
            remediation="follow the Keep a Changelog format (keepachangelog.com)",
        )
    ]
