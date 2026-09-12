#!/usr/bin/env python3
"""ContextPack: structural hops + spine expansion."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rkc_common import iter_okf, knowledge_root, parse_okf

STATUS_RANK = {"accepted": 0, "reviewed": 1, "draft": 2, "rejected": 3, "superseded": 4}
DEFAULT_MAX_HOPS = 2
DEFAULT_MAX_NODES = 20
TINY_MAX_HOPS = 1
TINY_MAX_NODES = 8
DEFAULT_MAX_TOKENS = 32000
LEAD_MAX = 8
SPINE_TYPES = ("Finding", "Claim", "Evidence")


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


def resolve_root_id(root: Path, root_id: str, nodes: dict) -> str:
    """Accept a node id, file path, or stem."""
    if root_id in nodes:
        return root_id
    raw = Path(root_id)
    candidates = [raw]
    if not raw.is_absolute():
        candidates.extend(
            [
                root / raw,
                Path.cwd() / raw,
                root / "research" / raw,
            ]
        )
    for cand in candidates:
        if cand.is_file():
            fm, _body = parse_okf(cand)
            nid = fm.get("id") or cand.stem
            if nid in nodes:
                return nid
    stem = raw.stem
    if stem in nodes:
        return stem
    raise SystemExit(f"unknown root {root_id}")


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


def estimate_tokens(n: dict) -> int:
    """Cheap char/4 estimate. No tokenizer, no LLM."""
    parts = [
        str(n.get("id") or ""),
        str(n.get("type") or ""),
        str(n.get("title") or ""),
        str(n.get("description") or ""),
        str(n.get("status") or ""),
        str(n.get("_path") or ""),
        str(n.get("_body") or "")[:400],
    ]
    chars = sum(len(p) for p in parts)
    return max(1, (chars + 3) // 4)


def rel_path(root: Path, path: str | None) -> str:
    if not path:
        return ""
    p = Path(path)
    try:
        return "/" + p.relative_to(root).as_posix()
    except ValueError:
        pass
    try:
        return "/" + p.relative_to(root.parent).as_posix()
    except ValueError:
        return path


def spine_counts(pack_nodes: list[dict]) -> dict[str, int]:
    counts = {t: 0 for t in SPINE_TYPES}
    for n in pack_nodes:
        t = n.get("type")
        if t in counts:
            counts[t] += 1
    return counts


def detect_gaps(pack_ids: list[str], nodes: dict, out: dict, inbound: dict) -> list[str]:
    gaps: list[str] = []
    packed = set(pack_ids)
    for nid in pack_ids:
        n = nodes[nid]
        ntype = n.get("type")
        if ntype == "ResearchQuestion":
            answered = any(rel == "answers" and src in nodes for rel, src, _ in inbound.get(nid, []))
            if not answered:
                gaps.append(f"unanswered ResearchQuestion `{nid}` — {n.get('title') or nid}")
        elif ntype == "Claim":
            ev = [tgt for rel, tgt, _ in out.get(nid, []) if rel == "evidenced_by" and tgt in nodes]
            if not ev:
                gaps.append(f"thin evidence: Claim `{nid}` has no evidenced_by")
            elif not any(tgt in packed for tgt in ev):
                gaps.append(f"thin evidence: Claim `{nid}` evidence not in pack")
        elif ntype == "Finding":
            claims = [tgt for rel, tgt, _ in out.get(nid, []) if rel == "asserts" and tgt in nodes]
            if not claims:
                gaps.append(f"thin evidence: Finding `{nid}` asserts no Claim")
    return gaps or ["none"]


def node_card(n: dict) -> dict:
    return {
        "id": n.get("id"),
        "type": n.get("type"),
        "title": n.get("title"),
        "status": n.get("status"),
        "path": n.get("_path"),
    }


def format_summary(result: dict) -> str:
    """Compact card-friendly markdown. Parent wraps this into the retrieval card."""
    seed = result.get("seed") or {}
    seed_path = seed.get("path") or ""
    seed_type = seed.get("type") or "Unknown"
    seed_title = seed.get("title") or seed.get("id") or result.get("root")
    spine = result.get("spine") or {}
    if any(spine.get(t, 0) for t in SPINE_TYPES):
        spine_line = (
            f"Finding={spine.get('Finding', 0)} "
            f"Claim={spine.get('Claim', 0)} "
            f"Evidence={spine.get('Evidence', 0)}"
        )
    else:
        spine_line = "n/a"
    lines = [
        "## Pack summary",
        f"- Seed: `{seed_path}` (`{seed_type}`) — {seed_title}",
        (
            f"- Pack: hops={result.get('max_hops')} "
            f"nodes={len(result.get('nodes') or [])} "
            f"tokens={result.get('tokens')}/{result.get('token_budget')}"
        ),
        f"- Truncated: {str(bool(result.get('truncated'))).lower()}",
        f"- Spine: {spine_line}",
        "- Lead nodes:",
    ]
    leads = result.get("nodes") or []
    if not leads:
        lines.append("  - none")
    else:
        for n in leads[:LEAD_MAX]:
            path = n.get("path") or n.get("id")
            title = n.get("title") or n.get("id")
            lines.append(f"  - `{path}` (`{n.get('type')}`) — {title}")
    gaps = result.get("gaps") or ["none"]
    if gaps == ["none"]:
        lines.append("- Open gaps: none")
    else:
        lines.append("- Open gaps:")
        for g in gaps:
            lines.append(f"  - {g}")
    return "\n".join(lines) + "\n"


def pack(root: Path, root_id: str, max_hops=2, max_nodes=20, max_tokens=DEFAULT_MAX_TOKENS):
    nodes, out, inbound = load_graph(root)
    root_id = resolve_root_id(root, root_id, nodes)
    if root_id not in nodes:
        raise SystemExit(f"unknown root {root_id}")
    if max_nodes < 1:
        raise SystemExit("token budget fail-closed: root cannot fit (max_nodes < 1)")
    root_tokens = estimate_tokens(nodes[root_id])
    if root_tokens > max_tokens:
        raise SystemExit("token budget fail-closed: root cannot fit")
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
    selected: list[str] = []
    used = 0
    truncated = False
    for nid in ranked:
        cost = estimate_tokens(nodes[nid])
        if nid == root_id:
            selected.append(nid)
            used += cost
            continue
        if len(selected) >= max_nodes or used + cost > max_tokens:
            truncated = True
            break
        selected.append(nid)
        used += cost
    if root_id not in selected:
        raise SystemExit("token budget fail-closed: root cannot fit after rank truncate")
    truncated = truncated or len(ranked) > len(selected)
    pack_nodes = [nodes[i] for i in selected]
    seed = nodes[root_id]
    result = {
        "root": root_id,
        "max_hops": max_hops,
        "max_nodes": max_nodes,
        "truncated": truncated,
        "packer_version": "1",
        "tokens": used,
        "token_budget": max_tokens,
        "spine": spine_counts(pack_nodes),
        "gaps": detect_gaps(selected, nodes, out, inbound),
        "seed": {
            "id": seed.get("id") or root_id,
            "type": seed.get("type"),
            "title": seed.get("title"),
            "status": seed.get("status"),
            "path": rel_path(root, seed.get("_path")),
        },
        "nodes": [
            {
                **node_card(n),
                "path": rel_path(root, n.get("_path")),
            }
            for n in pack_nodes
        ],
    }
    return result


def main():
    ap = argparse.ArgumentParser(description="RKC ContextPack (structural hops + spine)")
    ap.add_argument("root_id", help="Node id, file path, or stem")
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--max-hops", type=int, default=None)
    ap.add_argument("--max-nodes", type=int, default=None)
    ap.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    ap.add_argument(
        "--tiny",
        action="store_true",
        help=f"Chat probe: hops={TINY_MAX_HOPS}, max_nodes={TINY_MAX_NODES}",
    )
    ap.add_argument(
        "--summary",
        action="store_true",
        help="Print compact card-friendly markdown instead of the full JSON pack",
    )
    args = ap.parse_args()
    if args.tiny:
        max_hops = TINY_MAX_HOPS if args.max_hops is None else args.max_hops
        max_nodes = TINY_MAX_NODES if args.max_nodes is None else args.max_nodes
    else:
        max_hops = DEFAULT_MAX_HOPS if args.max_hops is None else args.max_hops
        max_nodes = DEFAULT_MAX_NODES if args.max_nodes is None else args.max_nodes
    kr = knowledge_root(args.root)
    result = pack(kr, args.root_id, max_hops, max_nodes, args.max_tokens)
    if args.summary:
        print(format_summary(result), end="")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
