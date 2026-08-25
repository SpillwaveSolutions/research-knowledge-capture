# Research Knowledge Capture (RKC)

Layer 0 ContentPack for a research second brain. OKF Markdown + YAML is the source of truth. Agent Brain is a disposable index — see [`research-graph`](https://github.com/SpillwaveSolutions/research-graph).

**Version:** 0.2.5 — Subject title comes from the slug, not the first source filename. See the [PRD](docs/prd/research-knowledge-capture-PRD.md).

## What it owns

Eight nouns: `ResearchArea`, `Subject`, `ResearchTask`, `SourceDocument`, `ResearchQuestion`, `Claim`, `Evidence`, `Finding`.

Registered rels: `has_subject`, `related_to`, `has_task`, `ingested_from`, `asks`, `answers`, `produced`, `asserts`, `evidenced_by`, `contradicts`, `supersedes`, `same_as`.

Article bridge (`Article → draws_from → Finding`) is owned by **content-media**, not this pack.

## Install

```
claude plugin marketplace add SpillwaveSolutions/research-knowledge-capture
claude plugin install research-knowledge-capture@rkc-plugin-marketplace
```

Hosts: Claude Code, Grok Build, Codex, Cursor, Agent Plugins 1.0. See [docs/HOSTS.md](docs/HOSTS.md).

## Commands

| Host | Ingest | Extract | Pack | Validate | Spine |
| --- | --- | --- | --- | --- | --- |
| Claude / Grok / Cursor | `/research-ingest` | `/research-extract` | `/research-pack` | `/research-validate` | `/research-spine` |
| Codex | `$research-ingest` | `$research-extract` | `$research-pack` | `$research-validate` | `$research-spine` |

```
python3 scripts/rkc_validate.py --root sample-knowledge
python3 scripts/rkc_pack.py subject.loop-policy.01J8X000000000000000000001 --root sample-knowledge
python3 tests/test_rkc.py
python3 tests/test_extract.py
python3 tests/test_plugin.py
python3 tests/test_bulk_fixes.py
python3 tests/test_spine.py
```

Public samples are **Northstar / Lumenfield fiction**. Live dumps stay in private trees.

## Bulk ingest

- Lookup is `research/catalogs/ingest-index.json` (not a full-tree scan). Rebuild with `--rebuild-index`.
- Archive-only ingest still creates the Subject and writes `has_task`. Pass `--area <slug>` for a ResearchArea + `has_subject`.
- `index.md` / `README.md` titles are `parent/filename`. `--extractor-version` defaults to the current extractor, so omitting `--extract` on a re-run is idempotent.
- Repair a 0.2.0 tree with `python3 scripts/rkc_spine.py --knowledge knowledge --link-tasks` then `--area-map areas.json`.
- Heuristic extract skips files over 200 KB. Use `--force-large` only when you mean it.
- One process per Subject (or per knowledge tree). Do not `pkill -f` a multiprocessing ingest; kill by PID.
- `vendor` is free text. Convention: `grok` `gemini` `claude` `deepseek` `chatgpt` `article` `perplexity` `unknown`.
- `--source-kind` defaults to `deep_research`.

## Retrieval ladder

`rg` → `/research-pack` → BM25/Chroma → Kuzu last (Layer 1).

## Actor

`grok-bot/research-knowledge-capture`. Isolated session. Ready PR. No force-push. No write to main.
