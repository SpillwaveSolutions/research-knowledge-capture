# ADR 003 — Structural hops vs spine expansion

Status: accepted. 2026-08-22.

`max_hops` (default 2) applies to the structural walk. Once a Finding is in the pack, `asserts` → Claim and `evidenced_by` → Evidence do not consume hop budget. From a ResearchQuestion root, one inbound hop on `answers` is allowed.
