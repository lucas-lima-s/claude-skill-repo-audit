from __future__ import annotations

from auditlib.severity import Severity
from checks import readme_links


def test_no_readme_is_silent(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"other.md": "no readme here\n"})
    ctx = ctx_factory(repo)
    assert readme_links.run(ctx) == []


def test_broken_relative_image_fails(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "![x](docs/missing.png)\n"})
    ctx = ctx_factory(repo)
    results = readme_links.run(ctx)
    assert any(r.check == "readme.broken_relative_image" and r.severity == Severity.FAIL for r in results)


def test_resolvable_relative_image_is_silent(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "![x](docs/shot.svg)\n", "docs/shot.svg": "<svg></svg>\n"})
    ctx = ctx_factory(repo)
    results = readme_links.run(ctx)
    assert results == []


def test_hotlinked_image_warns(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "![x](https://i.imgur.com/x.png)\n"})
    ctx = ctx_factory(repo)
    results = readme_links.run(ctx)
    warn = [r for r in results if r.check == "readme.hotlinked_image"]
    assert warn
    assert warn[0].severity == Severity.WARN
    assert "i.imgur.com" in warn[0].message


def test_allowlisted_badge_host_is_silent(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "![badge](https://img.shields.io/badge/x-y-green)\n"})
    ctx = ctx_factory(repo)
    results = readme_links.run(ctx)
    assert results == []


def test_broken_relative_link_warns(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"README.md": "See [docs](docs/missing.md) for details.\n"})
    ctx = ctx_factory(repo)
    results = readme_links.run(ctx)
    assert any(r.check == "readme.broken_relative_link" and r.severity == Severity.WARN for r in results)
