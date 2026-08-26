from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
PROFILES_DIR = REPO_ROOT / "profiles"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from auditlib.config import load_config, load_profile  # noqa: E402
from auditlib.context import CheckContext, build_context  # noqa: E402


def build_ctx(
    repo_path: Path,
    profile_name: str = "portfolio",
    offline: bool = True,
    run_tests: bool = False,
    history_secrets: bool = False,
) -> CheckContext:
    profile = load_profile(PROFILES_DIR, profile_name)
    config = load_config(repo_path=repo_path, tool_root=REPO_ROOT)
    return build_context(
        repo_path=repo_path,
        profile=profile,
        config=config,
        offline=offline,
        run_tests=run_tests,
        history_secrets=history_secrets,
    )


@pytest.fixture
def ctx_factory():
    return build_ctx


def init_git_repo(repo_path: Path, files: dict[str, str], author_email: str = "t@example.com") -> Path:
    repo_path.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        target = repo_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    env = {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": author_email,
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": author_email,
        "PATH": os.environ.get("PATH", ""),
    }
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init"],
        cwd=repo_path,
        check=True,
        env=env,
    )
    return repo_path


@pytest.fixture
def git_repo_factory():
    return init_git_repo


def _make_fixture(kind: str, out_dir: Path) -> Path:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "make_fixture.py"), "--kind", kind, "--out", str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return out_dir


@pytest.fixture
def clean_repo(tmp_path: Path) -> Path:
    return _make_fixture("clean", tmp_path / "clean")


@pytest.fixture
def dirty_repo(tmp_path: Path) -> Path:
    return _make_fixture("dirty", tmp_path / "dirty")


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT
