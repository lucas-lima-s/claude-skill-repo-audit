from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity

TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,34}$")


def _owner_repo(ctx: CheckContext) -> str | None:
    from auditlib import gitutil

    rc, out, _ = gitutil.git(["remote", "get-url", "origin"], ctx.repo_path)
    if rc != 0 or not out.strip():
        return None
    url = out.strip()
    for marker in ("github.com:", "github.com/"):
        if marker in url:
            url = url.split(marker, 1)[1]
            break
    else:
        return None
    owner_repo = url.removesuffix(".git")
    return owner_repo if "/" in owner_repo else None


def _vault_token() -> str | None:
    root = os.environ.get("AGENT_WORKBENCH_ROOT")
    if not root:
        return None
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from agent_workbench.vault import get_secret
    except ImportError:
        return None
    try:
        return get_secret("GITHUB_TOKEN") or None
    except Exception:
        return None


def _gh_auth_token() -> str | None:
    try:
        proc = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    return None


def resolve_github_token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or _vault_token() or _gh_auth_token()


def _fetch_repo_metadata(ctx: CheckContext, owner_repo: str) -> dict | None:
    token = resolve_github_token()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "repo-audit"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(f"https://api.github.com/repos/{owner_repo}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def _from_local_meta(ctx: CheckContext) -> list[CheckResult]:
    meta_path = ctx.path(".github/repo-meta.toml")
    if not meta_path.exists():
        return [
            CheckResult(
                check="github.metadata_unavailable",
                severity=Severity.INFO,
                message="no .github/repo-meta.toml and no online GitHub access; skipping description/topics checks",
                remediation="add .github/repo-meta.toml with description and topics, or run online",
            )
        ]
    try:
        data = tomllib.loads(meta_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return [
            CheckResult(
                check="github.metadata_unavailable",
                severity=Severity.INFO,
                message=".github/repo-meta.toml is not valid TOML",
            )
        ]
    repo_name = Path(ctx.repo_path).name
    return _evaluate(ctx, data.get("description", "") or "", data.get("topics", []) or [], repo_name)


def _evaluate(ctx: CheckContext, description: str, topics: list[str], repo_name: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    min_len = ctx.config.github.description_min_length

    is_bad_description = (
        not description
        or len(description) < min_len
        or len(description) > 350
        or description.strip().lower() == repo_name.lower()
    )
    if is_bad_description:
        results.append(
            CheckResult(
                check="github.description",
                severity=Severity.WARN,
                message=f"GitHub description is missing or low quality (length={len(description)})",
                remediation=f"write a description of at least {min_len} characters that is not just the repo name",
            )
        )

    topics_min = ctx.config.github.topics_min
    topics_max = ctx.config.github.topics_max
    bad_topics = [t for t in topics if not TOPIC_RE.match(t) or t == repo_name.lower()]
    if not (topics_min <= len(topics) <= topics_max) or bad_topics:
        results.append(
            CheckResult(
                check="github.topics",
                severity=Severity.WARN,
                message=f"GitHub topics do not meet the {topics_min}-{topics_max} kebab-case rule "
                f"(found {len(topics)})",
                remediation=f"set {topics_min} to {topics_max} lowercase-kebab topics, none equal to the repo name",
            )
        )

    return results


@register("github_meta")
def run(ctx: CheckContext) -> list[CheckResult]:
    if ctx.offline:
        return _from_local_meta(ctx)

    owner_repo = _owner_repo(ctx)
    if owner_repo is None:
        return _from_local_meta(ctx)

    data = _fetch_repo_metadata(ctx, owner_repo)
    if data is None:
        return _from_local_meta(ctx)

    repo_name = owner_repo.split("/", 1)[-1]
    return _evaluate(ctx, data.get("description") or "", data.get("topics") or [], repo_name)
