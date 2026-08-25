---
name: research-spine
description: Create missing Subject and ResearchArea nodes and write has_task / has_subject on an existing RKC tree. Idempotent repair for 0.2.0 archive-only ingest.
---

# research-spine

Actor: `grok-bot/research-knowledge-capture`. Isolated session. Ready PR. No force-push. No write to main.

Use this when the graph has ResearchTasks (and maybe Subjects) but pack from a Subject walks nowhere.

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_spine.py --knowledge knowledge --list-subjects
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_spine.py --knowledge knowledge --link-tasks
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_spine.py --knowledge knowledge --area-map areas.json
```

`areas.json`:

```
{
  "areas": [
    {
      "slug": "claude-platform",
      "title": "Claude platform",
      "prefixes": ["ref-claude", "course-claude"],
      "subjects": ["loop-policy"]
    }
  ]
}
```

Exact `subjects` win over `prefixes`. `--default-area <slug>` catches leftovers. `--dry-run` prints the plan.

Then `python3 scripts/rkc_validate.py --root knowledge --spine`.
