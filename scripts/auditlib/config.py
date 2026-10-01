from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from auditlib.severity import Severity

UNION_PATHS = {
    ("denylist", "terms"),
    ("denylist", "regexes"),
    ("denylist", "soft_regexes"),
    ("denylist", "email_domains"),
    ("secrets", "extra_patterns"),
    ("secrets", "ignore_paths"),
}


@dataclass
class ArtifactRule:
    path: str
    missing: Severity
    requires: str | None = None


@dataclass
class Profile:
    name: str
    extends: str | None
    artifacts: dict[str, ArtifactRule]
    enabled_checks: tuple[str, ...]
    layer2_prompts: tuple[str, ...]
    downgrade_warn_to_info: bool
    overrides: dict[str, str]


def _parse_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load_profile(
    profiles_dir: Path,
    name: str,
    _depth: int = 0,
    _seen: tuple[str, ...] = (),
) -> Profile:
    if _depth > 4:
        raise SystemExit(f"repo-audit: profile extends chain exceeds max depth resolving '{name}'")
    if name in _seen:
        raise SystemExit(f"repo-audit: profile extends cycle detected: {' -> '.join((*_seen, name))}")

    profile_path = profiles_dir / f"{name}.toml"
    if not profile_path.exists():
        raise SystemExit(f"repo-audit: unknown profile '{name}' ({profile_path} not found)")

    raw = _parse_toml(profile_path)
    extends = raw.get("extends") or None

    artifacts: dict[str, ArtifactRule] = {}
    enabled_checks: tuple[str, ...] = ()
    layer2_prompts: tuple[str, ...] = ()
    downgrade = False
    overrides: dict[str, str] = {}

    if extends:
        parent = load_profile(profiles_dir, extends, _depth + 1, (*_seen, name))
        artifacts = dict(parent.artifacts)
        enabled_checks = parent.enabled_checks
        layer2_prompts = parent.layer2_prompts
        downgrade = parent.downgrade_warn_to_info
        overrides = dict(parent.overrides)

    if raw.get("enabled_checks"):
        enabled_checks = tuple(raw["enabled_checks"])
    if raw.get("layer2_prompts"):
        layer2_prompts = tuple(raw["layer2_prompts"])
    if "downgrade_warn_to_info" in raw:
        downgrade = bool(raw["downgrade_warn_to_info"])

    for key, spec in raw.get("artifacts", {}).items():
        artifacts[key] = ArtifactRule(
            path=spec["path"],
            missing=Severity(spec["missing"]),
            requires=spec.get("requires"),
        )

    overrides.update(raw.get("overrides", {}))

    return Profile(
        name=raw.get("name", name),
        extends=extends,
        artifacts=artifacts,
        enabled_checks=enabled_checks,
        layer2_prompts=layer2_prompts,
        downgrade_warn_to_info=downgrade,
        overrides=overrides,
    )


@dataclass
class IdentitySection:
    allowed_author_emails: tuple[str, ...] = ()
    allowed_author_names: tuple[str, ...] = ()


@dataclass
class DenylistSection:
    terms: tuple[str, ...] = ()
    email_domains: tuple[str, ...] = ()
    regexes: tuple[str, ...] = ()
    soft_regexes: tuple[str, ...] = ()
    severity: str = "FAIL"
    allow_paths: tuple[str, ...] = ()
    allow_marker: str = "repo-audit: allow-term"
    flag_non_public_author_domains: bool = True
    public_email_domains: tuple[str, ...] = ()


@dataclass
class SecretsSection:
    ignore_paths: tuple[str, ...] = ()
    extra_patterns: tuple[str, ...] = ()
    entropy_threshold: float = 4.0
    min_length: int = 20


@dataclass
class HistorySection:
    max_commits: int = 5000


@dataclass
class TestsSection:
    command: tuple[str, ...] | None = None
    timeout_seconds: int = 300


@dataclass
class VisualSection:
    required: bool = False
    asset_globs: tuple[str, ...] = (
        "docs/*.png",
        "docs/*.gif",
        "docs/*.svg",
        "docs/*.webp",
        "assets/*.png",
        "assets/*.gif",
        "screenshots/**",
    )


@dataclass
class StalenessSection:
    warn_days: int = 180
    fail_days: int = 0


@dataclass
class GithubSection:
    description_min_length: int = 30
    topics_min: int = 3
    topics_max: int = 5


@dataclass
class AuditConfig:
    identity: IdentitySection = field(default_factory=IdentitySection)
    denylist: DenylistSection = field(default_factory=DenylistSection)
    secrets: SecretsSection = field(default_factory=SecretsSection)
    history: HistorySection = field(default_factory=HistorySection)
    tests: TestsSection = field(default_factory=TestsSection)
    visual: VisualSection = field(default_factory=VisualSection)
    staleness: StalenessSection = field(default_factory=StalenessSection)
    github: GithubSection = field(default_factory=GithubSection)


def _default_raw() -> dict[str, Any]:
    return {
        "identity": {"allowed_author_emails": [], "allowed_author_names": []},
        "denylist": {
            "terms": [],
            "email_domains": [],
            "regexes": [],
            "soft_regexes": [],
            "severity": "FAIL",
            "allow": {"paths": [], "marker": "repo-audit: allow-term"},
            "structural": {"flag_non_public_author_domains": True, "public_email_domains": []},
        },
        "secrets": {"ignore_paths": [], "extra_patterns": [], "entropy_threshold": 4.0, "min_length": 20},
        "history": {"max_commits": 5000},
        "tests": {"command": None, "timeout_seconds": 300},
        "visual": {
            "required": False,
            "asset_globs": [
                "docs/*.png",
                "docs/*.gif",
                "docs/*.svg",
                "docs/*.webp",
                "assets/*.png",
                "assets/*.gif",
                "screenshots/**",
            ],
        },
        "staleness": {"warn_days": 180, "fail_days": 0},
        "github": {"description_min_length": 30, "topics_min": 3, "topics_max": 5},
    }


def _deep_merge(base: dict[str, Any], incoming: dict[str, Any], prefix: tuple[str, ...] = ()) -> dict[str, Any]:
    result = dict(base)
    for key, value in incoming.items():
        path = (*prefix, key)
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value, path)
        elif isinstance(value, list) and path in UNION_PATHS and isinstance(result.get(key), list):
            merged = list(result[key])
            for item in value:
                if item not in merged:
                    merged.append(item)
            result[key] = merged
        else:
            result[key] = value
    return result


def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return str(a) == str(b)


def _build_config(raw: dict[str, Any]) -> AuditConfig:
    identity = raw.get("identity", {})
    denylist = raw.get("denylist", {})
    allow = denylist.get("allow", {})
    structural = denylist.get("structural", {})
    secrets = raw.get("secrets", {})
    history = raw.get("history", {})
    tests = raw.get("tests", {})
    visual = raw.get("visual", {})
    staleness = raw.get("staleness", {})
    github = raw.get("github", {})

    command = tests.get("command")
    return AuditConfig(
        identity=IdentitySection(
            allowed_author_emails=tuple(identity.get("allowed_author_emails", [])),
            allowed_author_names=tuple(identity.get("allowed_author_names", [])),
        ),
        denylist=DenylistSection(
            terms=tuple(denylist.get("terms", [])),
            email_domains=tuple(denylist.get("email_domains", [])),
            regexes=tuple(denylist.get("regexes", [])),
            soft_regexes=tuple(denylist.get("soft_regexes", [])),
            severity=denylist.get("severity", "FAIL"),
            allow_paths=tuple(allow.get("paths", [])),
            allow_marker=allow.get("marker", "repo-audit: allow-term"),
            flag_non_public_author_domains=bool(structural.get("flag_non_public_author_domains", True)),
            public_email_domains=tuple(structural.get("public_email_domains", [])),
        ),
        secrets=SecretsSection(
            ignore_paths=tuple(secrets.get("ignore_paths", [])),
            extra_patterns=tuple(secrets.get("extra_patterns", [])),
            entropy_threshold=float(secrets.get("entropy_threshold", 4.0)),
            min_length=int(secrets.get("min_length", 20)),
        ),
        history=HistorySection(max_commits=int(history.get("max_commits", 5000))),
        tests=TestsSection(
            command=tuple(command) if command else None,
            timeout_seconds=int(tests.get("timeout_seconds", 300)),
        ),
        visual=VisualSection(
            required=bool(visual.get("required", False)),
            asset_globs=tuple(visual.get("asset_globs", VisualSection().asset_globs)),
        ),
        staleness=StalenessSection(
            warn_days=int(staleness.get("warn_days", 180)),
            fail_days=int(staleness.get("fail_days", 0)),
        ),
        github=GithubSection(
            description_min_length=int(github.get("description_min_length", 30)),
            topics_min=int(github.get("topics_min", 3)),
            topics_max=int(github.get("topics_max", 5)),
        ),
    )


def load_config(
    repo_path: Path,
    tool_root: Path,
    cli_config_path: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> AuditConfig:
    raw = _default_raw()

    denylist_default = tool_root / "config" / "denylist.default.toml"
    if denylist_default.exists():
        raw = _deep_merge(raw, _parse_toml(denylist_default))

    is_self_audit = _same_path(repo_path, tool_root)
    if is_self_audit:
        tool_repo_audit = tool_root / "repo-audit.toml"
        if tool_repo_audit.exists():
            raw = _deep_merge(raw, _parse_toml(tool_repo_audit))
    else:
        operator_local = tool_root / "repo-audit.local.toml"
        if operator_local.exists():
            raw = _deep_merge(raw, _parse_toml(operator_local))

    repo_toml = repo_path / "repo-audit.toml"
    if repo_toml.exists():
        raw = _deep_merge(raw, _parse_toml(repo_toml))

    repo_local = repo_path / "repo-audit.local.toml"
    if repo_local.exists():
        raw = _deep_merge(raw, _parse_toml(repo_local))

    if cli_config_path is not None and cli_config_path.exists():
        raw = _deep_merge(raw, _parse_toml(cli_config_path))

    if cli_overrides:
        raw = _deep_merge(raw, cli_overrides)

    return _build_config(raw)
