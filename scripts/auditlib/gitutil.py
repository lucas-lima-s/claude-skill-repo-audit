from __future__ import annotations

import subprocess
from pathlib import Path

TIMEOUT_SECONDS = 30


def git(args: list[str], cwd: str | Path) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=False,
            text=True,
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "git command timed out"
    except FileNotFoundError:
        return 127, "", "git executable not found"


def is_repo(path: str | Path) -> bool:
    rc, out, _ = git(["rev-parse", "--is-inside-work-tree"], path)
    return rc == 0 and out.strip() == "true"


def ls_files(path: str | Path) -> list[str]:
    rc, out, _ = git(["ls-files"], path)
    if rc != 0:
        return []
    return [line for line in out.splitlines() if line]


def log_identities(path: str | Path, refs: str = "--all", max_commits: int = 5000) -> list[tuple[str, str, str, str]]:
    rc, out, _ = git(
        ["log", refs, f"--max-count={max_commits}", "--format=%ae%n%an%n%ce%n%cn"],
        path,
    )
    if rc != 0:
        return []
    lines = out.splitlines()
    identities = []
    for i in range(0, len(lines) - 3, 4):
        identities.append((lines[i], lines[i + 1], lines[i + 2], lines[i + 3]))
    return identities


def log_messages(path: str | Path, refs: str = "--all", max_commits: int = 5000) -> list[str]:
    rc, out, _ = git(
        ["log", refs, f"--max-count={max_commits}", "--format=%s%n%b%x00"],
        path,
    )
    if rc != 0:
        return []
    return [chunk for chunk in out.split("\x00") if chunk.strip()]


def refs(path: str | Path) -> list[str]:
    rc, out, _ = git(["for-each-ref", "--format=%(refname)"], path)
    if rc != 0:
        return []
    return [line for line in out.splitlines() if line]


def last_commit_iso(path: str | Path) -> str | None:
    rc, out, _ = git(["log", "-1", "--format=%cI"], path)
    if rc != 0 or not out.strip():
        return None
    return out.strip()


def commit_count(path: str | Path) -> int:
    rc, out, _ = git(["rev-list", "--count", "--all"], path)
    if rc != 0:
        return 0
    try:
        return int(out.strip())
    except ValueError:
        return 0


def added_paths_ever(path: str | Path, patterns: list[str]) -> list[str]:
    rc, out, _ = git(
        ["log", "--all", "--diff-filter=A", "--name-only", "--format=", "--", *patterns],
        path,
    )
    if rc != 0:
        return []
    return [line for line in out.splitlines() if line]
