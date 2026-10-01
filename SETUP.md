# Setup

## Requirements

- Python 3.11 or newer (the tool is stdlib-only; `tomllib` and `StrEnum`
  both require 3.11).
- [`uv`](https://docs.astral.sh/uv/) — optional but recommended; without it,
  run the scripts with any Python 3.11+ interpreter and `pip install -e .`
  the dev group yourself (`ruff`, `pytest`).
- `git` on `PATH` — required for anything beyond `staleness`/`github_meta`
  against a repo that isn't a git working tree.
- [`gh`](https://cli.github.com/): optional. Only used as the last fallback
  source for a GitHub token when `github_meta` or `language_truth` runs online
  and no other source has one.

## Install

Clone the repository anywhere and expose that folder to each agent through
its skills directory (for example `~/.claude/skills/repo-audit`,
`~/.agents/skills/repo-audit` or `~/.gemini/config/skills/repo-audit`, as a
symlink or a copy). A skill manager that links one folder per skill works the
same way.

```bash
git clone <this-repo-url> <skill-dir>
cd <skill-dir>
uv sync
```

## Environment variables

| Variable | Used by | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | `github_meta`, `language_truth` (online mode) | Auth for `api.github.com`. Read from the process environment only. |
| `AGENT_WORKBENCH_ROOT` | `github_meta`, `language_truth` (online mode) | Optional. When set and `GITHUB_TOKEN` is not in the environment, the token is looked up with `agent_workbench.vault.get_secret("GITHUB_TOKEN")`. Unset elsewhere; the tool stays standalone. |
| `REPO_AUDIT_NEVER_EXIT_NONZERO` | `audit.py`, `scan.py` | Set to `1` to force exit code `0` regardless of gate. Manual debugging only — never set this in CI. |
| `SKILLS_PYTHON` | not read by this tool directly | Present in `.env.example` for parity with other skills in a shared portfolio; harmless to leave unset here. |

Token lookup order: `GITHUB_TOKEN` in the environment, then the optional
vault above, then `gh auth token`. No `.env` file is read, and in particular
never the `.env` of the audited repository: a target could otherwise plant a
token, and its secrets are not this tool's to use.

## Configuration precedence

`auditlib.config.load_config` merges, in this order (later wins; list
values are replaced except `denylist.terms|regexes|soft_regexes|email_domains`
and `secrets.extra_patterns|ignore_paths`, which are unioned):

1. `config/denylist.default.toml` (shipped with this tool — structural only)
2. `<this tool's own repo-audit.toml>`, but only when auditing this tool
   itself
3. `<this tool's own repo-audit.local.toml>`, when auditing any *other* repo
   (operator overlay: nicknames and employer terms stay on this machine)
4. `<audited-repo>/repo-audit.toml` (committed, generic)
5. `<audited-repo>/repo-audit.local.toml` (gitignored, machine-local)
6. `--config <path>` (an explicit override file)
7. Explicit CLI flags (e.g. `--offline`, `--run-tests`, `--trust-target`)

`[tests].command` from the audited repository is only executed with
`--trust-target`; without it `tests.execution` reports INFO and runs nothing.

## The local-secrets pattern

Two files never get committed, mirroring each other:

- `.env`: real tokens for your shell (export them; the tool itself reads the
  environment, not the file). See `.env.example`.
- `repo-audit.local.toml`: real denylist terms (an old employer's name, an
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

The same rule applies to hygiene tests *inside* other repos. Do not commit a
nickname, a drive-letter home-directory literal, a product key, or an employer token
"because the test needs it". Load those values from `.env` / a gitignored
local TOML. Splitting the string (`"abc" + "def"`), joining a char array, or
base64-encoding it is still a leak; `content.denylist_reconstructed` and
`hardcoded_paths.literal` will flag those encodings.

## JSON contract

Every report follows schema v2 — see `docs/json_contract.md` for the full
shape of both a single-repo report and a multi-repo dashboard, and
`docs/rules.md` for what each check id means.

## Standalone invocation

The scripts have no dependency on being installed as an agent skill; they
are plain Python entry points:

```bash
uv run python scripts/audit.py /path/to/repo --profile portfolio --json-out report.json
uv run python scripts/scan.py --repos repos.txt --out dashboard.json
uv run python scripts/dashboard.py --json dashboard.json --format md
```
