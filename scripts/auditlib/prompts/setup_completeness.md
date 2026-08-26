<!-- inputs: SETUP.md, README.md, .env.example -->

# Layer 2 prompt: setup_completeness

## What to read

`SETUP.md` if it exists, otherwise the setup/installation section of `README.md`; `.env.example`; and every environment-variable reference found anywhere else in the repository (source, scripts, CI workflows, config files).

## What to look for

- Every environment variable referenced anywhere in the repo (`os.environ`, `process.env`, `${{ env.X }}`, shell `$VAR` in scripts) that is not documented in SETUP.md/README and not listed in `.env.example`.
- Every key present in `.env.example` that is never explained.
- External tool prerequisites mentioned in code or CI (a specific CLI, a minimum language version, an optional dependency) that setup docs do not mention.
- Instructions that reference a step the repo cannot actually perform (a script that no longer exists, a path that was renamed).

## What to ignore

- Variables that are clearly internal test fixtures (e.g. only used inside `tests/`).
- Standard variables every reader already knows (`PATH`, `HOME`) unless the repo depends on a non-default value.

## Output

Emit zero or more findings as a JSON list, each shaped as:

```json
{
  "source": "layer2",
  "check": "setup_completeness.<short_slug>",
  "severity": "INFO|WARN",
  "message": "one sentence describing the gap",
  "file": "SETUP.md",
  "line": null,
  "remediation": "one concrete sentence on how to fix it"
}
```

Never emit `FAIL` — the engine caps layer 2 severity at `WARN` regardless. Do not invent findings to pad the report; an empty list is a valid, good outcome.
