# ADR 004 — Re-ingest supersession

Status: accepted. 2026-08-22.

Idempotency key: source bytes + prompt hash + extractor version.

New extractor version creates draft nodes. Nodes with `status` in reviewed|accepted or `verified: true` are never auto-superseded.
