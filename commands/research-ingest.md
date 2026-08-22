---
name: research-ingest
description: Archive a dump from _inbox/research-dumps/ into RKC source-assets and write SourceDocument + ResearchTask shells.
---

Follow the **research-ingest** skill completely.

1. Load `${CLAUDE_PLUGIN_ROOT}/skills/research-ingest/SKILL.md`.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_ingest.py <inbox> --knowledge <knowledge> --vendor <vendor> --subject <slug>`.
3. Do not extract Claims yet unless the user asked. Shells only. Ready PR. No force-push.
