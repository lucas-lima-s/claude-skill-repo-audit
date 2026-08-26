# Contributing

## Setup

```bash
uv sync
uv run pytest -q
uv run ruff check . && uv run ruff format .
```

## Adding a check

1. Write a module under `scripts/checks/` (repo-audit-only) or
   `scripts/auditlib/checks/` (generic — true of any repository, not just a
   repo-audit-flavored one). Register it with
   `@register("your_module_name")` on a `run(ctx: CheckContext) -> list[CheckResult]`
   function; the registry key is the module name, and a single `run` can
   emit multiple `CheckResult`s under different dotted `check` ids.
2. Add the registry key to the relevant `profiles/*.toml` `enabled_checks`
   list (usually `portfolio.toml`; `public`/`local` inherit via `extends`
   unless you need a different severity, in which case add an
   `[overrides]` entry).
3. Add one positive test (the check fires) and one negative test (it stays
   silent on clean input) to the matching `tests/test_*.py` file.
4. Add a section to `docs/rules.md`: what it checks, the severity per
   profile, why it matters for a public repo, and the concrete fix.
5. Add a `## [Unreleased]` entry to `CHANGELOG.md`.

## Adding a layer-2 prompt

Add a markdown file to `scripts/auditlib/prompts/` (generic) or
`scripts/prompts/` (repo-audit-only) starting with
`<!-- inputs: a.md, b.md, dir -->`, then `## What to read`,
`## What to look for`, `## What to ignore`, `## Output` with the exact
finding JSON shape. State the hard rule explicitly: never emit `FAIL`; cap
at `WARN`; do not invent findings to pad the report. Add the prompt id to
the profile(s) that should run it, and to `docs/layer2_prompts.md`.

## The no-plaintext-secret rule

**No real secret and no real employer term may ever be committed to this
repository.** Test fixtures (`scripts/make_fixture.py`) assemble every
dangerous literal — the planted AWS-shaped key, the planted corporate
email, the planted denylist term — from string chunks at runtime, never as
a contiguous literal in source. If you add a new fixture or test that needs
a secret-shaped string, follow the same pattern; a literal `AKIA...` in a
committed file will trip GitHub's own push protection and block the push.

## Commit policy

- English subjects, [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`, `style:`).
- Keep the git identity for this repo scoped locally
  (`git config user.email`/`user.name`) rather than relying on whatever the
  machine's global identity happens to be — that is exactly what
  `history.author_identity` exists to catch.
