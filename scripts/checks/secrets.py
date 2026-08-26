from __future__ import annotations

import fnmatch
import math
import re
from collections import Counter
from pathlib import Path

from auditlib import gitutil
from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity

_AWS_PREFIX = "AK" + "IA"
_ANTHROPIC_PREFIX = "sk-" + "ant-"

PATTERNS: dict[str, re.Pattern[str]] = {
    "aws_access_key": re.compile(_AWS_PREFIX + r"[0-9A-Z]{16}"),
    "github_pat": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    "github_fine_grained": re.compile(r"github_pat_[A-Za-z0-9_]{60,}"),
    "slack": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "google_api": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "anthropic": re.compile(_ANTHROPIC_PREFIX + r"[A-Za-z0-9_-]{20,}"),
    "openai": re.compile(r"sk-(proj-)?[A-Za-z0-9_-]{32,}"),
    "stripe_live": re.compile(r"sk_live_[0-9a-zA-Z]{24,}"),
    "private_key": re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "generic_assignment": re.compile(
        r"(?i)(api[_-]?key|secret|token|passwd|password|client[_-]?secret)\s*[:=]\s*[\"'][^\"'\s]{16,}[\"']"
    ),
}

PLACEHOLDER_MARKERS = (
    "xxx",
    "changeme",
    "<your",
    "your-",
    "example",
    "dummy",
    "sample",
    "placeholder",
    "replace_me",
    "redacted",
    "0000",
)

INLINE_ALLOW_SECRET = "repo-audit: allow-secret"
ENV_EXCEPTIONS = (".env.example", ".env.sample", ".env.template", ".env.dist")
MAX_FILE_BYTES = 2 * 1024 * 1024
LOCKFILE_NAMES = frozenset(
    {"uv.lock", "package-lock.json", "poetry.lock", "Cargo.lock", "Gemfile.lock", "composer.lock", "yarn.lock"}
)


def _redact(value: str) -> str:
    if len(value) <= 6:
        return "<redacted>"
    return f"{value[:4]}...{value[-2:]}"


def _shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _looks_like_placeholder(token: str) -> bool:
    lowered = token.lower()
    if any(marker in lowered for marker in PLACEHOLDER_MARKERS):
        return True
    if len(set(token)) == 1:
        return True
    if token.startswith(("http://", "https://", "data:", "/", "./", "../")):
        return True
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9./_-]+", token) and "/" in token[1:-1])


def _is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            chunk = fh.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def _ignored(rel: str, ignore_paths: tuple[str, ...]) -> bool:
    normalized = rel.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in ignore_paths)


def _candidate_token_re(min_length: int) -> re.Pattern[str]:
    return re.compile(
        rf"[\"']([A-Za-z0-9+/=_-]{{{min_length},}})[\"']|[:=]\s*([A-Za-z0-9+/=_-]{{{min_length},}})(?=\s|$|[\"'),;])"
    )


def _candidate_tokens(line: str, min_length: int) -> list[str]:
    tokens: list[str] = []
    for match in _candidate_token_re(min_length).finditer(line):
        token = match.group(1) or match.group(2)
        if token:
            tokens.append(token)
    return tokens


def _scan_pattern_matches(rel: str, text: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if INLINE_ALLOW_SECRET in line:
            continue
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(line):
                results.append(
                    CheckResult(
                        check="secrets.pattern",
                        severity=Severity.FAIL,
                        message=f"possible {name} secret: {_redact(match.group(0))}",
                        file=rel,
                        line=lineno,
                        remediation="rotate the credential and remove it from the working tree",
                        evidence={"provider": name},
                    )
                )
    return results


def _scan_entropy(ctx: CheckContext, rel: str, text: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    threshold = ctx.config.secrets.entropy_threshold
    min_length = ctx.config.secrets.min_length
    for lineno, line in enumerate(text.splitlines(), start=1):
        if INLINE_ALLOW_SECRET in line:
            continue
        for token in _candidate_tokens(line, min_length):
            if _looks_like_placeholder(token):
                continue
            entropy = _shannon_entropy(token)
            is_hex = bool(re.fullmatch(r"[0-9a-f]{32,}", token, re.IGNORECASE))
            fires = (entropy >= threshold) or (is_hex and entropy >= 3.0)
            if fires:
                results.append(
                    CheckResult(
                        check="secrets.entropy",
                        severity=Severity.WARN,
                        message=f"high-entropy string looks like a secret: {_redact(token)} (entropy={entropy:.2f})",
                        file=rel,
                        line=lineno,
                        remediation="if this is a real credential, rotate it and load it from the environment instead",
                    )
                )
    return results


def _scan_committed_env(ctx: CheckContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    for tracked in ctx.tracked_files:
        rel = tracked.replace("\\", "/")
        basename = rel.rsplit("/", 1)[-1]
        if basename == ".env" or (basename.startswith(".env.") and basename not in ENV_EXCEPTIONS):
            if basename in ENV_EXCEPTIONS:
                continue
            results.append(
                CheckResult(
                    check="secrets.committed_env",
                    severity=Severity.FAIL,
                    message=f"an env file is committed to the working tree: {rel}",
                    file=rel,
                    remediation="remove it from tracking (git rm --cached), rotate its secrets, add it to .gitignore",
                )
            )

    if ctx.is_git_repo:
        added = gitutil.added_paths_ever(ctx.repo_path, [".env", ".env.*"])
        added = [p for p in added if p.rsplit("/", 1)[-1] not in ENV_EXCEPTIONS]
        if added:
            results.append(
                CheckResult(
                    check="secrets.committed_env",
                    severity=Severity.FAIL,
                    message="'.env' was committed at some point in history",
                    remediation="rotate every secret it may have held; rewrite history with git filter-repo",
                    evidence={"paths": sorted(set(added))},
                )
            )

    return results


def _scan_env_not_ignored(ctx: CheckContext) -> list[CheckResult]:
    env_path = ctx.path(".env")
    if not env_path.exists():
        return []
    if not ctx.is_git_repo:
        return []
    rc, _, _ = gitutil.git(["check-ignore", "-q", ".env"], ctx.repo_path)
    if rc == 0:
        return []
    return [
        CheckResult(
            check="secrets.env_not_ignored",
            severity=Severity.FAIL,
            message=".env exists on disk but is not covered by .gitignore",
            file=".env",
            remediation="add '.env' to .gitignore before it gets committed by accident",
        )
    ]


def _scan_history(ctx: CheckContext) -> list[CheckResult]:
    if not ctx.history_secrets or not ctx.is_git_repo:
        return []
    rc, out, _ = gitutil.git(
        ["log", "--all", "-p", "--unified=0", f"--max-count={ctx.config.history.max_commits}"],
        ctx.repo_path,
    )
    if rc != 0:
        return []
    results: list[CheckResult] = []
    seen: set[tuple[str, str]] = set()
    for name, pattern in PATTERNS.items():
        for match in pattern.finditer(out):
            token = match.group(0)
            key = (name, token)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                CheckResult(
                    check="secrets.pattern",
                    severity=Severity.FAIL,
                    message=f"possible {name} secret found in git history: {_redact(token)}",
                    remediation="rotate the credential; rewrite history with git filter-repo",
                    evidence={"provider": name, "history": True},
                )
            )
    return results


@register("secrets")
def run(ctx: CheckContext) -> list[CheckResult]:
    results: list[CheckResult] = []
    base = Path(ctx.repo_path)
    ignore_paths = ctx.config.secrets.ignore_paths

    for path in ctx.iter_tracked():
        rel = str(path.relative_to(base)).replace("\\", "/")
        if _ignored(rel, ignore_paths) or rel.rsplit("/", 1)[-1] in LOCKFILE_NAMES:
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

        results.extend(_scan_pattern_matches(rel, text))
        results.extend(_scan_entropy(ctx, rel, text))

    results.extend(_scan_committed_env(ctx))
    results.extend(_scan_env_not_ignored(ctx))
    results.extend(_scan_history(ctx))

    return results
