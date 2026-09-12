---
name: research-search
description: Thin git-native RKC search (rg → scan). AND terms, type filter, limit, json. No Chroma or Kuzu.
---

# research-search

Locate seed candidates in `knowledge/research/**`. Git stays the source of truth. This is the L0 rung under `research-retriever`, not a Layer 1 projector.

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_search.py "false civic alerts" --root knowledge
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_search.py loop-policy --type Finding,ResearchQuestion,Subject --limit 5 --json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_search.py detector --engine scan
```

## Rules

- AND semantics across whitespace-separated terms.
- `--type` is a comma-separated list of RKC nouns. Use `ResearchQuestion`, never PKC `Question`.
- Default `--limit` is 5 (retriever seed list).
- Scores title > id > description > tags > body. Finding / ResearchQuestion / Subject win ties (seed preference).
- Ladder: `rg` prefilter → linear frontmatter/body scan. `--engine scan` forces the scan. Missing `rg` is not an error.
- No Chroma, BM25, Kuzu, or SQLite. Layer 1 (`research-graph`) may feed seeds later; do not require it here.

After hits, spawn `research-retriever` (or `/research-retrieve`) to pack. Do not dump matching file bodies into the parent.
