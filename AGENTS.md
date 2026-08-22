# AGENTS.md — research-knowledge-capture

Layer 0 ContentPack. OKF Markdown + YAML is the source of truth.

## Hosts

| Host | Manifest |
| --- | --- |
| Agent Plugins 1.0 | `plugin.json` + `skills/` |
| Claude Code | `.claude-plugin/` |
| Grok Build | Claude layout + `.grok-plugin/` |
| Codex | `.codex-plugin/` (`$research-ingest`) |
| Cursor | `.cursor-plugin/` + `.cursor/rules/` |

## Commands

- `/research-ingest` · `$research-ingest`
- `/research-extract` · `$research-extract`
- `/research-pack` · `$research-pack`
- `/research-validate` · `$research-validate`

Deterministic:

```
python3 scripts/rkc_ingest.py _inbox/research-dumps --knowledge knowledge --vendor grok --subject loop-policy
python3 scripts/rkc_extract.py --knowledge knowledge --asset research/source-assets/<sha>/original.md --subject-id <id>
python3 scripts/rkc_pack.py subject.loop-policy.01J8X000000000000000000001 --root sample-knowledge
python3 scripts/rkc_validate.py --root sample-knowledge
python3 tests/test_rkc.py
python3 tests/test_extract.py
python3 tests/test_plugin.py
```

## Operating principles

1. Eight nouns. Twelve registered rels. Unknown type/rel is an error.
2. IDs `<type-slug>.<subject-slug>.<ulid>`, immutable.
3. `claim_key` merge. Spine expansion on pack. Citation integrity on quotes.
4. Extractor is fail-closed: overlay quotes must match the source-asset; accepted/verified nodes are never auto-superseded.
5. Do not write Article or `draws_from`. content-media owns that bridge.
6. Actor `grok-bot/research-knowledge-capture`. Ready PR. No force-push.
7. Public samples are Northstar / Lumenfield fiction.

Layer 1 (`research-graph`) owns the Agent Brain projector. This plugin owns none of Chroma, BM25, or Kuzu.
