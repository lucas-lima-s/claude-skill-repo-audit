# Check reference

One section per check id. "Severity per profile" lists the severity `portfolio`
emits; `public` and `local` only differ where noted (see `profiles/*.toml`).

## `artifacts.*`

Data-driven from `profile.artifacts` (one id per artifact, e.g.
`artifacts.readme_md`, `artifacts.license`). `OK` when the path exists,
otherwise the profile's configured `missing` severity (`FAIL` for
README.md/LICENSE, `WARN` for SETUP.md/CONTRIBUTING.md/CHANGELOG.md/
pyproject.toml/CI workflow, `INFO` for .gitattributes/visual assets).

**Why it matters:** a public repo without a license or README is not
publishable regardless of what the code does. **Fix:** add the missing file.

## `gitattributes.eol`

WARN when `.gitattributes` exists but lacks `* text=auto eol=lf`.
**Why:** without it, a Windows checkout can flip line endings across the
whole tree and turn every future diff into a whitespace diff. **Fix:** add
the line.

## `gitattributes.linguist`

INFO when a committed generated asset (`docs/*.svg`, `*.min.js`, `dist/**`)
has no `linguist-generated`/`linguist-vendored` attribute. **Why:** GitHub's
language bar and diff view both treat generated files as hand-written
otherwise. **Fix:** add e.g. `docs/*.svg linguist-generated=true`.

## `gitignore.coverage`

WARN per missing family the repo warrants: Python bytecode cache, a Python
virtualenv, `.env`, `node_modules/` (if `package.json` exists), `*.log`,
`.history/`. **Fix:** add the missing pattern.

## `pyproject.format`

FAIL on invalid TOML or when neither `[tool.ruff]` nor `[tool.black]` exists.
WARN when a linter exists with no formatter signal. INFO when
`requires-python` is absent. WARN when `uv.lock` is committed but
`[tool.uv]`/`[build-system]` are both absent. **Fix:** add the missing
section; `[tool.uv]\npackage = false` when there is no `[build-system]`.

## `dev_deps.declared`

INFO when no dev-dependency group exists at all; WARN when `tests/` exists
but `pytest` is not declared; WARN per unsupported
`requirements-dev.txt` line. **Fix:** declare `[dependency-groups].dev`.

## `ci_workflow.matrix`

OK when at least one workflow names an OS runner and a language-version
token; WARN listing what is missing. **Fix:** add an os/version matrix.

## `ci_workflow.parser_limit`

WARN when a workflow uses `include:` or a YAML anchor — this scanner reads
workflows textually and does not expand either. **Fix:** none required; it is
a scope disclosure, not a defect.

## `ci_workflow.shallow_clone`

WARN when a workflow checks out with `actions/checkout` and no
`fetch-depth: 0`, while the repo also runs a history-scanning check
(`git_history`/`secrets`). A shallow clone hides commits from those checks
and can produce a false `history.single_commit`. **Fix:** add
`with: { fetch-depth: 0 }`.

## `changelog.format`

WARN when `CHANGELOG.md` lacks a `# Changelog` header in its first 10 lines
or a `## [Unreleased]` section. **Fix:** follow Keep a Changelog.

## `python_style.future`

WARN (source) / INFO (`tests/`) when a tracked `.py` file is missing
`from __future__ import annotations`. **Fix:** add it as the first statement.

## `python_style.typing_aliases`

WARN when a file imports a deprecated `typing` alias
(`List`/`Dict`/`Tuple`/`Set`/`FrozenSet`/`Type`/`Optional`/`Union`).
**Fix:** use builtin generics and `X | None` / `X | Y`.

## `python_style.parse`

WARN naming the file and line when a tracked `.py` file has a `SyntaxError`.

## `hardcoded_paths.literal`

FAIL per line containing a machine-specific path: a Windows drive letter
followed by a per-user profile directory, `/home/<name>/...`,
`/Users/<name>/...`, a drive letter followed by
`(projects|dev|work|repos)/...`, or a local CPython install path. The
scanner collapses regex encodings of drive-letter home paths and
reconstructed fragments (concatenated strings, PowerShell char arrays) before
matching, so a hygiene test that "hides" a home path still fails. Suppressed
by `$HOME`/`%TEMP%`/CI-style placeholders or the inline marker
`repo-audit: allow-path`. **Why:** a hardcoded path is the single most common
tell that a repo was published straight from someone's laptop. **Fix:**
replace with an env var, a relative path, or a CI-provided temp dir. If the
line exists only so a privacy test can search for it, load it from gitignored
local config instead of committing it.

## `hardcoded_paths.history`

FAIL when `git log -G` finds a machine-path pattern (`Users`, local `PythonNN`,
`/home/<name>`) in history, even if the working tree is clean. **Fix:** rewrite
history, or confirm the only remaining hit is a structural detector that does
not name a real user.

## `secrets.pattern`

FAIL when a tracked file matches a known credential shape (AWS, GitHub,
Slack, Google, Anthropic, OpenAI, Stripe, a private-key header, a JWT, or a
generic `key = "..."` assignment). The matched value is always redacted to
its first 4 and last 2 characters. **Fix:** rotate the credential and remove
it from the working tree; use the inline marker `repo-audit: allow-secret`
only for a genuine false positive.

## `secrets.entropy`

WARN when a quoted string or assignment value looks random enough to be a
secret (Shannon entropy over a threshold, or a long hex string with lower
entropy). Placeholders (`changeme`, `<your...>`, `example`, ...), paths,
URLs and repeated characters are suppressed. **Fix:** confirm it is not a
real credential; if it is, treat it like `secrets.pattern`.

## `secrets.committed_env`

FAIL when a tracked `.env`/`.env.*` file exists (excluding `.env.example`
and friends), or when `.env`/`.env.*` was ever added in git history even if
later removed. **Fix:** `git rm --cached`, rotate every secret it may have
held, and if it was ever committed, rewrite history with
`git filter-repo`.

## `secrets.env_not_ignored`

FAIL when `.env` exists on disk but `.gitignore` does not cover it yet — a
near-miss that will become `secrets.committed_env` on the next `git add -A`.
**Fix:** add `.env` to `.gitignore` now.

## `history.author_identity`

FAIL per non-portfolio identity found in `git log --all`. An identity passes
when its email is explicitly allowed, ends in `users.noreply.github.com`, or
matches a known public email provider; anything else — most notably an old
employer's domain — fails. This is intentionally **structural**: the tool
never needs to know the name of any employer to catch its domain. **Fix:**
recreate the history under the portfolio identity, or rewrite it with
`git filter-repo --mailmap`.

## `history.commit_message`

FAIL when a configured denylist term or regex matches a commit subject or
body. **Fix:** the message already exists in history; rewrite or recreate it.

## `history.ref_name`

WARN when a denylist term or regex matches a branch/tag name.
**Fix:** rename or delete the ref before publishing.

## `history.denylist_term`

INFO when a *soft* regex (e.g. a generic `TEAM-1234`-shaped ticket pattern)
matches a commit message — worth a glance, not a hard block.

## `history.single_commit`

INFO when the whole history is exactly one commit — reads as a code dump to
a reviewer. **Fix:** not required, but a handful of real commits reads
better.

## `history.not_a_repo`

WARN when the target has no `.git` at all; every other history check is
skipped.

## `content.denylist_term`

FAIL per tracked-file line matching a denylist term or regex, honoring
`denylist.allow.paths` globs and the inline marker `repo-audit: allow-term`.
The matched term is redacted to its first 3 characters. **Fix:** remove or
rewrite the content. Private terms belong in `repo-audit.local.toml` or `.env`,
not in a committed hygiene list.

## `content.denylist_reconstructed`

FAIL when a denylist term or regex matches a string that was not contiguous in
the file: `"foo" + "bar"`, `_pattern("foo", "bar")`, a PowerShell `@('f','o')`
char array, or a base64 literal that decodes to the term. **Why:** splitting or
encoding a nickname / employer name / product key is still publishing it.
**Fix:** delete the fragments from the tracked file and load the real terms
from gitignored local config.

## `tests.execution`

Runs the resolved test command (`config.tests.command`, then `uv run
--frozen pytest -q` if `uv.lock` exists, then the current interpreter's
`pytest` if it's a declared dev dependency, then `npm test`). OK on exit 0,
FAIL on a non-zero exit or a timeout, WARN when no command resolves, INFO
when disabled via `--no-run-tests` or when `--trust-target` was not passed.
Every one of those commands executes code from the audited repository, so
nothing runs without that explicit trust flag. **Fix:** fix the failing tests, or
declare a `[tests].command` if the auto-detected one is wrong.

## `language.declared_vs_real`

Compares the declared stack (from `pyproject.toml`/`package.json`/
`Cargo.toml`/`go.mod`) against a byte histogram of tracked files, excluding
anything carrying a `linguist-vendored`/`linguist-generated`/
`linguist-documentation` attribute. FAIL when the mismatch holds ≥50% of
counted bytes, WARN below that. **Fix:** add the exact `.gitattributes` line
the finding's `remediation` names, e.g. `*.bat linguist-vendored`.

## `language.linguist_hint`

INFO reporting the computed primary language when there is no mismatch to
report — mostly useful evidence for a human skimming the report.

## `readme.hotlinked_image`

WARN when `README.md` embeds an image from a host outside the badge
allowlist (`img.shields.io`, `shields.io`, `github.com`,
`raw.githubusercontent.com`, `user-images.githubusercontent.com`,
`codecov.io`). **Fix:** commit the asset under `docs/` and reference it
relatively.

## `readme.broken_relative_image`

FAIL when a relative image path in `README.md` does not resolve on disk.
**Fix:** fix the path or add the missing file.

## `readme.broken_relative_link`

WARN — same idea, for a relative markdown link instead of an image.

## `visual.asset_present`

Active when `config.visual.required` is set, or the repo looks visual
(`index.html`, a `.unity`/`.godot`/`.love` marker, or a `game`/`ui`/`frontend`
top-level directory). Requires at least one matching asset under
`docs/`/`assets/`/`screenshots/` that is also referenced from `README.md`.
FAIL when required and missing, INFO when merely auto-detected. A synthetic,
clearly-labelled mockup is acceptable — a live capture is not required.

## `staleness.last_commit`

Age in days of the last commit. WARN at `staleness.warn_days` (default 180),
FAIL at `staleness.fail_days` (default 0, meaning "never fail on this
alone"). **Fix:** make a real commit, or archive the repo if it is finished.

## `github.description`

WARN when the repo's GitHub description is missing, too short, too long, or
just the repo name. Read from the GitHub API when online, or from
`.github/repo-meta.toml` when `--offline`.

## `github.topics`

WARN when the topic count is outside `[topics_min, topics_max]` (default
3–5), a topic is not lowercase-kebab, or a topic equals the repo name.

## `github.metadata_unavailable`

INFO when running `--offline` with no `.github/repo-meta.toml` present, or
when online access fails — the description/topics checks are skipped rather
than guessed at.

## `deferred_work.marker`

Flags `ROADMAP.md`/`TODO.md`/`FUTURE.md`, a README/doc section titled
"Roadmap"/"Future work"/"Planned"/"Coming soon", and `TODO:`/`FIXME:`/`XXX:`
in tracked source. `WARN` under `portfolio`, `INFO` under `public`/`local`.
**Why:** a portfolio repo should ship finished work. **Fix:** execute it or
delete the marker.

## `runner.missing_repo` (synthetic)

Emitted only by `scan.py` when a repo path in the input list does not exist
on disk — the scan continues for the other repos instead of crashing.
