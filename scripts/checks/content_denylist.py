from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity

ALLOW_MARKER = "repo-audit: allow-term"
MAX_FILE_BYTES = 2 * 1024 * 1024


def _redact(term: str) -> str:
    return term[:3] + "..." if len(term) > 3 else term


def _is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return b"\x00" in fh.read(8192)
    except OSError:
        return True


def _allowed(rel: str, allow_paths: tuple[str, ...]) -> bool:
    normalized = rel.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in allow_paths)


@register("content_denylist")
def run(ctx: CheckContext) -> list[CheckResult]:
    terms = ctx.config.denylist.terms
    regexes = ctx.config.denylist.regexes
    if not terms and not regexes:
        return []

    base = Path(ctx.repo_path)
    allow_paths = ctx.config.denylist.allow_paths
    marker = ctx.config.denylist.allow_marker or ALLOW_MARKER
    results: list[CheckResult] = []

    for path in ctx.iter_tracked():
        rel = str(path.relative_to(base)).replace("\\", "/")
        if _allowed(rel, allow_paths):
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        if _is_binary(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for lineno, line in enumerate(text.splitlines(), start=1):
            if marker in line:
                continue
            lowered = line.lower()
            for term in terms:
                if term.lower() in lowered:
                    results.append(
                        CheckResult(
                            check="content.denylist_term",
                            severity=Severity.FAIL,
                            message=f"denylisted term ({_redact(term)}) found in tracked content",
                            file=rel,
                            line=lineno,
                            remediation=f"remove or rewrite this content; add '{marker}' if this is deliberate",
                        )
                    )
            for pattern in regexes:
                if re.search(pattern, line):
                    results.append(
                        CheckResult(
                            check="content.denylist_term",
                            severity=Severity.FAIL,
                            message="denylisted pattern matched in tracked content",
                            file=rel,
                            line=lineno,
                            remediation=f"remove or rewrite this content; add '{marker}' if this is deliberate",
                        )
                    )

    return results
