from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime, timedelta

from auditlib.severity import Severity
from checks import deferred_work, github_meta, staleness, visual_assets


def _commit_at(repo, rel_days_ago: int) -> None:
    when = (datetime.now(UTC) - timedelta(days=rel_days_ago)).strftime("%Y-%m-%dT%H:%M:%S")
    env = {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_AUTHOR_DATE": when,
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_COMMITTER_DATE": when,
        "PATH": os.environ.get("PATH", ""),
    }
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "backdated"],
        cwd=repo,
        check=True,
        env=env,
    )


def test_staleness_ok_when_recent(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n"})
    ctx = ctx_factory(repo)
    results = staleness.run(ctx)
    assert results[0].severity == Severity.OK


def test_staleness_warns_when_old(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n"})
    (repo / "README.md").write_text("# hi again\n", encoding="utf-8")
    _commit_at(repo, 800)
    ctx = ctx_factory(repo)
    results = staleness.run(ctx)
    assert results[0].severity == Severity.WARN
    assert results[0].evidence["age_days"] >= 700


def test_github_meta_offline_missing_repo_meta_is_info(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n"})
    ctx = ctx_factory(repo, offline=True)
    results = github_meta.run(ctx)
    assert results[0].check == "github.metadata_unavailable"


def test_github_meta_offline_reads_repo_meta_toml(tmp_path, git_repo_factory, ctx_factory) -> None:
    meta = (
        'description = "A description long enough to pass the minimum length check easily."\ntopics = ["a", "b", "c"]\n'
    )
    repo = git_repo_factory(tmp_path / "repo", {".github/repo-meta.toml": meta})
    ctx = ctx_factory(repo, offline=True)
    results = github_meta.run(ctx)
    assert results == []


def test_github_meta_flags_short_description(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(
        tmp_path / "repo", {".github/repo-meta.toml": 'description = "too short"\ntopics = ["a", "b", "c"]\n'}
    )
    ctx = ctx_factory(repo, offline=True)
    results = github_meta.run(ctx)
    assert any(r.check == "github.description" for r in results)


def test_github_meta_flags_bad_topic_count(tmp_path, git_repo_factory, ctx_factory) -> None:
    meta = 'description = "A description long enough to pass the minimum length check easily."\ntopics = ["a"]\n'
    repo = git_repo_factory(tmp_path / "repo", {".github/repo-meta.toml": meta})
    ctx = ctx_factory(repo, offline=True)
    results = github_meta.run(ctx)
    assert any(r.check == "github.topics" for r in results)


def test_deferred_work_flags_roadmap_file(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"ROADMAP.md": "# Roadmap\n"})
    ctx = ctx_factory(repo)
    results = deferred_work.run(ctx)
    assert any(r.file == "ROADMAP.md" for r in results)


def test_deferred_work_flags_inline_todo(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"src/app.py": "# TODO: fix this\nx = 1\n"})
    ctx = ctx_factory(repo)
    results = deferred_work.run(ctx)
    assert any(r.file == "src/app.py" for r in results)


def test_deferred_work_silent_when_clean(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"src/app.py": "x = 1\n", "README.md": "# hi\n"})
    ctx = ctx_factory(repo)
    assert deferred_work.run(ctx) == []


def test_visual_assets_inactive_without_detection(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n"})
    ctx = ctx_factory(repo)
    assert visual_assets.run(ctx) == []


def test_visual_assets_required_but_missing_fails(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n"})
    ctx = ctx_factory(repo)
    ctx.config.visual.required = True
    results = visual_assets.run(ctx)
    assert results[0].severity == Severity.FAIL


def test_visual_assets_present_and_referenced_is_ok(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "![shot](docs/shot.png)\n", "docs/shot.png": "fake-bytes"})
    ctx = ctx_factory(repo)
    ctx.config.visual.required = True
    results = visual_assets.run(ctx)
    assert results[0].severity == Severity.OK


def test_github_token_never_comes_from_target_env(tmp_path, monkeypatch) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / ".env").write_text("GITHUB_TOKEN=from-target\n", encoding="utf-8")
    monkeypatch.chdir(target)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("AGENT_WORKBENCH_ROOT", raising=False)
    monkeypatch.setattr(github_meta, "_gh_auth_token", lambda: None)
    assert github_meta.resolve_github_token() is None


def test_github_token_prefers_environment(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "from-env")
    monkeypatch.setattr(github_meta, "_gh_auth_token", lambda: "from-gh")
    assert github_meta.resolve_github_token() == "from-env"


def test_github_token_falls_back_to_gh(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("AGENT_WORKBENCH_ROOT", raising=False)
    monkeypatch.setattr(github_meta, "_gh_auth_token", lambda: "from-gh")
    assert github_meta.resolve_github_token() == "from-gh"
