# Changelog

## 0.2.9 — 2026-09-19

Symlinked-root patch. Closes [#35](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/35) via [#37](https://github.com/SpillwaveSolutions/research-knowledge-capture/pull/37).

- **Engine parity holds on a symlinked root** ([#35](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/35)). `rg` prints resolved paths, and `search()` passed the caller's root through unresolved, so `_rel` could not make the rg hits relative. It fell into `except ValueError` and returned the full absolute path with a doubled leading slash, and the two engines then reported different paths for the same file. That is the parity contract 0.2.8 shipped to guarantee, and the caller could not tell the wrong path from a real one. The root is the cause, not `_rel`: both engines derive their paths from it, so `search()` resolves it once. One syscall per call, not one per hit.
- `_rel` no longer catches `ValueError`. The old branch did not recover, it returned a wrong value.
- Not macOS-only. `/var` is a symlink to `/private/var` there, so every `tempfile` root reproduces it. A symlinked checkout or a container bind mount is the same shape on Linux. CI has neither, which is why it shipped.
- New `tools/ci-local.sh` mirrors every step of `.github/workflows/ci.yml`. Its first check parses every workflow and fails when the glob finds none. PKC #82 was an unparseable `ci.yml` that failed at startup with zero jobs, and a workflow cannot check itself.
- Tests: `test_symlinked_root_agrees_across_engines` searches through a real symlink.

## 0.2.8 — 2026-09-19

Retrieval-ladder patch: parse once, engine parity, fail-closed rg override, rg test coverage. Closes [#30](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/30), [#31](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/31), [#32](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/32) via [#33](https://github.com/SpillwaveSolutions/research-knowledge-capture/pull/33).

- `rkc_search.py` scan path parses each file once (closes [#30](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/30)). `iter_okf` already parsed every file to yield it; `search()` parsed each again (measured 2.0×, ~2.9 s vs 99 ms for rg on a 3k-file tree). The scan rung is what hosts without ripgrep run.
- `rkc_validate.py` parses the tree once per run; `validate()` and `spine_issues()` share it (`load_tree`).
- Search parity ([#31](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/31)): the filename stem no longer enters the haystack (`hay_title`, `hay_id`). A titleless node whose filename matched the query was found by `scan` but invisible to the `rg` prefilter. Filenames are not content; display still falls back to the stem.
- `find_rg()` ([#32](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/32)) honours `RKC_RG_PATH` / `OKF_RG_PATH` / `SECOND_BRAIN_RG_PATH` and fails closed when the override is unusable — the same rule as research-graph and PKC, so one env var means one thing across plugins.
- Scan search skips unparsable files instead of aborting, matching the rg path.
- Tests: `tests/fixtures/fake_rg.py` (ported from PKC) and rg-vs-scan parity tests; the rg engine had no coverage.

## 0.2.7 — 2026-09-12

Query-time retrieval, PKC/SAC/DEKC parity.

- `agents/research-retriever.md` — isolated retriever. Scores and deep-walks off the parent. Returns a summary card only.
- `/research-retrieve` skill + command. Parent spawns the retriever; do not pack inline for Q&A.
- `rkc_pack.py --summary` — compact card-friendly pack (seed, hops/nodes/tokens, spine counts, lead nodes, gaps). `--tiny` is hops=1 / max_nodes=8. `--max-tokens` fail-closed (default 32000). Seed may be an id, path, or stem.
- `rkc_search.py` + `/research-search` — git-native `rg` → scan ladder. AND terms, type filter, limit 5, `--json`. No Chroma, BM25, or Kuzu. Layer 1 may feed seeds later.
- `research-capturer` delegates Q&A retrieval to `research-retriever`.

## 0.2.6 — 2026-08-25

- `--dry-run` does not create `research/catalogs/ingest-index.json` or its parent directories. Closes [#25](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/25).
- Empty, whitespace-only, and frontmatter-only sources are skipped and reported. `--min-source-bytes` defaults to 1. Closes [#26](https://github.com/SpillwaveSolutions/research-knowledge-capture/issues/26).

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
