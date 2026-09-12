---
name: research-pack
description: Build an RKC ContextPack. Structural max_hops=2 plus Finding→Claim→Evidence spine. Question roots allow one inbound hop on answers.
---

# research-pack

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_pack.py <id> --root knowledge
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_pack.py <id> --root knowledge --summary
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_pack.py <id> --root knowledge --tiny --summary
```

For Q&A, the parent spawns `research-retriever` (`/research-retrieve`) and takes the card. Do not dump this pack into the parent chat.

## Rules (ADR 003)

- Structural `max_hops` default 2.
- Once a Finding is in the pack, `asserts` → Claim and `evidenced_by` → Evidence do **not** consume hops.
- ResearchQuestion root: one inbound hop on `answers`.
- `max_nodes` default 20. Truncate by rank: status → verified → confidence → newer as_of → id.
- `--tiny` is hops=1, max_nodes=8 (chat probe).
- `--summary` prints a compact card-friendly pack (seed, hops/nodes/tokens, spine counts, lead nodes, gaps).
- Token budget (`--max-tokens`, default 32000) is fail-closed if the root cannot fit.
- Seed may be a node id, file path, or stem.
- Default project filter in Layer 1 is accepted|reviewed; this packer includes whatever is in the tree.

Do not cite Chroma or Kuzu blobs. Citations are Finding → Claim → Evidence → source-asset.
