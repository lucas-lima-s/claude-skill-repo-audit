from __future__ import annotations

from auditlib.severity import Severity
from checks import secrets


def _planted_aws_key() -> str:
    return "AK" + "IA" + "Q" * 16


def test_aws_pattern_matches_planted_key() -> None:
    key = _planted_aws_key()
    match = secrets.PATTERNS["aws_access_key"].search(f'AWS_KEY = "{key}"')
    assert match is not None
    assert match.group(0) == key


def test_redact_hides_middle_of_secret() -> None:
    redacted = secrets._redact(_planted_aws_key())
    assert redacted.startswith("AKIA")
    assert redacted.endswith("QQ")
    assert _planted_aws_key() not in redacted


def test_secrets_pattern_finding_on_tracked_file(tmp_path, git_repo_factory, ctx_factory) -> None:
    key = _planted_aws_key()
    repo = git_repo_factory(tmp_path / "repo", {"config.py": f'AWS_KEY = "{key}"\n'})
    ctx = ctx_factory(repo)
    results = secrets.run(ctx)
    pattern_findings = [r for r in results if r.check == "secrets.pattern"]
    assert pattern_findings
    assert all(key not in r.message for r in pattern_findings)


def test_secrets_entropy_fires_on_high_entropy_token(tmp_path, git_repo_factory, ctx_factory) -> None:
    token = "8mROq3F92kzLxTnE1pQwZaYsRtVuWc7bJdKfNiHgXo01234="
    repo = git_repo_factory(tmp_path / "repo", {"config.py": f'API_TOKEN = "{token}"\n'})
    ctx = ctx_factory(repo)
    results = secrets.run(ctx)
    assert any(r.check == "secrets.entropy" for r in results)


def test_secrets_entropy_suppressed_for_placeholder(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {"config.py": 'API_TOKEN = "changeme_replace_me_1234567890"\n'})
    ctx = ctx_factory(repo)
    results = secrets.run(ctx)
    assert not any(r.check == "secrets.entropy" for r in results)


def test_secrets_inline_allow_marker_suppresses_pattern(tmp_path, git_repo_factory, ctx_factory) -> None:
    key = _planted_aws_key()
    repo = git_repo_factory(tmp_path / "repo", {"config.py": f'AWS_KEY = "{key}"  # repo-audit: allow-secret\n'})
    ctx = ctx_factory(repo)
    results = secrets.run(ctx)
    assert not any(r.check == "secrets.pattern" for r in results)


def test_secrets_committed_env_is_fail(tmp_path, git_repo_factory, ctx_factory) -> None:
    repo = git_repo_factory(tmp_path / "repo", {".gitignore": "", ".env": "SECRET=x\n"})
    ctx = ctx_factory(repo)
    results = secrets.run(ctx)
    committed = [r for r in results if r.check == "secrets.committed_env"]
    assert any(r.severity == Severity.FAIL for r in committed)


def test_secrets_ignore_paths_skips_scanning(tmp_path, git_repo_factory, ctx_factory) -> None:
    key = _planted_aws_key()
    repo = git_repo_factory(tmp_path / "repo", {"tests/fixture.py": f'AWS_KEY = "{key}"\n'})
    ctx = ctx_factory(repo)
    ctx.config.secrets.ignore_paths = ("tests/**",)
    results = secrets.run(ctx)
    assert not any(r.check == "secrets.pattern" for r in results)


def test_shannon_entropy_of_repeated_char_is_zero() -> None:
    assert secrets._shannon_entropy("aaaaaaaa") == 0.0


def test_lockfile_hex_hashes_are_not_flagged_as_entropy(tmp_path, git_repo_factory, ctx_factory) -> None:
    lockfile_body = "\n".join(f'hash = "sha256:{("a1b2c3d4e5f6" * 6)[:64]}"' for _ in range(5))
    repo = git_repo_factory(tmp_path / "repo", {"uv.lock": lockfile_body})
    ctx = ctx_factory(repo)
    results = secrets.run(ctx)
    assert not any(r.file == "uv.lock" for r in results)
