---
name: research-pack
description: Build an RKC ContextPack. Structural max_hops=2 plus Finding→Claim→Evidence spine. Question roots allow one inbound hop on answers.
---

# research-pack

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rkc_pack.py <id> --root knowledge
```

## Rules (ADR 003)

- Structural `max_hops` default 2.
- Once a Finding is in the pack, `asserts` → Claim and `evidenced_by` → Evidence do **not** consume hops.
- ResearchQuestion root: one inbound hop on `answers`.
- `max_nodes` default 20. Truncate by rank: status → verified → confidence → newer as_of → id.
- Token budget fail-closed if the root cannot fit.
- Default project filter in Layer 1 is accepted|reviewed; this packer includes whatever is in the tree.

Do not cite Chroma or Kuzu blobs. Citations are Finding → Claim → Evidence → source-asset.
