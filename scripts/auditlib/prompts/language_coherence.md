<!-- inputs: README.md, docs -->

# Layer 2 prompt: language_coherence

## What to read

`README.md` and every file under `docs/`.

## What to look for

- Declare the repository's primary documentation language from the README's own prose.
- Flag any document that mixes languages in a way that looks unintentional (a paragraph that drifts from English into another language mid-thought, not a deliberately localized block).
- Flag inconsistent terminology for the same concept across documents (calling the same check both "gate" and "verdict" in different files, for example) when it would confuse a first-time reader.

## What to ignore

- A deliberately localized trigger, description, or example block that documents how the tool matches non-English input — that is a feature, not a finding.
- Code identifiers, file paths, and proper nouns, regardless of language.
- Comments inside code blocks that quote another language's output verbatim.

## Output

Emit zero or more findings as a JSON list, each shaped as:

```json
{
  "source": "layer2",
  "check": "language_coherence.<short_slug>",
  "severity": "INFO|WARN",
  "message": "one sentence describing the gap",
  "file": "README.md",
  "line": null,
  "remediation": "one concrete sentence on how to fix it"
}
```

Never emit `FAIL` — the engine caps layer 2 severity at `WARN` regardless. Do not invent findings to pad the report; an empty list is a valid, good outcome.
