from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from auditlib import gitutil
from auditlib.config import AuditConfig, Profile

EXCLUDED_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}


@dataclass
class CheckContext:
    repo_path: str
    profile: Profile
    config: AuditConfig
    offline: bool
    run_tests: bool
    tracked_files: tuple[str, ...]
    is_git_repo: bool
    history_secrets: bool = False
    trust_target: bool = False

    def path(self, rel: str) -> Path:
        return Path(self.repo_path) / rel

    def exists(self, rel: str) -> bool:
        return self.path(rel).exists()

    def read_text(self, rel: str) -> str | None:
        target = self.path(rel)
        try:
            return target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def iter_tracked(self, *globs: str) -> Iterator[Path]:
        if self.tracked_files:
            base = Path(self.repo_path)
            for rel in self.tracked_files:
                candidate = Path(rel)
                if not globs or any(candidate.match(g) for g in globs):
                    yield base / rel
            return
        base = Path(self.repo_path)
        yield from _walk_filesystem(base, globs)


def _walk_filesystem(base: Path, globs: tuple[str, ...]) -> Iterator[Path]:
    for entry in base.rglob("*"):
        if not entry.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in entry.relative_to(base).parts):
            continue
        rel = entry.relative_to(base)
        if not globs or any(rel.match(g) for g in globs):
            yield entry


@dataclass
class TargetForLayer2:
    prompt_id: str
    prompt_file: str
    files: list[str]


def build_context(
    repo_path: Path,
    profile: Profile,
    config: AuditConfig,
    offline: bool,
    run_tests: bool,
    history_secrets: bool = False,
    trust_target: bool = False,
) -> CheckContext:
    is_git = gitutil.is_repo(repo_path)
    tracked = tuple(gitutil.ls_files(repo_path)) if is_git else ()
    return CheckContext(
        repo_path=str(repo_path),
        profile=profile,
        config=config,
        offline=offline,
        run_tests=run_tests,
        tracked_files=tracked,
        is_git_repo=is_git,
        history_secrets=history_secrets,
        trust_target=trust_target,
    )
