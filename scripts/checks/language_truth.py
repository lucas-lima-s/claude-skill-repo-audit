from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from auditlib import gitutil
from auditlib.context import CheckContext
from auditlib.registry import register
from auditlib.severity import CheckResult, Severity

from checks.github_meta import resolve_github_token

EXT_TO_LANGUAGE = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cc": "C++",
    ".cs": "C#",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ps1": "PowerShell",
    ".bat": "Batchfile",
    ".cmd": "Batchfile",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sql": "SQL",
    ".lua": "Lua",
    ".r": "R",
    ".dart": "Dart",
    ".svg": "SVG",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
}

PRIMARY_EXCLUDED = {"Markdown"}
EXCLUDE_DIR_PREFIXES = ("node_modules/", "dist/", "build/", "vendor/")
LINGUIST_ATTRS = {"linguist-vendored", "linguist-generated", "linguist-documentation"}
UNSET_VALUES = {"unset", "unspecified", "false"}


def _excluded_by_path(rel: str) -> bool:
    if any(rel.startswith(prefix) for prefix in EXCLUDE_DIR_PREFIXES):
        return True
    name = rel.rsplit("/", 1)[-1]
    if ".min." in name:
        return True
    return bool(name.endswith(".lock") or name in {"uv.lock", "package-lock.json"})


def _linguist_excluded_paths(repo_path: str, rel_paths: list[str]) -> set[str]:
    if not rel_paths:
        return set()
    excluded: set[str] = set()
    chunk_size = 200
    for i in range(0, len(rel_paths), chunk_size):
        chunk = rel_paths[i : i + chunk_size]
        rc, out, _ = gitutil.git(["check-attr", "-a", "--", *chunk], repo_path)
        if rc != 0:
            continue
        for line in out.splitlines():
            parts = line.split(": ", 2)
            if len(parts) != 3:
                continue
            path, attr, value = parts
            if attr in LINGUIST_ATTRS and value not in UNSET_VALUES:
                excluded.add(path)
    return excluded


def _declared_language(ctx: CheckContext) -> str | None:
    if ctx.exists("pyproject.toml") or ctx.exists("setup.py"):
        return "Python"
    if ctx.exists("package.json"):
        return "TypeScript" if ctx.exists("tsconfig.json") else "JavaScript"
    if ctx.exists("Cargo.toml"):
        return "Rust"
    if ctx.exists("go.mod"):
        return "Go"
    return None


def _extension_hint(language: str) -> str:
    for ext, lang in EXT_TO_LANGUAGE.items():
        if lang == language:
            return ext
    return ""


def _fetch_github_language(repo_path: str) -> str | None:
    rc, out, _ = gitutil.git(["remote", "get-url", "origin"], repo_path)
    if rc != 0 or not out.strip():
        return None
    joined = out.strip()
    for marker in ("github.com:", "github.com/"):
        if marker in joined:
            joined = joined.split(marker, 1)[1]
            break
    else:
        return None
    owner_repo = joined.removesuffix(".git")
    if "/" not in owner_repo:
        return None

    token = resolve_github_token()

    headers = {"Accept": "application/vnd.github+json", "User-Agent": "repo-audit"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(f"https://api.github.com/repos/{owner_repo}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None
    return data.get("language")


@register("language_truth")
def run(ctx: CheckContext) -> list[CheckResult]:
    if not ctx.is_git_repo or not ctx.tracked_files:
        return []

    base = Path(ctx.repo_path)
    candidates = [f.replace("\\", "/") for f in ctx.tracked_files]
    candidates = [f for f in candidates if not _excluded_by_path(f)]
    linguist_excluded = _linguist_excluded_paths(ctx.repo_path, candidates)
    candidates = [f for f in candidates if f not in linguist_excluded]

    histogram: dict[str, int] = {}
    for rel in candidates:
        language = EXT_TO_LANGUAGE.get(Path(rel).suffix.lower())
        if language is None or language in PRIMARY_EXCLUDED:
            continue
        try:
            size = (base / rel).stat().st_size
        except OSError:
            continue
        histogram[language] = histogram.get(language, 0) + size

    total_bytes = sum(histogram.values())
    if total_bytes == 0:
        return []

    primary_language = max(histogram, key=lambda lang: histogram[lang])
    primary_ratio = histogram[primary_language] / total_bytes
    declared = _declared_language(ctx)

    results: list[CheckResult] = []

    if declared and declared != primary_language:
        offending_ext = _extension_hint(primary_language) or ".<ext>"
        severity = Severity.FAIL if primary_ratio >= 0.5 else Severity.WARN
        results.append(
            CheckResult(
                check="language.declared_vs_real",
                severity=severity,
                message=f"declared stack is {declared} but {primary_language} is {primary_ratio:.0%} of counted bytes",
                remediation=f"add '*{offending_ext} linguist-vendored' (or "
                f"'docs/*.svg linguist-generated=true' for generated files) to .gitattributes",
                evidence={
                    "declared": declared,
                    "computed_primary": primary_language,
                    "ratio": round(primary_ratio, 4),
                    "histogram": histogram,
                },
            )
        )
    else:
        results.append(
            CheckResult(
                check="language.linguist_hint",
                severity=Severity.INFO,
                message=f"computed primary language: {primary_language} ({primary_ratio:.0%})",
                evidence={"histogram": histogram},
            )
        )

    if not ctx.offline:
        github_language = _fetch_github_language(ctx.repo_path)
        if github_language:
            results[0].evidence["github_language"] = github_language

    return results
