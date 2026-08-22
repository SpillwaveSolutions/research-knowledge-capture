---
name: research-ingest
description: Archive a dump from _inbox/research-dumps/ into RKC source-assets and write SourceDocument + ResearchTask shells. Pass --extract to run the Phase 2 extractor.
---

Follow the **research-ingest** skill completely.

1. Load `${CLAUDE_PLUGIN_ROOT}/skills/research-ingest/SKILL.md`.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_ingest.py <inbox> --knowledge <knowledge> --vendor <vendor> --subject <slug>`.
3. After the shell lands, run `/research-extract` (or pass `--extract`) unless the user asked for archive-only.
4. Ready PR. No force-push.
