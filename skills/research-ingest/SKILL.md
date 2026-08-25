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
  --knowledge knowledge --vendor grok --subject <slug> --area <area-slug>
```

Then extract:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_ingest.py _inbox/research-dumps \
  --knowledge knowledge --vendor grok --subject <slug> --area <area-slug> --extract --subject-id <id>
```

or `/research-extract` against the archived asset.

`vendor` is free text. Conventional values: `grok` | `gemini` | `claude` | `deepseek` | `chatgpt` | `article` | `perplexity` | `unknown`.

`--source-kind` defaults to `deep_research`. Use `reference_doc`, `published_medium`, `published_substack` when that is what you have.

`--extract` bumps extractor version to 2 unless set. Prompt hash: `--prompt-hash` or `--prompt-file`.

Files over 200 KB skip heuristic extract unless `--force-large`. Progress goes to stderr. Failed files append to `research/catalogs/ingest-errors.jsonl`; the run continues.

Idempotency lookup is `research/catalogs/ingest-index.json`. `--rebuild-index` rebuilds it from sources + tasks.

Do not parallelize writers inside one knowledge tree. Shard by Subject (one tree or one process per slug). If you stop a run, kill workers by PID — `pkill -f` misses multiprocessing children.

Public samples are Northstar / Lumenfield fiction only.
