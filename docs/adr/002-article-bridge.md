# ADR 002 — Article bridge

Status: accepted. 2026-08-22.

Canonical stored edge: **Article → draws_from → Finding**.

content-media registers and writes this edge. RKC never writes an edge whose target type it does not own. Projector may expose `informs` as a query-only inverse.
