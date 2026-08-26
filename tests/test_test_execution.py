from __future__ import annotations

import sys

from auditlib.severity import Severity
from checks import test_execution


def test_disabled_returns_info(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n"})
    ctx = ctx_factory(repo, run_tests=False)
    results = test_execution.run(ctx)
    assert results[0].severity == Severity.INFO
    assert results[0].message == "skipped (--no-run-tests)"


def test_no_command_resolved_warns(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n"})
    ctx = ctx_factory(repo, run_tests=True)
    results = test_execution.run(ctx)
    assert results[0].severity == Severity.WARN


def test_pytest_via_dev_deps_passes(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(
        tmp_path / "repo",
        {
            "pyproject.toml": '[project]\nname = "x"\n\n[dependency-groups]\ndev = ["pytest"]\n',
            "tests/test_ok.py": "def test_ok():\n    assert True\n",
        },
    )
    ctx = ctx_factory(repo, run_tests=True)
    results = test_execution.run(ctx)
    assert results[0].severity == Severity.OK
    assert results[0].evidence["command"][0] == sys.executable


def test_pytest_failure_reported(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(
        tmp_path / "repo",
        {
            "pyproject.toml": '[project]\nname = "x"\n\n[dependency-groups]\ndev = ["pytest"]\n',
            "tests/test_fail.py": "def test_fail():\n    assert False\n",
        },
    )
    ctx = ctx_factory(repo, run_tests=True)
    results = test_execution.run(ctx)
    assert results[0].severity == Severity.FAIL


def test_explicit_command_takes_precedence(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n"})
    ctx = ctx_factory(repo, run_tests=False)
    ctx.config.tests.command = ("python", "-c", "print('hi')")
    resolved = test_execution._resolve_command(ctx)
    assert resolved == ["python", "-c", "print('hi')"]
