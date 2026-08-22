---
name: research-validate
description: Fail-closed schema and rel check for knowledge/research/**.
---

Follow the **research-validate** skill completely.

1. Load `${CLAUDE_PLUGIN_ROOT}/skills/research-validate/SKILL.md`.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_validate.py --root <knowledge>`.
3. Unknown type or rel is an error. Stop. Do not repair by inventing a rel.
