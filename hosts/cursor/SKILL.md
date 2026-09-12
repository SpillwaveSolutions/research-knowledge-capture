---
name: cursor-research-knowledge-capture
description: Bind a Cursor agent to RKC. Capture research into OKF. Do not project the graph.
---

# Cursor / research-knowledge-capture

Follow `docs/CURSOR.md` and `docs/HOSTS.md`.

1. Identity: `cursor/research-knowledge-capture`.
2. Local Cursor may `/plugin install research-knowledge-capture`.
3. Commands: `/research-ingest`, `/research-extract`, `/research-pack`, `/research-retrieve`, `/research-search`, `/research-validate`.
4. Q&A retrieval: spawn `research-retriever`. Do not pack inline.
5. Never write Article or `draws_from` (content-media). Never invent rels.
6. Never auto-supersede accepted or verified claims. Overlay quotes must match the source-asset.
