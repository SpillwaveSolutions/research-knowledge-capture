---
name: research-search
description: Thin L0 search over knowledge/research/** (AND terms, type filter, json).
---

Follow the **research-search** skill completely.

1. Load `${CLAUDE_PLUGIN_ROOT}/skills/research-search/SKILL.md`.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_search.py "<query>" --root <knowledge> --limit 5 --json`.
3. Prefer Finding / ResearchQuestion / Subject hits as seeds. Then `/research-retrieve`.
