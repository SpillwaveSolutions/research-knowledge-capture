# ADR 005 — Claim identity

Status: accepted. 2026-08-22.

`claim_key = sha256(normalize(text)|claim_kind|subject_id)`.

Same key → attach Evidence to the existing Claim. Near-matches use `same_as`. `contradicts` only when `claim_kind` matches and `as_of` ranges overlap.
