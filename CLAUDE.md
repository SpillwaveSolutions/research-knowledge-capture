# CLAUDE.md — research-knowledge-capture

Same plugin as AGENTS.md. Claude Code loads `.claude-plugin/plugin.json`.

Do not invent RKC types. Do not write `draws_from`. Run `scripts/rkc_validate.py` after edits under `knowledge/research/**`. After ingest, run `scripts/rkc_extract.py` (heuristic or `--overlay`). Overlay quotes must match the archived asset. Never auto-supersede accepted or verified nodes.
