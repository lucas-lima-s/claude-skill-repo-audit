from __future__ import annotations

import fnmatch

from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity

EOL_LINE = "* text=auto eol=lf"
GENERATED_GLOBS = ("docs/*.svg", "*.min.js", "dist/**")
LINGUIST_ATTRS = ("linguist-generated", "linguist-vendored")


def _parse_gitattributes(text: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        entries.append((parts[0], " ".join(parts[1:])))
    return entries


def _has_linguist_attr(rel_path: str, entries: list[tuple[str, str]]) -> bool:
    for pattern, attrs in entries:
        candidate = pattern.lstrip("/")
        if fnmatch.fnmatch(rel_path, candidate) and any(attr in attrs for attr in LINGUIST_ATTRS):
            return True
    return False


@register("gitattributes")
def run(ctx: CheckContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    text = ctx.read_text(".gitattributes")
    if text is None:
        return results

    if EOL_LINE not in text:
        results.append(
            CheckResult(
                check="gitattributes.eol",
                severity=Severity.WARN,
                message=".gitattributes exists without a '* text=auto eol=lf' line",
                file=".gitattributes",
                remediation=f"add '{EOL_LINE}' to .gitattributes",
            )
        )

    entries = _parse_gitattributes(text)
    offenders = []
    for tracked in ctx.tracked_files:
        rel = tracked.replace("\\", "/")
        if any(fnmatch.fnmatch(rel, glob) for glob in GENERATED_GLOBS) and not _has_linguist_attr(rel, entries):
            offenders.append(rel)

    if offenders:
        results.append(
            CheckResult(
                check="gitattributes.linguist",
                severity=Severity.INFO,
                message=f"{len(offenders)} generated asset(s) lack a linguist-generated/vendored attribute",
                file=offenders[0],
                remediation="add e.g. 'docs/*.svg linguist-generated=true' to .gitattributes",
                evidence={"files": offenders},
            )
        )

    return results
