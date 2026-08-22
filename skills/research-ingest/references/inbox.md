# Inbox contract

`_inbox/research-dumps/` is a drop folder, not an OKF type.

- Supported: `.md`, `.txt` in v1.
- Archive path: `knowledge/research/source-assets/<sha256>/original.*`.
- Idempotency key: `sha256(bytes) + extractor_version`. Prompt hash joins in Phase 2.
- Segmentation and PR summary are agent-owned, not this script.
