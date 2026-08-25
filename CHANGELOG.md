# Changelog

## 0.2.5 — 2026-08-25

- Subject title is derived from the `--subject` slug (or `--subject-title`), not the first source filename. `rkc_spine.py` uses the same rule when it creates a missing Subject. Closes [#23](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/23).

## 0.2.4 — 2026-08-25

- Intra-run claim merge no longer calls `add_link` on a node whose path is still `None`. A second file that repeats a claim from the first no longer crashes extract with `'NoneType' object has no attribute 'read_text'`.

## 0.2.3 — 2026-08-25

- Quote date-like YAML scalars. `as_of` / `timestamp` / `captured_at` stay strings through parse and write. Closes [#16](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/16) and [#17](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/17).
- `parse_okf` wraps `yaml.safe_load` in `ParseError` that names the file. `rkc_validate.py` reports it and continues. Closes [#6](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/6).
- Default `--extractor-version` to `EXTRACTOR_VERSION`. Same bytes under another version are reported, not duplicated, unless `--allow-reextract`. Idempotent `--extract` skips the extractor. Closes [#18](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/18).
- `index.md` / `README.md` titles become `parent/filename`. Closes [#19](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/19).

## 0.2.2 — 2026-08-24

- `rkc_spine.py` / `/research-spine` repairs Area → Subject → Task on a tree ingested by 0.2.0. `--link-tasks`, `--list-subjects`, `--area-map`. Idempotent.

## 0.2.1 — 2026-08-24


Bulk-ingest hardening from the first 2,997-file corpus ([#13](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/13)).

Blockers:

- Ingest lookup is O(1) via `research/catalogs/ingest-index.json`. Rebuild with `--rebuild-index` (sources + tasks only). [#1](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/1)
- Heuristic extract skips sources over 200 KB (`--force-large` to override), caps candidates, and matches near-duplicates through a token index instead of all-pairs Jaccard. [#2](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/2)
- Long subject slugs keep a prefix plus an 8-hex digest of the full value so distinct names no longer collapse. [#3](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/3)

Major:

- `pyyaml` is a required dependency. `_mini_yaml` unescapes `\\n` / `\\t` / `\\"` / `\\\\` and warns when the fallback runs. [#4](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/4)
- `_needs_quote` treats a trailing colon as quoted. Ingest writes through `write_okf`. [#5](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/5)
- `rkc_validate.py` reports the unparsable path and continues. [#6](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/6)
- SourceDocuments store `origin_path`. `index.md` / `README.md` titles use the parent directory. `--source-kind` is accepted. [#7](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/7)
- Archive-only ingest creates the Subject node. [#8](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/8)
- Ingest writes `has_task`. `--area` creates a ResearchArea and writes `has_subject`. `--spine` fails validation on a missing ladder. [#9](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/9)

Minor:

- Heuristic extractor drops Markdown/numbered headings and `filecite` / `citeturn` export artifacts. [#10](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/10)
- Per-file progress on stderr, ingest-key resume, `--errors-file` (does not abort the run). Intra-tree `--workers` is not added: concurrent writers race, and `pkill -f` orphans multiprocessing children. Shard by Subject instead. [#11](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/11)
- Vendor is free text. Convention now includes `perplexity` and `unknown`. [#12](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/12)

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
