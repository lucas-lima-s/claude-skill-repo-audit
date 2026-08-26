---
name: repo-audit
description: "Audits any repository against publish-ready standards before it goes public: secret and API-key scan, author-identity and internal-term scan across the whole git history, test execution, language-vs-declared-stack, README image rot, staleness and GitHub description/topics quality. Also runs over a list of repos and renders a portfolio dashboard. Use when the user says 'audit this repo', 'is this ready to publish', 'check for secrets before I push', 'audit my whole portfolio', '/repo-audit', or in pt-BR 'audita esse repo', 'esse repo ta pronto pra publicar?', 'varre meus repos antes de publicar'."
argument-hint: "[repo-path|--repos <file>] [--profile portfolio|public|local]"
allowed-tools: "Read, Bash(*scripts/audit.py*), Bash(*scripts/scan.py*), Bash(*scripts/dashboard.py*)"
---

# repo-audit

A publish gate for repositories. It runs in two layers:

- **Layer 1 (deterministic)** — Python checks with no model in the loop: secret
  patterns and entropy, committed `.env` files, git-history author identity,
  denylisted terms in commits/refs/content, test execution, declared-vs-real
  language, README image/link rot, staleness, GitHub description/topics
  quality, deferred-work markers. Every finding carries an explicit
  `remediation` string. Layer 1 is the only layer that can produce a `FAIL`
  and therefore the only layer that can flip the gate to `BLOCK`.
- **Layer 2 (LLM-assisted)** — a small set of markdown prompts (README
  quality, setup completeness, changelog significance, language coherence,
  and a portfolio-only narrative check) that you, the agent, run yourself
  against the files `targets_for_layer2` names. Layer 2 can only add `INFO`
  or `WARN` findings — the engine hard-caps anything you emit as `FAIL` down
  to `WARN`.

## Single-repo flow

1. Run `scripts/audit.py <repo-path> [--profile portfolio|public|local] [--offline] [--json-out PATH]`.
2. Read the path printed as `JSON_PATH=<path>` — the **last line of stdout** —
   and load that JSON file (schema v2, see `docs/json_contract.md`).
3. For each entry in `targets_for_layer2`, open its `prompt_file` and apply it
   to the listed `files`. Produce zero or more findings in the exact shape the
   prompt's `## Output` section documents.
4. Append everything you produced to `findings_layer2` — or hand it to
   `auditlib.layer2.merge_layer2(report, your_findings)` if you're scripting
   this — and re-render with `dashboard.py --json <path> --format md` or
   `audit.py --render`.
5. Report the `gate` (`PASS`/`BLOCK`) and the findings, worst severity first.

## Multi-repo flow

1. Build a repo list: a text file (one path per line) for `--repos FILE`, a
   shell glob for `--repos-glob GLOB`, or repeated `--repo PATH` flags.
2. Run `scripts/scan.py (--repos FILE | --repos-glob GLOB | --repo PATH ...) --profile portfolio --out dashboard.json`.
   Repos are audited in parallel; a path that does not exist becomes a
   synthetic `BLOCK` entry instead of crashing the scan.
3. Render with `scripts/dashboard.py --json dashboard.json --format md`, or
   feed each repo's own `targets_for_layer2` through the layer-2 prompts the
   same way as the single-repo flow, one prompt pass per repo.

## Profiles

| Profile | Intent | Notable difference |
|---|---|---|
| `portfolio` | About to publish under a personal account | `deferred_work.marker` is `WARN`; `tests.execution` defaults to on |
| `public` | Already public, periodic re-check | Same checks as `portfolio`; `deferred_work.marker` downgraded to `INFO` |
| `local` | Fast local iteration | All `WARN` downgraded to `INFO`; GitHub metadata checks downgraded to `INFO` |

## Inviolable rules

- **Never auto-fix.** Every finding carries a `remediation` string instead of
  a patch. You apply changes yourself, deliberately.
- **Never emit `FAIL` from layer 2.** The engine will demote it to `WARN`
  regardless — treat layer 2 as advisory, not gating.
- **Never write inside the audited repo.** All output goes to `--json-out` or
  a temp file; the tool never mutates the target.
- **Never print a matched secret in full.** Every secret finding redacts to
  `<first 4 chars>...<last 2>`.
- **Never commit a real denylist term to this repo.** The shipped
  `config/denylist.default.toml` is structural only; real terms belong in a
  gitignored `repo-audit.local.toml` on the machine running the audit.
