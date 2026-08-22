# ADR 007 — Deterministic extractor plus fail-closed overlay

Status: accepted. 2026-08-22.

The Phase 2 extractor is a script, not an implicit LLM call.

1. **Segment** the archived dump with global line/char locators (`rkc_segment.py`).
2. **Heuristic extract** is deterministic and is what CI runs.
3. **Overlay JSON** is the agent/LLM path. Every quote is verified against the source-asset before any OKF write. A missing quote fails closed (no writes).
4. **claim_key merge** attaches Evidence to the existing Claim. Near-matches get `same_as`. `contradicts` is a new draft pointing at the existing node.
5. **PR summary** is required and is not an OKF type. It lives under `research/catalogs/pr-summaries/` so `iter_okf` skips it.
6. Prompt hash joins the ingest key: `sha256(bytes|prompt_hash|extractor_version)`.

Agent Brain stays `GRAPH_USE_LLM_EXTRACTION=false`. This extractor writes OKF; the projector does not invent nodes.
