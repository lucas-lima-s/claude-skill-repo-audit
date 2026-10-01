from __future__ import annotations

import re
from pathlib import Path

from auditlib import gitutil
from auditlib.context import CheckContext
from auditlib.privacy import collapse_encoded_paths, identity_blobs
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity

PATTERNS = (
    re.compile(r"\b[a-z]:/+users(?:/|$)"),
    re.compile(r"\b[a-z]:/+users/[a-z0-9._-]+"),
    re.compile(r"(?<!/usr)/users/[a-z0-9._-]+(/|$)"),
    re.compile(r"/home/[a-z0-9._-]+(/|$)"),
    re.compile(r"\b[a-z]:/+(projects|dev|work|repos)(/|$)"),
    re.compile(r"\b[a-z]:/+python\d+"),
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

MAX_FILE_BYTES = 2 * 1024 * 1024
LOCKFILE_NAMES = frozenset(
    {
        "uv.lock",
        "package-lock.json",
        "poetry.lock",
        "Cargo.lock",
        "Gemfile.lock",
        "composer.lock",
        "yarn.lock",
    }
)
HISTORY_REGEX = r"[A-Za-z]:.+Users|[A-Za-z]:.+Python[0-9]|/home/[A-Za-z0-9._-]+"


def _is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return b"\x00" in fh.read(8192)
    except OSError:
        return True


def _line_has_machine_path(line: str) -> bool:
    normalized = collapse_encoded_paths(line)
    if any(marker in normalized for marker in SUPPRESSORS):
        return False
    candidates = [normalized, *[collapse_encoded_paths(blob) for blob in identity_blobs(line)]]
    return any(pattern.search(candidate) for candidate in candidates for pattern in PATTERNS)


def _scan_history(ctx: CheckContext) -> list[CheckResult]:
    if not ctx.is_git_repo:
        return []
    rc, out, _ = gitutil.git(
        [
            "log",
            "--all",
            "-i",
            "-G",
            HISTORY_REGEX,
            "--format=%h %s",
            f"--max-count={min(ctx.config.history.max_commits, 50)}",
        ],
        ctx.repo_path,
    )
    if rc != 0 or not out.strip():
        return []
    commits = [line.strip() for line in out.splitlines() if line.strip()][:8]
    return [
        CheckResult(
            check="hardcoded_paths.history",
            severity=Severity.FAIL,
            message="a machine-specific path pattern appears in git history",
            remediation="remove the path from history (git filter-repo) or confirm it is only a "
            "structural detector loaded from gitignored local config",
            evidence={"commits": commits},
        )
    ]


@register("hardcoded_paths")
def run(ctx: CheckContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    base = Path(ctx.repo_path)

    for path in ctx.iter_tracked():
        rel = str(path.relative_to(base)).replace("\\", "/")
        if rel.rsplit("/", 1)[-1] in LOCKFILE_NAMES:
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
            if _line_has_machine_path(line):
                results.append(
                    CheckResult(
                        check="hardcoded_paths.literal",
                        severity=Severity.FAIL,
                        message="literal machine-specific path found",
                        file=rel,
                        line=lineno,
                        remediation="replace with an env var, a relative path, or a CI-provided temp dir; "
                        "if this is a hygiene detector, load the path from gitignored local config "
                        "(.env / repo-audit.local.toml) instead of committing it",
                    )
                )

    if ctx.history_secrets:
        results.extend(_scan_history(ctx))
    return results
