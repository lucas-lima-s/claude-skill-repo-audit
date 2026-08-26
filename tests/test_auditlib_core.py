from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from auditlib.config import ArtifactRule, load_config, load_profile
from auditlib.context import build_context
from auditlib.severity import CheckResult, Severity, cap_severity, worst

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def test_severity_rank_order() -> None:
    assert Severity.OK.rank < Severity.INFO.rank < Severity.WARN.rank < Severity.FAIL.rank


def test_check_result_to_dict_serializes_severity_value() -> None:
    result = CheckResult(check="x.y", severity=Severity.WARN, message="m")
    data = result.to_dict()
    assert data["severity"] == "WARN"
    assert data["check"] == "x.y"
    assert data["evidence"] == {}


def test_cap_severity_caps_above_ceiling() -> None:
    assert cap_severity(Severity.FAIL, Severity.WARN) == Severity.WARN
    assert cap_severity(Severity.INFO, Severity.WARN) == Severity.INFO


def test_worst_picks_highest_rank() -> None:
    results = [
        CheckResult(check="a", severity=Severity.OK, message=""),
        CheckResult(check="b", severity=Severity.WARN, message=""),
        CheckResult(check="c", severity=Severity.INFO, message=""),
    ]
    assert worst(results) == Severity.WARN


def test_load_profile_resolves_extends_chain() -> None:
    profile = load_profile(PROFILES_DIR, "local")
    assert profile.extends == "public"
    assert "artifacts" in profile.enabled_checks
    assert profile.downgrade_warn_to_info is True
    assert profile.overrides.get("deferred_work.marker") == "INFO"


def test_load_profile_unknown_name_exits() -> None:
    with pytest.raises(SystemExit):
        load_profile(PROFILES_DIR, "does-not-exist")


def test_load_profile_cycle_detected(tmp_path: Path) -> None:
    (tmp_path / "a.toml").write_text('extends = "b"\n', encoding="utf-8")
    (tmp_path / "b.toml").write_text('extends = "a"\n', encoding="utf-8")
    with pytest.raises(SystemExit):
        load_profile(tmp_path, "a")


def test_artifact_rule_fields() -> None:
    rule = ArtifactRule(path="README.md", missing=Severity.FAIL, requires="none")
    assert rule.path == "README.md"
    assert rule.missing == Severity.FAIL


def test_load_config_unions_denylist_terms(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "repo-audit.toml").write_text('[denylist]\nterms = ["foo"]\n', encoding="utf-8")
    (repo / "repo-audit.local.toml").write_text('[denylist]\nterms = ["bar"]\n', encoding="utf-8")

    tool_root = Path(__file__).resolve().parent.parent
    config = load_config(repo_path=repo, tool_root=tool_root)

    assert "foo" in config.denylist.terms
    assert "bar" in config.denylist.terms


def test_load_config_cli_flag_wins_over_repo_config(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "repo-audit.toml").write_text("[staleness]\nwarn_days = 30\n", encoding="utf-8")

    tool_root = Path(__file__).resolve().parent.parent
    config = load_config(repo_path=repo, tool_root=tool_root)
    assert config.staleness.warn_days == 30


def test_load_config_ships_structural_public_domains() -> None:
    tool_root = Path(__file__).resolve().parent.parent
    repo = tool_root / "examples" / "clean_repo"
    config = load_config(repo_path=repo, tool_root=tool_root)
    assert "users.noreply.github.com" in config.denylist.public_email_domains


def test_context_iter_tracked_git_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "b.txt").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init"],
        cwd=repo,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            "PATH": os.environ.get("PATH", ""),
        },
    )

    profile = load_profile(PROFILES_DIR, "portfolio")
    config = load_config(repo_path=repo, tool_root=Path(__file__).resolve().parent.parent)
    ctx = build_context(repo_path=repo, profile=profile, config=config, offline=True, run_tests=False)

    assert ctx.is_git_repo is True
    py_files = [p.name for p in ctx.iter_tracked("*.py")]
    assert py_files == ["a.py"]


def test_context_iter_tracked_non_git_falls_back_to_filesystem(tmp_path: Path) -> None:
    repo = tmp_path / "plain"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")

    profile = load_profile(PROFILES_DIR, "portfolio")
    config = load_config(repo_path=repo, tool_root=Path(__file__).resolve().parent.parent)
    ctx = build_context(repo_path=repo, profile=profile, config=config, offline=True, run_tests=False)

    assert ctx.is_git_repo is False
    py_files = [p.name for p in ctx.iter_tracked("*.py")]
    assert py_files == ["a.py"]
