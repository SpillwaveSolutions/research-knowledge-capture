# Overlay JSON

Agent/LLM extraction must emit this schema. `rkc_extract.py --overlay` applies it fail-closed.

```json
{
  "subject_id": "subject.loop-policy.01J8X000000000000000000001",
  "as_of": "2026-08-22",
  "question_id": "question.loop-policy.01J8X000000000000000000004",
  "finding": {
    "title": "…",
    "text": "…"
  },
  "claims": [
    {
      "text": "Atomic assertion sentence.",
      "claim_kind": "numeric",
      "quote": "Exact span from the archived dump.",
      "confidence": 0.8,
      "as_of": "2026-08-22"
    }
  ]
}
```

`claim_kind`: `factual` | `numeric` | `definitional` | `predictive` | `causal`.

Optional on a claim: `same_as`, `contradicts`, `supersedes` (target ids). `supersedes` on an accepted/verified node is skipped.

If `quote` is not in the asset, the extractor exits non-zero and writes nothing.
