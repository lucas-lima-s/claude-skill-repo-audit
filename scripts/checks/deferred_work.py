from __future__ import annotations

import re
from pathlib import Path

from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity

MARKER_FILES = ("ROADMAP.md", "TODO.md", "FUTURE.md")
SECTION_TITLE_RE = re.compile(r"^#{1,6}\s*(roadmap|future work|planned|coming soon)\s*$", re.IGNORECASE)
INLINE_MARKER_RE = re.compile(r"\b(TODO|FIXME|XXX):")
SOURCE_GLOBS = ("*.py", "*.js", "*.jsx", "*.ts", "*.tsx", "*.go", "*.rs", "*.java")
SOURCE_EXCLUDE_PREFIXES = ("examples/", "tests/fixtures/")


@register("deferred_work")
def run(ctx: CheckContext) -> list[CheckResult]:
    base = Path(ctx.repo_path)
    results: list[CheckResult] = []

    for filename in MARKER_FILES:
        if ctx.exists(filename):
            results.append(
                CheckResult(
                    check="deferred_work.marker",
                    severity=Severity.WARN,
                    message=f"{filename} exists",
                    file=filename,
                    remediation="a portfolio repo should ship finished work; execute it or delete the marker",
                )
            )

    for path in ctx.iter_tracked("*.md"):
        rel = str(path.relative_to(base)).replace("\\", "/")
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if SECTION_TITLE_RE.match(line.strip()):
                results.append(
                    CheckResult(
                        check="deferred_work.marker",
                        severity=Severity.WARN,
                        message=f"'{line.strip()}' section reads as deferred work",
                        file=rel,
                        line=lineno,
                        remediation="a portfolio repo should ship finished work; execute it or delete the section",
                    )
                )

    for path in ctx.iter_tracked(*SOURCE_GLOBS):
        rel = str(path.relative_to(base)).replace("\\", "/")
        if any(rel.startswith(prefix) for prefix in SOURCE_EXCLUDE_PREFIXES):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if INLINE_MARKER_RE.search(line):
                results.append(
                    CheckResult(
                        check="deferred_work.marker",
                        severity=Severity.WARN,
                        message="deferred-work marker in tracked source",
                        file=rel,
                        line=lineno,
                        remediation="a portfolio repo should ship finished work; execute it or delete the marker",
                    )
                )

    return results
