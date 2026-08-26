# Layer-2 prompt index

Every layer-2 prompt is a markdown file starting with an
`<!-- inputs: a.md, b.md, dir --> ` header, then `## What to read`,
`## What to look for`, `## What to ignore`, `## Output`. `runner.py`
resolves a prompt id to a file by checking the per-tool prompt directory
before the generic one, so a tool built on top of `auditlib` can override a
generic prompt by shipping its own file with the same id.

Resolution order for a prompt id: `scripts/prompts/<id>.md` (repo-audit-only,
checked first), then `scripts/auditlib/prompts/<id>.md` (generic, shared with
anything that vendors `auditlib`).

| Prompt id | File | Profile(s) | Inputs |
|---|---|---|---|
| `readme_quality` | `scripts/auditlib/prompts/readme_quality.md` | all | `README.md` |
| `setup_completeness` | `scripts/auditlib/prompts/setup_completeness.md` | all | `SETUP.md`, `README.md`, `.env.example` |
| `changelog_significance` | `scripts/auditlib/prompts/changelog_significance.md` | all | `CHANGELOG.md` |
| `language_coherence` | `scripts/auditlib/prompts/language_coherence.md` | all | `README.md`, `docs` |
| `portfolio_narrative` | `scripts/prompts/portfolio_narrative.md` | `portfolio` only | `README.md`, `SKILL.md` |

Every prompt restates the same hard rule, because it matters more than any
single prompt's specifics: **never emit `FAIL`; cap at `WARN`; do not invent
findings to pad the report.** An empty findings list is a valid, good
outcome — a prompt that always finds something is a prompt that is padding.
