---
name: research-extract
description: Segment an archived research dump, extract claims/evidence/findings, merge on claim_key, write a required PR summary. Fail-closed. Never auto-supersede accepted or verified nodes.
---

# research-extract

Actor: `grok-bot/research-knowledge-capture`. Isolated session. Ready PR. No force-push. No write to main.

Run **after** `/research-ingest` has archived the dump. Do not mint types or rels outside the registry.

## Deterministic path (preferred)

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_segment.py knowledge/research/source-assets/<sha>/original.md
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_extract.py \
  --knowledge knowledge \
  --asset research/source-assets/<sha>/original.md \
  --subject-id subject.<slug>.<ulid> \
  --subject <slug> \
  --vendor grok \
  --source-id source.<slug>.<ulid> \
  --task-id task.<slug>.<ulid>
```

`--overlay claims.json` is the agent/LLM path. Quotes are verified against the asset **before any write**. Bad quote → no writes.

## Rules

1. `claim_key = sha256(normalize(text)|claim_kind|subject_id)`. Same key → attach Evidence to the existing Claim.
2. Near-match → `same_as`. `contradicts` only when `claim_kind` matches and `as_of` overlaps.
3. Never auto-supersede `reviewed` | `accepted` | `verified: true`. Overlay `supersedes` targeting a protected node is skipped and listed.
4. New nodes are `status: draft`. Human PR gate.
5. Verbatim quotes must match the archived span (`rkc_validate`).
6. Required PR summary under `knowledge/research/catalogs/pr-summaries/` (not an OKF type): new/merged claims, contradictions, skipped accepted, duplicate evidence.
7. `--dry-run` prints the plan and writes nothing.
8. Public samples are Northstar / Lumenfield fiction only.

See `references/overlay.md`.
