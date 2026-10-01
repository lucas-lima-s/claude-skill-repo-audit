from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from auditlib.context import CheckContext
from auditlib.privacy import identity_blobs
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
            surfaces = [line, *identity_blobs(line)]
            for surface in surfaces:
                lowered = surface.lower()
                reconstructed = surface is not line
                for term in terms:
                    if term.lower() in lowered:
                        check = "content.denylist_reconstructed" if reconstructed else "content.denylist_term"
                        results.append(
                            CheckResult(
                                check=check,
                                severity=Severity.FAIL,
                                message=f"denylisted term ({_redact(term)}) found in tracked content",
                                file=rel,
                                line=lineno,
                                remediation=(
                                    "load this term from gitignored local config "
                                    "(.env / repo-audit.local.toml); do not commit it, even split into "
                                    f"string fragments. Add '{marker}' only if the match is deliberate"
                                ),
                            )
                        )
                for pattern in regexes:
                    if re.search(pattern, surface):
                        check = "content.denylist_reconstructed" if reconstructed else "content.denylist_term"
                        results.append(
                            CheckResult(
                                check=check,
                                severity=Severity.FAIL,
                                message="denylisted pattern matched in tracked content",
                                file=rel,
                                line=lineno,
                                remediation=(
                                    "load this pattern from gitignored local config; do not commit "
                                    f"identity or employer terms, even encoded. Add '{marker}' only if "
                                    "the match is deliberate"
                                ),
                            )
                        )

    return results
