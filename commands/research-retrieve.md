---
name: research-retrieve
description: Spawn research-retriever. Parent gets a summary card only. Do not pack inline.
---

Follow the **research-retrieve** skill completely.

1. Load `${CLAUDE_PLUGIN_ROOT}/skills/research-retrieve/SKILL.md`.
2. Spawn the `research-retriever` agent. Do not run `rkc_pack.py` in the parent for Q&A.
3. Accept the retrieval card only. Do not ask the sub-agent for pack JSON or Evidence bodies.
