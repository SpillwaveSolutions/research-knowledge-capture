---
name: research-ingest
description: Archive AI deep-research dumps and articles into RKC source-assets. Hash, copy, write SourceDocument + ResearchTask shells. Idempotent on bytes plus extractor version.
---

# research-ingest

Actor: `grok-bot/research-knowledge-capture`. Isolated session. Ready PR. No force-push. No write to main.

## What this skill does

1. Read files from `_inbox/research-dumps/` (not a type).
2. SHA-256 the bytes. Archive to `knowledge/research/source-assets/<sha256>/original.*`.
3. Write `SourceDocument` + `ResearchTask` shells with `ingested_from`.
4. Same bytes + extractor version → return existing ids (ADR 004).
5. Never auto-supersede `reviewed` | `accepted` | `verified: true`.

## Command

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_ingest.py _inbox/research-dumps \
  --knowledge knowledge --vendor grok --subject <slug>
```

Vendors: `grok` | `gemini` | `claude` | `deepseek` | `chatgpt` | `article`.

## Extraction (agent, not this script)

The script does **not** mint Claims. After the shell lands:

- Segment large dumps with global locators.
- `claim_key = sha256(normalize(text)|claim_kind|subject_id)`. Same key → attach Evidence to the existing Claim.
- Finding → asserts → Claim → evidenced_by → Evidence → source-asset + locator.
- Verbatim quotes must match the archived span.
- Required PR summary: new/merged claims, contradictions, skipped accepted nodes.

Public samples are Northstar / Lumenfield fiction only.
