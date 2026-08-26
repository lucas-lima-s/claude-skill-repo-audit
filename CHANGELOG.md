# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-25

### Added

- `auditlib`, the shared repo-level engine: `Severity`/`CheckResult`,
  `CheckContext` with git-aware and filesystem-fallback file iteration,
  `Profile`/`AuditConfig` loading with `extends`-chain resolution and layered
  TOML merging, a check registry, a layer-1 runner with per-check error
  isolation, schema-v2 report building, and a layer-2 severity cap.
- Nine generic, repository-agnostic layer-1 checks: `artifacts` (the
  publish-readiness scorecard), `gitattributes`, `gitignore`, `pyproject`,
  `dev_deps`, `ci_workflow`, `changelog_format`, `python_style`, and
  `hardcoded_paths`.
- Four generic layer-2 prompts: `readme_quality`, `setup_completeness`,
  `changelog_significance`, `language_coherence`.
- Ten repo-audit-only layer-1 checks: `secrets` (provider patterns and
  entropy), `git_history` (author identity, denylisted terms, ref names),
  `content_denylist`, `test_execution`, `language_truth`, `readme_links`,
  `visual_assets`, `staleness`, `github_meta`, `deferred_work`.
- One repo-audit-only layer-2 prompt: `portfolio_narrative`.
- `portfolio`, `public`, and `local` profiles with an `extends` chain and
  per-check severity overrides.
- `scripts/audit.py` (single-repo CLI), `scripts/scan.py` (parallel
  multi-repo scan via `ProcessPoolExecutor`), `scripts/dashboard.py`
  (JSON/markdown rendering with a configurable fail-on threshold).
- `scripts/make_fixture.py`, which materializes throwaway clean/dirty git
  fixtures with every dangerous literal assembled at runtime from string
  chunks, and `examples/clean_repo/`, the real repo it copies as a template.
- `scripts/render_demo.py`, which turns a JSON report into the light/dark
  SVG cards used in this README.
- The JSON contract (schema v2) for both a single-repo report and a
  multi-repo dashboard, documented in `docs/json_contract.md`.
- A full pytest suite, including a self-audit ("dogfood") test that runs
  the tool against its own repository.
