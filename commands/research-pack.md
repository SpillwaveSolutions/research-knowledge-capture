---
name: research-pack
description: Pack a Subject, Finding, Task, or ResearchQuestion with structural hops plus spine expansion.
---

Follow the **research-pack** skill completely.

1. Load `${CLAUDE_PLUGIN_ROOT}/skills/research-pack/SKILL.md`.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_pack.py <id> --root <knowledge>`.
3. For a chat card use `--summary` (and `--tiny` to probe). For Q&A, spawn `research-retriever` instead of packing in the parent.
4. Report node ids and whether the pack was truncated.
