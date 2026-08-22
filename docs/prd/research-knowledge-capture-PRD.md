# Product Requirements Document — Research Knowledge Capture (RKC)

| Field | Value |
|---|---|
| Status | Implementing v2.2 — Phase 0–3 + Phase 2 extractor landed |
| Date | 22 August 2026 |
| Repos | `research-knowledge-capture` (this repo), `research-graph` (Layer 1) |
| Tracking | WikiTicket SDD (`.work/todo.jsonl`) |
| Actor | `grok-bot/research-knowledge-capture` |

## 1. Thesis

RKC owns durable research truth in OKF. Agent Brain (Chroma + BM25 + Kuzu) is a disposable index. ContextPack controls disclosure. The index can always be destroyed and rebuilt from `knowledge/research/**`.

This is a ContentPack, not a new product. Same rules as PKC, SAC, and DEKC: owned types, registered rels, fail-closed writes, actor isolation.

## 2. Layers

| Layer | Repo | Owns |
|---|---|---|
| L0 | **this plugin** | nouns, folders, registered rels, ingest, extract, `/research-pack`, validate |
| L1 | `research-graph` | Chroma + BM25 + Kuzu projector, `/research-ask`. Owns **no** types. Projector stays here until a second consumer needs it in core. |

Retrieval ladder: `rg` → `/research-pack` → BM25/Chroma → Kuzu last.

Do not fork Agent Brain. `GRAPH_USE_LLM_EXTRACTION=false`. Default project `accepted|reviewed` only.

## 3. Eight v1 nouns

| Type | Folder | Notes |
|---|---|---|
| ResearchArea | `areas/` | Top domain |
| Subject | `subjects/` | Topic under an area. news-digest owns Topic — keep Subject. |
| ResearchTask | `tasks/` | One deep-research run. PKC owns Task. |
| SourceDocument | `sources/` | Metadata for an archived dump. news-digest owns Source. |
| ResearchQuestion | `questions/` | What the run was answering. PKC owns Question. |
| Claim | `claims/` | Atomic assertion + `claim_key` + `claim_kind` + `as_of` |
| Evidence | `evidence/` | Quote or span + locator into source-asset |
| Finding | `findings/` | Synthesized conclusion |

Do **not** mint Article (content-media) or write `Concept` for entities.

Shard claims/evidence by subject-slug as volume grows: `claims/<subject-slug>/`.

## 4. Registered rels

`has_subject`, `related_to`, `has_task`, `ingested_from`, `asks`, `answers`, `produced`, `asserts`, `evidenced_by`, `contradicts`, `supersedes`, `same_as`.

content-media owns `draws_from` (Article → Finding). Projector may expose `informs` as a **query-only** inverse. RKC never writes an edge whose target type it does not own.

Unknown type or rel is an **error**. Fail closed.

## 5. Fields and identity

- IDs: `<type-slug>.<subject-slug>.<ulid>` e.g. `claim.loop-policy.01J8X000000000000000000006`. Immutable after first commit. No rename; use `supersedes`.
- `claim_key = sha256(normalize(text)|claim_kind|subject_id)`. Same key → attach Evidence to the existing Claim. Near-matches use `same_as`. `contradicts` only when `claim_kind` matches and `as_of` ranges overlap.
- `claim_kind`: factual | numeric | definitional | predictive | causal
- `as_of` on Claim/Finding (temporal validity)
- Trust: `status` (draft|reviewed|accepted|rejected|superseded) is authoritative for replacement. BaseConcept `truth_state` is the lifecycle enum (`current|snapshot|superseded|archived|historical|proposed`) — do **not** overload it with epistemic values. `verified`, `generated`, `confidence` stay. Epistemic (`asserted|source_supported|corroborated|disputed`) is **derived** from edges.

## 6. Ingest and extract

Inbox `_inbox/research-dumps/` is not a type. Archive to `knowledge/research/source-assets/<sha256>/original.*`.

- Idempotency key: `sha256(bytes|prompt_hash|extractor_version)`.
- Fail-closed. Human PR gate. Required PR summary: new/merged claims, contradictions, skipped accepted nodes.
- Nodes with `status` in reviewed|accepted or `verified: true` are never auto-superseded (ADR 004).
- Segmentation with global locators (`rkc_segment.py`). Heuristic extract is deterministic. Overlay JSON is the agent/LLM path; quotes verified against the asset before any write (ADR 007).
- Vendors: grok, gemini, claude, deepseek, chatgpt, article.

`rkc_ingest.py` writes SourceDocument + ResearchTask shells. `rkc_extract.py` (or `--extract`) writes draft Claims/Evidence/Findings and the PR summary.

## 7. ContextPack

Structural `max_hops: 2` + spine expansion (ADR 003).

Hop-math: Subject → Task → Finding is already 2 hops, so Claim/Evidence would be unreachable without the spine. Once a Finding is in the pack, `asserts` → Claim and `evidenced_by` → Evidence do **not** consume hops.

- ResearchQuestion root: one inbound hop on `answers`.
- `max_nodes: 20` truncates by rank: status → verified → confidence → newer `as_of` → id.
- Token budget fail-closed if the root cannot fit.

## 8. Citation integrity

Finding → asserts → Claim → evidenced_by → Evidence → source-asset + locator.

Verbatim quotes are verified against the archived asset span. No Chroma/Kuzu blob citations.

## 9. Public samples

Northstar / Lumenfield **fiction only**. Eval corpus:

- Pack `subject.loop-policy.01J8X000000000000000000001` with hops=2 **must** include Claim + Evidence (spine).
- Pack `question.loop-policy.01J8X000000000000000000004` must include Finding via inbound `answers`.
- Unknown rel fails. Accepted Claim without `evidenced_by` fails. Verbatim mismatch fails.
- `claim_key` is stable under whitespace/case/punctuation.
- Corroborating dump with the same normalized claim attaches Evidence to the accepted Claim and does not change its status.
- Overlay quote missing from the asset writes nothing.

## 10. Phases and tasks

| Phase | Status | Tasks |
|---|---|---|
| 0 WikiTicket + ADRs | **done** | `.work/`, ADRs 001–007, actor isolation |
| 1 Schemas + samples + eval | **done** | 8 schemas, registry, fiction corpus, tests |
| 2 Ingest + extractor | **done** | archive, idempotency, segmentation, claim_key merge, overlay, PR summary |
| 3 `/research-pack` | **done** | spine, question inbound, rank, fail-closed budget |
| 4 `research-graph` | **stub** | projector + `/research-ask`; Agent Brain; no LLM extraction |
| 5 Article bridge | **todo** | content-media registry patch for `draws_from`; marketplace hardening |

## 11. Non-goals (v1)

- No UI. Plugins only.
- No second Article type.
- No Memgraph. Kuzu via Agent Brain in L1.
- Projector not in Agent Brain core until a second consumer exists.
- No auto-write of `draws_from`.
- Agent Brain does not extract; RKC does. `GRAPH_USE_LLM_EXTRACTION=false`.

## 12. Host matrix

Claude Code, Grok Build (zero-config Claude layout), Codex, Cursor, Agent Plugins 1.0. Skills live once under `skills/`.
