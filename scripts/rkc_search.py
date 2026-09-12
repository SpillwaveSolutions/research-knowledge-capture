#!/usr/bin/env python3
"""Thin git-native search over an RKC knowledge tree.

Ladder: ripgrep prefilter → linear frontmatter/body scan. No Chroma, BM25,
Kuzu, or SQLite. Ranking is always computed in Python so scores stay identical
across engines. Layer 1 (`research-graph`) may feed seeds later.

Usage:
  python3 scripts/rkc_search.py "false-alert 1.4" --root sample-knowledge
  python3 scripts/rkc_search.py loop-policy --type Finding,ResearchQuestion --json
  python3 scripts/rkc_search.py detector --engine scan --limit 5
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rkc_common import OWNED_TYPES, SKIP_DIR_NAMES, iter_okf, knowledge_root, parse_okf

DEFAULT_LIMIT = 5
SEED_RANK = {
    "Finding": 0,
    "ResearchQuestion": 1,
    "Subject": 2,
    "Claim": 3,
    "Evidence": 4,
    "ResearchTask": 5,
    "SourceDocument": 6,
    "ResearchArea": 7,
}


def tokenize(q: str) -> list[str]:
    return [t for t in re.split(r"\s+", q.strip().lower()) if t]


def find_rg() -> str | None:
    return shutil.which("rg")


def rg_list_files(root: Path, terms: list[str]) -> list[Path] | None:
    """Prefilter with the first term. Remaining AND happens in Python."""
    rg = find_rg()
    research = root / "research"
    if not rg or not terms or not research.is_dir():
        return None
    cmd = [
        rg,
        "-l",
        "-i",
        "-F",
        "--glob",
        "*.md",
        "--glob",
        "!**/source-assets/**",
        "--glob",
        "!**/catalogs/**",
        "--glob",
        "!**/pr-summaries/**",
        terms[0],
        str(research),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError:
        return None
    if proc.returncode not in (0, 1):
        return None
    files: list[Path] = []
    for line in proc.stdout.splitlines():
        p = Path(line.strip())
        if p.is_file() and p.name.lower() not in {"index.md", "readme.md"}:
            if any(part in SKIP_DIR_NAMES for part in p.parts):
                continue
            files.append(p)
    return files


def scan_files(root: Path) -> list[Path]:
    return [path for path, _fm, _body in iter_okf(root)]


def candidate_files(
    root: Path,
    terms: list[str],
    *,
    use_rg: bool | None = None,
) -> tuple[list[Path], str]:
    if use_rg is False:
        return scan_files(root), "scan"
    if use_rg is None and not find_rg():
        return scan_files(root), "scan"
    hits = rg_list_files(root, terms)
    if hits is None:
        return scan_files(root), "scan"
    return hits, "rg"


def _rel(root: Path, path: Path) -> str:
    try:
        return "/" + path.relative_to(root).as_posix()
    except ValueError:
        return "/" + path.as_posix()


def _snippet(body: str, terms: list[str], width: int = 160) -> str:
    low = body.lower()
    pos = -1
    for t in terms:
        i = low.find(t)
        if i >= 0:
            pos = i
            break
    if pos < 0:
        text = re.sub(r"\s+", " ", body).strip()
        return text[:width] + ("…" if len(text) > width else "")
    start = max(0, pos - 40)
    end = min(len(body), pos + width)
    frag = re.sub(r"\s+", " ", body[start:end]).strip()
    if start > 0:
        frag = "…" + frag
    if end < len(body):
        frag = frag + "…"
    return frag


def search(
    root: Path,
    query: str,
    *,
    types: list[str] | None = None,
    limit: int = DEFAULT_LIMIT,
    use_rg: bool | None = None,
) -> tuple[list[dict[str, Any]], str]:
    terms = tokenize(query)
    if not terms:
        return [], "scan"

    type_filter = {t.lower() for t in (types or []) if t}
    files, engine = candidate_files(root, terms, use_rg=use_rg)
    results: list[dict[str, Any]] = []

    for path in files:
        try:
            fm, body = parse_okf(path)
        except Exception:
            continue
        ctype = str(fm.get("type") or "")
        if ctype not in OWNED_TYPES:
            continue
        if type_filter and ctype.lower() not in type_filter:
            continue

        hay_title = str(fm.get("title") or path.stem).lower()
        hay_desc = str(fm.get("description") or "").lower()
        hay_tags = " ".join(str(t) for t in (fm.get("tags") or [])).lower()
        hay_body = (body or "").lower()
        hay_id = str(fm.get("id") or path.stem).lower()
        full = f"{hay_title}\n{hay_desc}\n{hay_tags}\n{hay_body}\n{hay_id}"

        score = 0
        hits: list[str] = []
        missing = False
        for term in terms:
            if term not in full:
                missing = True
                break
            c_title = hay_title.count(term)
            c_desc = hay_desc.count(term)
            c_id = hay_id.count(term)
            c_tags = hay_tags.count(term)
            c_body = hay_body.count(term)
            score += c_title * 10 + c_desc * 5 + c_id * 6 + c_tags * 4 + min(c_body, 8)
            if c_title:
                hits.append("title")
            if c_desc:
                hits.append("description")
            if c_id:
                hits.append("id")
            if c_tags:
                hits.append("tags")
            if c_body:
                hits.append("body")
        if missing or score <= 0:
            continue

        results.append(
            {
                "id": fm.get("id") or path.stem,
                "path": _rel(root, path),
                "type": ctype,
                "title": fm.get("title") or path.stem,
                "description": fm.get("description") or "",
                "status": fm.get("status"),
                "score": score,
                "hits": sorted(set(hits)),
                "snippet": _snippet(body or str(fm.get("description") or ""), terms),
            }
        )

    results.sort(
        key=lambda r: (-r["score"], SEED_RANK.get(r["type"], 9), r["title"] or "")
    )
    return results[: max(0, limit)], engine


def render(results: list[dict[str, Any]], query: str, engine: str) -> str:
    lines = [f"# Search: {query}", "", f"{len(results)} hit(s) · engine {engine}", ""]
    if not results:
        lines.append("_No matches. Try `--engine scan`, fewer terms, or need-layer1-search._")
        return "\n".join(lines) + "\n"
    for r in results:
        lines.append(f"## [{r['title']}]({r['path']}) · `{r['type']}` · score {r['score']}")
        lines.append("")
        lines.append(f"`{r['id']}`")
        if r.get("description"):
            lines.append("")
            lines.append(str(r["description"]))
        if r.get("snippet"):
            lines.append("")
            lines.append(f"> {r['snippet']}")
        lines.append("")
        lines.append(f"_hits: {', '.join(r['hits'])}_")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="RKC full-text search (rg → scan)")
    ap.add_argument("query", help="Search terms (AND)")
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--type", dest="types", default=None, help="Comma-separated RKC types")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--engine",
        choices=("auto", "rg", "scan"),
        default="auto",
        help="Force a retrieval rung. Missing rg is not an error.",
    )
    args = ap.parse_args(argv)

    kr = knowledge_root(args.root)
    if not (kr / "research").is_dir():
        print(f"error: knowledge root not found: {kr}", file=sys.stderr)
        return 1

    use_rg: bool | None
    if args.engine == "scan":
        use_rg = False
    elif args.engine == "rg":
        use_rg = True
        if not find_rg():
            print(
                "rkc_search: rg not found; falling back to scan. Install ripgrep or pass --engine scan.",
                file=sys.stderr,
            )
            use_rg = False
    else:
        use_rg = None

    types = [t.strip() for t in (args.types or "").split(",") if t.strip()] or None
    unknown = [t for t in (types or []) if t not in OWNED_TYPES and t.lower() not in {x.lower() for x in OWNED_TYPES}]
    if unknown:
        print(
            f"error: unknown type {unknown[0]!r}. Use an RKC noun "
            f"(ResearchQuestion, not Question): {', '.join(sorted(OWNED_TYPES))}",
            file=sys.stderr,
        )
        return 2

    results, engine = search(kr, args.query, types=types, limit=args.limit, use_rg=use_rg)
    if args.json:
        print(
            json.dumps(
                {
                    "query": args.query,
                    "count": len(results),
                    "engine": engine,
                    "results": results,
                },
                indent=2,
            )
        )
    else:
        print(render(results, args.query, engine), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
