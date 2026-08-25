---
name: research-spine
description: Repair Area → Subject → Task links on an existing RKC knowledge tree. Create missing Subjects and ResearchAreas. Idempotent.
---

Follow the **research-spine** skill completely.

1. Load `${CLAUDE_PLUGIN_ROOT}/skills/research-spine/SKILL.md`.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_spine.py --knowledge <knowledge> --list-subjects`.
3. Run `--link-tasks`, then `--area-map <file>` if areas are known.
4. Validate with `--spine`. Ready PR. No force-push.
