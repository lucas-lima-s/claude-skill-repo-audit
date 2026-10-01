from __future__ import annotations

import sys
from pathlib import Path

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
    ctx = ctx_factory(repo, run_tests=True, trust_target=True)
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
    ctx = ctx_factory(repo, run_tests=True, trust_target=True)
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
    ctx = ctx_factory(repo, run_tests=True, trust_target=True)
    results = test_execution.run(ctx)
    assert results[0].severity == Severity.FAIL


def test_explicit_command_takes_precedence(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n"})
    ctx = ctx_factory(repo, run_tests=False)
    ctx.config.tests.command = ("python", "-c", "print('hi')")
    resolved = test_execution._resolve_command(ctx)
    assert resolved == ["python", "-c", "print('hi')"]


def _marker_repo(tmp_path, git_repo_factory):
    marker = tmp_path / "executed.txt"
    script = tmp_path / "touch_marker.py"
    script.write_text(f"open({str(marker)!r}, 'w').write('x')\n", encoding="utf-8")
    command = [Path(sys.executable).as_posix(), script.as_posix()]
    toml_line = "command = [" + ", ".join(f"'{part}'" for part in command) + "]"
    repo = git_repo_factory(tmp_path / "repo", {"repo-audit.toml": f"[tests]\n{toml_line}\n"})
    return repo, marker


def test_untrusted_target_is_never_executed(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo, marker = _marker_repo(tmp_path, git_repo_factory)
    ctx = ctx_factory(repo, run_tests=True)
    results = test_execution.run(ctx)
    assert results[0].severity == Severity.INFO
    assert "--trust-target" in results[0].message
    assert not marker.exists()


def test_trusted_target_runs_its_configured_command(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo, marker = _marker_repo(tmp_path, git_repo_factory)
    ctx = ctx_factory(repo, run_tests=True, trust_target=True)
    results = test_execution.run(ctx)
    assert results[0].severity == Severity.OK
    assert marker.exists()
