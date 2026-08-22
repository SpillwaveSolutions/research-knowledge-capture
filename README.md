# Research Knowledge Capture (RKC)

Layer 0 ContentPack for a research second brain. OKF Markdown + YAML is the source of truth. Agent Brain is a disposable index — see [`research-graph`](https://github.com/SpillwaveSolutions/research-graph).

**Version:** 0.2.0 — Phase 0–3 plus Phase 2 extractor of the [PRD](docs/prd/research-knowledge-capture-PRD.md).

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

| Host | Ingest | Extract | Pack | Validate |
| --- | --- | --- | --- | --- |
| Claude / Grok / Cursor | `/research-ingest` | `/research-extract` | `/research-pack` | `/research-validate` |
| Codex | `$research-ingest` | `$research-extract` | `$research-pack` | `$research-validate` |

```
python3 scripts/rkc_validate.py --root sample-knowledge
python3 scripts/rkc_pack.py subject.loop-policy.01J8X000000000000000000001 --root sample-knowledge
python3 tests/test_rkc.py
python3 tests/test_extract.py
python3 tests/test_plugin.py
```

Public samples are **Northstar / Lumenfield fiction**. Live dumps stay in private trees.

## Retrieval ladder

`rg` → `/research-pack` → BM25/Chroma → Kuzu last (Layer 1).

## Actor

`grok-bot/research-knowledge-capture`. Isolated session. Ready PR. No force-push. No write to main.
