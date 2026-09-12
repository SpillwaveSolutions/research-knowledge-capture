---
name: research-retrieve
description: Spawn research-retriever for RKC Q&A. Parent gets a summary card only. Do not pack inline.
---

# research-retrieve

Parent session: **spawn `research-retriever`**. Do not run `rkc_pack.py` or walk Finding → Claim → Evidence inline for a question. Scoring and deep walks stay off the parent. The sub-agent returns the retrieval card only.

```
# Parent does not pack. The retriever does:
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_search.py "<query>" --root knowledge --limit 5 --json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_pack.py <id> --root knowledge --tiny --summary
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_pack.py <id> --root knowledge --summary
```

## When to use

User asks a ResearchQuestion, or wants context for a Finding, Claim, Evidence, Subject, or SourceDocument. Also when `/research-pack` would otherwise dump a full JSON pack into chat.

## When not to use

Capture, ingest, extract, validate, or spine repair — those stay on `research-capturer` and their write skills. This skill is retrieval-only.

## Layer 1

`research-graph` (Chroma / BM25 / Kuzu, `/research-ask`) is an **optional** later door that may feed seed ids into this same card. It is not required for this cut. L0 search + pack is enough. Do not stand up those indexes from this plugin. If L0 misses, the card says `need-layer1-search`.

## Card the parent should expect

```markdown
## Retrieval card
- Query: …
- Seed: `/path` (`Type`) — why chosen
- Fit: high|medium|low — one sentence
- Pack: hops=N nodes=N tokens=N/budget
- Spine: Finding → Claim → Evidence counts (or n/a)
- Lead nodes: (5–8 bullets)
- Open gaps: unanswered ResearchQuestion / thin evidence or none
- Next: stay|deepen|try-alt-seed `/other`|need-layer1-search
```

Never write PKC `Question`. The noun is `ResearchQuestion`.
