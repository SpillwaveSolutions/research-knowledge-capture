---
name: research-extract
description: Segment an archived dump, extract claims with claim_key merge, write a PR summary. Fail-closed.
---

Follow the **research-extract** skill completely.

1. Load `${CLAUDE_PLUGIN_ROOT}/skills/research-extract/SKILL.md`.
2. Confirm `/research-ingest` already archived the dump (source-asset + SourceDocument).
3. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_extract.py` with `--asset` or `--source-id`. Use `--overlay` only after quotes are copied from the asset.
4. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_validate.py`.
5. Include the PR summary in the ready PR. No force-push. No write to main.
