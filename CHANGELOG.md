# Changelog

## 0.2.0 — 2026-08-22

Phase 2 extractor.

- `rkc_segment.py` — global line/char locators, heading/paragraph packing.
- `rkc_extract.py` — heuristic extract + fail-closed overlay JSON.
- `claim_key` merge attaches Evidence to existing Claims; near-match `same_as`; `contradicts` as a new draft.
- Accepted / reviewed / verified nodes are never auto-superseded.
- Required PR summary under `research/catalogs/pr-summaries/` (not an OKF type).
- Ingest key is `sha256(bytes|prompt_hash|extractor_version)`. `--extract` flag.
- `/research-extract` skill + command. ADR 007.

## 0.1.0 — 2026-08-22

Phase 0–3 bootstrap.

- Eight nouns, twelve rels, JSON schemas, registry.
- Five-host packaging (Claude Code, Grok Build, Codex, Cursor, Agent Plugins 1.0).
- `/research-ingest`, `/research-pack`, `/research-validate`.
- Northstar / Lumenfield fiction sample + eval fixtures (spine, claim_key, quote verify, unknown rel).
- ADRs 001–006. Compact PRD under `docs/prd/`.
