# WORKLOG

WikiTicket SDD is the tracking system for this repo.

- Tickets: `.work/todo.jsonl`
- Policy: implement behind a WikiTicket; no force-push to main
- Actor: `grok-bot/research-knowledge-capture`

Phase 2 extractor (ticket `01KZWJ2RKC0000000000000005`) landed in 0.2.0: segmentation, claim_key merge, fail-closed overlay, PR summary.

Bulk-ingest hardening (ticket `01KZWJ2RKC0000000000000008`) landed in 0.2.1: ingest index, slug hash, YAML quoting, spine links, large-file cap. GitHub issues #1–#12.

Spine repair command (ticket `01KZWJ2RKC0000000000000009`) landed in 0.2.2: `rkc_spine.py` writes missing Subjects, `has_task`, ResearchAreas, and `has_subject`.

YAML date quoting, named parse errors, ingest-key default, and index.md titles (ticket `01KZWJ2RKC000000000000000A`) landed in 0.2.3: GitHub issues #6, #16–#19.

Intra-run extract merge path (ticket `01KZWJ2RKC000000000000000B`) landed in 0.2.4 after the chapter-1 ingest test.

Subject title from slug, not first source filename (ticket `01KZWJ2RKC000000000000000C`) landed in 0.2.5: GitHub issue #23.

Dry-run index write and empty-source ingest (ticket `01KZWJ2RKC000000000000000D`) landed in 0.2.6: GitHub issues #25 and #26.
