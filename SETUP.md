# Setup

## Requirements

- Python 3.11 or newer (the tool is stdlib-only; `tomllib` and `StrEnum`
  both require 3.11).
- [`uv`](https://docs.astral.sh/uv/) — optional but recommended; without it,
  run the scripts with any Python 3.11+ interpreter and `pip install -e .`
  the dev group yourself (`ruff`, `pytest`).
- `git` on `PATH` — required for anything beyond `staleness`/`github_meta`
  against a repo that isn't a git working tree.
- [`gh`](https://cli.github.com/) — optional. Only used as a fallback source
  for a GitHub token when `github_meta` runs online and `GITHUB_TOKEN` is
  unset.

## Install

```bash
git clone <this-repo-url> ~/.claude/skills/repo-audit
cd ~/.claude/skills/repo-audit
uv sync
```

## Environment variables

| Variable | Used by | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | `github_meta`, `language_truth` (online mode) | Auth for `api.github.com`. Falls back to `gh auth token` when unset. |
| `REPO_AUDIT_NEVER_EXIT_NONZERO` | `audit.py`, `scan.py` | Set to `1` to force exit code `0` regardless of gate. Manual debugging only — never set this in CI. |
| `SKILLS_PYTHON` | not read by this tool directly | Present in `.env.example` for parity with other skills in a shared portfolio; harmless to leave unset here. |

`.env` is read only by `github_meta` (for `GITHUB_TOKEN`) and is otherwise
ignored by the tool. Copy `.env.example` to `.env` locally if you want an
online run without exporting the variable in your shell.

## Configuration precedence

`auditlib.config.load_config` merges, in this order (later wins; list
values are replaced except `denylist.terms|regexes|soft_regexes|email_domains`
and `secrets.extra_patterns|ignore_paths`, which are unioned):

1. `config/denylist.default.toml` (shipped with this tool — structural only)
2. `<this tool's own repo-audit.toml>`, but only when auditing this tool
   itself
3. `<audited-repo>/repo-audit.toml` (committed, generic)
4. `<audited-repo>/repo-audit.local.toml` (gitignored, machine-local)
5. `--config <path>` (an explicit override file)
6. Explicit CLI flags (e.g. `--offline`, `--run-tests`)

## The local-secrets pattern

Two files never get committed, mirroring each other:

- `.env` — real tokens. Copy from `.env.example`.
- `repo-audit.local.toml` — real denylist terms (an old employer's name, an
  internal ticket prefix, an internal domain). Copy from
  `repo-audit.local.toml.example` and fill in the real values.

**Never commit either file.** Both are listed in `.gitignore`; verify with:

```bash
git check-ignore -q .env && echo ok
git check-ignore -q repo-audit.local.toml && echo ok
```

The reasoning: a public denylist that names a real employer is exactly the
kind of string a portfolio repo is trying to scrub, and it would read as
fork lineage to anyone who saw it. Keeping the real terms local and
gitignored is what lets the *shipped* denylist stay structural (see
`config/denylist.default.toml`) while still being effective on the machine
that runs the audit.

## JSON contract

Every report follows schema v2 — see `docs/json_contract.md` for the full
shape of both a single-repo report and a multi-repo dashboard, and
`docs/rules.md` for what each check id means.

## Standalone invocation

The scripts have no dependency on being installed as a Claude Code skill —
they are plain Python entry points:

```bash
uv run python scripts/audit.py /path/to/repo --profile portfolio --json-out report.json
uv run python scripts/scan.py --repos repos.txt --out dashboard.json
uv run python scripts/dashboard.py --json dashboard.json --format md
```
