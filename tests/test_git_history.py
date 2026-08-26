from __future__ import annotations

import os
import subprocess

from auditlib.severity import Severity
from checks import git_history


def test_not_a_git_repo_warns(tmp_path, ctx_factory) -> None:
    repo = tmp_path / "plain"
    repo.mkdir()
    ctx = ctx_factory(repo)
    results = git_history.run(ctx)
    assert len(results) == 1
    assert results[0].check == "history.not_a_repo"
    assert results[0].severity == Severity.WARN


def test_portfolio_identity_passes(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(
        tmp_path / "repo",
        {"README.md": "# hi\n"},
        author_email="106186397+lucas-lima-s@users.noreply.github.com",
    )
    ctx = ctx_factory(repo)
    results = git_history.run(ctx)
    assert not any(r.check == "history.author_identity" for r in results)


def test_corporate_identity_fails(tmp_path, git_repo_factory, ctx_factory) -> None:
    corporate_email = "dev" + "@" + "acme-corp" + ".example"
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n"}, author_email=corporate_email)
    ctx = ctx_factory(repo)
    results = git_history.run(ctx)
    identity_failures = [r for r in results if r.check == "history.author_identity"]
    assert identity_failures
    assert corporate_email in identity_failures[0].message


def test_public_provider_domain_passes(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n"}, author_email="someone@gmail.com")
    ctx = ctx_factory(repo)
    results = git_history.run(ctx)
    assert not any(r.check == "history.author_identity" for r in results)


def test_denylisted_term_in_commit_message_fails(tmp_path, git_repo_factory, ctx_factory) -> None:
    term = "acme" + "-corp"
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n"})
    (repo / "repo-audit.toml").write_text(f'[denylist]\nterms = ["{term}"]\n', encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    env = {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "PATH": os.environ.get("PATH", ""),
    }
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", f"chore: {term} rollout"],
        cwd=repo,
        check=True,
        env=env,
    )

    ctx = ctx_factory(repo)
    results = git_history.run(ctx)
    assert any(r.check == "history.commit_message" and r.severity == Severity.FAIL for r in results)


def test_single_commit_is_info(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n"})
    ctx = ctx_factory(repo)
    results = git_history.run(ctx)
    assert any(r.check == "history.single_commit" and r.severity == Severity.INFO for r in results)


def test_explicit_denylisted_email_domain_fails_even_if_public(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "# hi\n"}, author_email="someone@gmail.com")
    (repo / "repo-audit.toml").write_text('[denylist]\nemail_domains = ["gmail.com"]\n', encoding="utf-8")
    ctx = ctx_factory(repo)
    results = git_history.run(ctx)
    assert any(r.check == "history.author_identity" for r in results)
