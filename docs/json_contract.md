# JSON contract — schema v2

Both `audit.py` and `scan.py` print `JSON_PATH=<absolute-path>` as the
**last line of stdout**. Everything else — human-readable preamble, the
`--render` markdown — goes to stderr. Exit codes: `0` = PASS, `1` = BLOCK,
`2` = usage/IO error. Setting `REPO_AUDIT_NEVER_EXIT_NONZERO=1` forces exit
`0` regardless of gate (manual debugging only — CI must never set this).

## Single repo (`kind: "repo"`), written by `audit.py`

```json
{
  "schema_version": 2,
  "tool": "repo-audit",
  "tool_version": "0.1.0",
  "kind": "repo",
  "generated_at": "2026-08-25T12:00:00Z",
  "target_path": "/abs/path",
  "target_name": "claude-skill-repo-audit",
  "profile": "portfolio",
  "gate": "PASS",
  "scorecard": {"present": 12, "total": 13, "ok": 24, "info": 3, "warn": 1, "fail": 0},
  "findings_layer1": [
    {
      "check": "secrets.pattern",
      "severity": "FAIL",
      "message": "possible aws_access_key secret: AKIA...QQ",
      "file": ".env",
      "line": 1,
      "remediation": "rotate the credential and remove it from the working tree",
      "source": "layer1",
      "evidence": {"provider": "aws_access_key"}
    }
  ],
  "targets_for_layer2": [
    {
      "prompt_id": "readme_quality",
      "prompt_file": "/abs/.../auditlib/prompts/readme_quality.md",
      "files": ["/abs/README.md"]
    }
  ],
  "findings_layer2": []
}
```

- `scorecard.present`/`total` count the `artifacts.*` checks only.
  `ok`/`info`/`warn`/`fail` count every `findings_layer1` entry by severity.
- `gate` is computed **only** from `findings_layer1` — a `FAIL` in
  `findings_layer2` is impossible; the engine demotes it to `WARN` before it
  ever reaches the report.
- `findings_layer2` starts empty. An agent (or `auditlib.layer2.merge_layer2`)
  appends to it after running the prompts named in `targets_for_layer2`.

## Dashboard (`kind: "dashboard"`), written by `scan.py`

Same envelope, but `target_path` is omitted (there is no single target), and
two extra keys appear:

```json
{
  "schema_version": 2,
  "tool": "repo-audit",
  "tool_version": "0.1.0",
  "kind": "dashboard",
  "generated_at": "2026-08-25T12:00:00Z",
  "profile": "portfolio",
  "gate": "BLOCK",
  "totals": {"repos": 2, "blocked": 1, "fail": 3, "warn": 5, "info": 2, "ok": 30},
  "repos": [
    { "...": "one full single-repo report object per audited repo" }
  ]
}
```

`totals` sums every repo's `scorecard` counts plus how many repos have
`gate: "BLOCK"`. The dashboard's own `gate` is `BLOCK` when any repo is
`BLOCK`.

## Layer-2 finding shape

Every entry an agent appends to `findings_layer2` (or passes to
`merge_layer2`) must have at least `check`, `severity`, and `message`;
`file`, `line`, `remediation`, `evidence` are optional. `severity: "FAIL"` is
accepted but is silently rewritten to `"WARN"` with a note appended to the
message — layer 2 can never gate a repo on its own.

## Validating a report

`auditlib.report.load_and_validate(path)` reads a JSON report and raises
`SystemExit(2)` if `schema_version != 2`. Use it instead of a bare
`json.load` when writing a new tool against this contract, so a future
schema bump fails loudly instead of silently misreading old fields.
