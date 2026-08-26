from __future__ import annotations

from auditlib.checks import (
    artifacts,
    changelog_format,
    ci_workflow,
    dev_deps,
    gitignore,
    hardcoded_paths,
    pyproject,
    python_style,
)
from auditlib.severity import Severity


def test_artifacts_scorecard(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n", "LICENSE": "MIT\n"})
    ctx = ctx_factory(repo)
    results = artifacts.run(ctx)
    scorecard = artifacts.scorecard(results)
    assert scorecard["total"] >= 2
    readme_result = next(r for r in results if r.file == "README.md")
    assert readme_result.severity == Severity.OK
    changelog_result = next(r for r in results if r.file == "CHANGELOG.md")
    assert changelog_result.severity == Severity.WARN


def test_gitignore_coverage_flags_missing_families(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(
        tmp_path / "repo",
        {"pyproject.toml": "[project]\nname='x'\n", ".gitignore": "*.log\n"},
    )
    ctx = ctx_factory(repo)
    results = gitignore.run(ctx)
    checks = {r.message for r in results}
    assert any("python bytecode cache" in m for m in checks)
    assert any("dotenv" in m for m in checks)


def test_gitignore_coverage_passes_when_all_families_present(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(
        tmp_path / "repo",
        {
            "pyproject.toml": "[project]\nname='x'\n",
            ".gitignore": "__pycache__/\n.venv/\n.env\n*.log\n.history/\n",
        },
    )
    ctx = ctx_factory(repo)
    results = gitignore.run(ctx)
    assert results == []


def test_pyproject_fail_on_invalid_toml(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"pyproject.toml": "not = [valid\n"})
    ctx = ctx_factory(repo)
    results = pyproject.run(ctx)
    assert any(r.severity == Severity.FAIL for r in results)


def test_pyproject_fail_when_no_tooling(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"pyproject.toml": "[project]\nname = 'x'\n"})
    ctx = ctx_factory(repo)
    results = pyproject.run(ctx)
    assert any(r.severity == Severity.FAIL and r.check == "pyproject.format" for r in results)


def test_pyproject_warn_when_formatter_missing(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(
        tmp_path / "repo",
        {"pyproject.toml": '[project]\nname = "x"\nrequires-python = ">=3.11"\n\n[tool.ruff]\nline-length = 100\n'},
    )
    ctx = ctx_factory(repo)
    results = pyproject.run(ctx)
    assert any(r.severity == Severity.WARN for r in results)
    assert not any(r.severity == Severity.FAIL for r in results)


def test_pyproject_ok_when_ruff_lint_and_format_present(tmp_path, git_repo_factory, ctx_factory) -> None:
    content = (
        '[project]\nname = "x"\nrequires-python = ">=3.11"\n\n'
        '[tool.ruff]\nline-length = 100\n\n[tool.ruff.format]\nquote-style = "double"\n'
    )
    repo = git_repo_factory(tmp_path / "repo", {"pyproject.toml": content})
    ctx = ctx_factory(repo)
    results = pyproject.run(ctx)
    assert any(r.severity == Severity.OK for r in results)


def test_dev_deps_warns_when_pytest_missing(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(
        tmp_path / "repo",
        {"pyproject.toml": "[project]\nname = 'x'\n", "tests/test_x.py": "def test_x():\n    assert True\n"},
    )
    ctx = ctx_factory(repo)
    results = dev_deps.run(ctx)
    assert any(r.severity == Severity.WARN for r in results)


def test_dev_deps_names_from_dependency_groups(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(
        tmp_path / "repo",
        {"pyproject.toml": '[project]\nname = "x"\n\n[dependency-groups]\ndev = ["pytest>=8.0", "ruff"]\n'},
    )
    ctx = ctx_factory(repo)
    names = dev_deps.dev_dependency_names(ctx)
    assert names == {"pytest", "ruff"}


def test_ci_workflow_matrix_ok(tmp_path, git_repo_factory, ctx_factory) -> None:
    workflow = (
        "name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
        "    strategy:\n      matrix:\n        python-version: ['3.11']\n"
        "    steps:\n      - uses: actions/checkout@v4\n        with:\n          fetch-depth: 0\n"
    )
    repo = git_repo_factory(tmp_path / "repo", {".github/workflows/ci.yml": workflow})
    ctx = ctx_factory(repo)
    results = ci_workflow.run(ctx)
    assert any(r.check == "ci_workflow.matrix" and r.severity == Severity.OK for r in results)


def test_ci_workflow_shallow_clone_warns_when_history_scan_enabled(tmp_path, git_repo_factory, ctx_factory) -> None:
    workflow = (
        "name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
        "    strategy:\n      matrix:\n        python-version: ['3.11']\n"
        "    steps:\n      - uses: actions/checkout@v4\n"
    )
    repo = git_repo_factory(tmp_path / "repo", {".github/workflows/ci.yml": workflow})
    ctx = ctx_factory(repo, profile_name="portfolio")
    results = ci_workflow.run(ctx)
    assert any(r.check == "ci_workflow.shallow_clone" for r in results)


def test_changelog_format_warns_without_unreleased(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"CHANGELOG.md": "# Changelog\n\n## [0.1.0]\n"})
    ctx = ctx_factory(repo)
    results = changelog_format.run(ctx)
    assert any(r.severity == Severity.WARN for r in results)


def test_changelog_format_ok(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n## [0.1.0]\n"})
    ctx = ctx_factory(repo)
    results = changelog_format.run(ctx)
    assert results[0].severity == Severity.OK


def test_python_style_flags_deprecated_typing_aliases(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(
        tmp_path / "repo",
        {"src/mod.py": "from __future__ import annotations\nfrom typing import List, Dict\n\nx: List[int] = []\n"},
    )
    ctx = ctx_factory(repo)
    results = python_style.run(ctx)
    assert any(r.check == "python_style.typing_aliases" for r in results)


def test_python_style_flags_missing_future_annotations(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"src/mod.py": "x = 1\n"})
    ctx = ctx_factory(repo)
    results = python_style.run(ctx)
    assert any(r.check == "python_style.future" and r.severity == Severity.WARN for r in results)


def test_python_style_syntax_error_reported(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"src/broken.py": "def f(:\n    pass\n"})
    ctx = ctx_factory(repo)
    results = python_style.run(ctx)
    assert any(r.check == "python_style.parse" for r in results)


def test_hardcoded_paths_flags_windows_user_path(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "See C:/Users/someone/project for details.\n"})
    ctx = ctx_factory(repo)
    results = hardcoded_paths.run(ctx)
    assert any(r.severity == Severity.FAIL for r in results)


def test_hardcoded_paths_suppressed_by_env_var_marker(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "See $HOME/Users/someone for details.\n"})
    ctx = ctx_factory(repo)
    results = hardcoded_paths.run(ctx)
    assert results == []


def test_hardcoded_paths_suppressed_by_inline_marker(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "C:/Users/someone/project  # repo-audit: allow-path\n"})
    ctx = ctx_factory(repo)
    results = hardcoded_paths.run(ctx)
    assert results == []
