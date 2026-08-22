# Inbox contract

`_inbox/research-dumps/` is a drop folder, not an OKF type.

- Supported: `.md`, `.txt` in v1.
- Archive path: `knowledge/research/source-assets/<sha256>/original.*`.
- Idempotency key: `sha256(bytes|prompt_hash|extractor_version)`.
- Segmentation, claim_key merge, and PR summary: `scripts/rkc_extract.py` (see `/research-extract`).
