#!/usr/bin/env python3
"""ContextPack: structural hops + spine expansion."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rkc_common import iter_okf, knowledge_root

STATUS_RANK = {"accepted": 0, "reviewed": 1, "draft": 2, "rejected": 3, "superseded": 4}


def load_graph(root: Path):
    nodes = {}
    out = {}
    inbound = {}
    for path, fm, body in iter_okf(root):
        nid = fm.get("id") or path.stem
        nodes[nid] = {**fm, "_path": str(path), "_body": body}
        for link in fm.get("links") or []:
            if not isinstance(link, dict):
                continue
            rel, tgt = link.get("rel"), link.get("target") or link.get("id")
            if not rel or not tgt:
                continue
            out.setdefault(nid, []).append((rel, tgt, link))
            inbound.setdefault(tgt, []).append((rel, nid, link))
    return nodes, out, inbound


def sort_key(n: dict):
    conf = n.get("confidence")
    conf_sort = -(conf if isinstance(conf, (int, float)) else -1)
    as_of = n.get("as_of")
    if as_of in (None, ""):
        as_of_key = (1,)
    else:
        as_of_key = tuple(-ord(c) for c in str(as_of))
    return (
        STATUS_RANK.get(n.get("status") or "draft", 9),
        0 if n.get("verified") else 1,
        conf_sort,
        as_of_key,
        n.get("id") or "",
    )


def pack(root: Path, root_id: str, max_hops=2, max_nodes=20):
    nodes, out, inbound = load_graph(root)
    if root_id not in nodes:
        raise SystemExit(f"unknown root {root_id}")
    if max_nodes < 1:
        raise SystemExit("token budget fail-closed: root cannot fit (max_nodes < 1)")
    included = {root_id}
    frontier = {root_id}
    for hop in range(max_hops):
        nxt = set()
        for nid in frontier:
            n = nodes[nid]
            edges = list(out.get(nid, []))
            if n.get("type") == "ResearchQuestion":
                for rel, src, link in inbound.get(nid, []):
                    if rel == "answers":
                        edges.append((rel, src, link))
            for rel, tgt, _ in edges:
                if tgt in nodes and tgt not in included:
                    nxt.add(tgt)
        for t in nxt:
            included.add(t)
        frontier = nxt
    # spine expansion: Finding → asserts → Claim → evidenced_by → Evidence
    spine = set()
    for nid in list(included):
        if nodes[nid].get("type") != "Finding":
            continue
        for rel, tgt, _ in out.get(nid, []):
            if rel == "asserts" and tgt in nodes:
                spine.add(tgt)
                for r2, t2, _ in out.get(tgt, []):
                    if r2 == "evidenced_by" and t2 in nodes:
                        spine.add(t2)
    included |= spine
    ranked = sorted(included, key=lambda i: (0 if i == root_id else 1, sort_key(nodes[i])))
    truncated = len(ranked) > max_nodes
    ranked = ranked[:max_nodes]
    if root_id not in ranked:
        raise SystemExit("token budget fail-closed: root cannot fit after rank truncate")
    pack_nodes = [nodes[i] for i in ranked]
    return {
        "root": root_id,
        "max_hops": max_hops,
        "max_nodes": max_nodes,
        "truncated": truncated,
        "packer_version": "1",
        "nodes": [
            {
                "id": n.get("id"),
                "type": n.get("type"),
                "title": n.get("title"),
                "status": n.get("status"),
                "path": n.get("_path"),
            }
            for n in pack_nodes
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root_id")
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--max-hops", type=int, default=2)
    ap.add_argument("--max-nodes", type=int, default=20)
    args = ap.parse_args()
    kr = knowledge_root(args.root)
    print(json.dumps(pack(kr, args.root_id, args.max_hops, args.max_nodes), indent=2))


if __name__ == "__main__":
    main()
