# ADR 006 — ID convention

Status: accepted. 2026-08-22. Amended 2026-08-24.

Format: `<type-slug>.<subject-slug>.<ulid>` e.g. `claim.loop-policy.01J8X…`.

Immutable after first commit. No rename; use `supersedes`.

Subject slug is at most 64 characters (`[a-z0-9-]`). Inputs that normalize longer than 64 characters keep a 55-character prefix plus `-` plus an 8-hex SHA-256 of the *full* normalized value, so distinct long names do not collide (see issue #3).
