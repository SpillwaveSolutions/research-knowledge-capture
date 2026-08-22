---
name: research-ingest
description: Archive AI deep-research dumps and articles into RKC source-assets. Hash, copy, write SourceDocument + ResearchTask shells. Optionally run the Phase 2 extractor. Idempotent on bytes plus prompt hash plus extractor version.
---

# research-ingest

Actor: `grok-bot/research-knowledge-capture`. Isolated session. Ready PR. No force-push. No write to main.

## What this skill does

1. Read files from `_inbox/research-dumps/` (not a type).
2. SHA-256 the bytes. Archive to `knowledge/research/source-assets/<sha256>/original.*`.
3. Write `SourceDocument` + `ResearchTask` shells with `ingested_from`.
4. Same bytes + prompt hash + extractor version → return existing ids (ADR 004).
5. Never auto-supersede `reviewed` | `accepted` | `verified: true`.

## Command

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_ingest.py _inbox/research-dumps \
  --knowledge knowledge --vendor grok --subject <slug>
```

Then extract:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_ingest.py _inbox/research-dumps \
  --knowledge knowledge --vendor grok --subject <slug> --extract --subject-id <id>
```

or `/research-extract` against the archived asset.

Vendors: `grok` | `gemini` | `claude` | `deepseek` | `chatgpt` | `article`.

`--extract` bumps extractor version to 2 unless set. Prompt hash: `--prompt-hash` or `--prompt-file`.

Public samples are Northstar / Lumenfield fiction only.
