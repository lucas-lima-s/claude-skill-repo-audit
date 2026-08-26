from __future__ import annotations

from auditlib.severity import Severity
from checks import language_truth


def test_declared_python_matches_computed_primary_is_silent(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(
        tmp_path / "repo",
        {"pyproject.toml": "[project]\nname='x'\n", "src/app.py": "x = 1\n" * 50},
    )
    ctx = ctx_factory(repo)
    results = language_truth.run(ctx)
    assert not any(r.check == "language.declared_vs_real" for r in results)


def test_language_mismatch_fails_above_fifty_percent(tmp_path, git_repo_factory, ctx_factory) -> None:
    batch_lines = "\r\n".join(f"echo step {i}" for i in range(400)) + "\r\n"
    repo = git_repo_factory(
        tmp_path / "repo",
        {"pyproject.toml": "[project]\nname='x'\n", "build.bat": batch_lines, "src/app.py": "x = 1\n"},
    )
    ctx = ctx_factory(repo)
    results = language_truth.run(ctx)
    mismatch = [r for r in results if r.check == "language.declared_vs_real"]
    assert mismatch
    assert mismatch[0].severity == Severity.FAIL
    assert "linguist-vendored" in mismatch[0].remediation


def test_language_mismatch_warns_below_fifty_percent(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(
        tmp_path / "repo",
        {
            "pyproject.toml": "[project]\nname='x'\n",
            "build.bat": "echo hi\r\n" * 3,
            "src/app.py": "x = 1\n" * 3,
        },
    )
    ctx = ctx_factory(repo)
    results = language_truth.run(ctx)
    mismatch = [r for r in results if r.check == "language.declared_vs_real"]
    assert mismatch
    assert mismatch[0].severity == Severity.WARN
    assert mismatch[0].evidence["ratio"] < 0.5


def test_linguist_vendored_attribute_excludes_file_from_histogram(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(
        tmp_path / "repo",
        {
            "pyproject.toml": "[project]\nname='x'\n",
            "vendor.bat": "echo hi\r\n" * 100,
            "src/app.py": "x = 1\n" * 20,
            ".gitattributes": "vendor.bat linguist-vendored\n",
        },
    )
    ctx = ctx_factory(repo)
    results = language_truth.run(ctx)
    assert not any(r.check == "language.declared_vs_real" for r in results)
