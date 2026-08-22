#!/usr/bin/env python3
"""Idempotent inbox ingest skeleton.

Full LLM extraction is agent-driven. This hashes, archives, and writes
SourceDocument + ResearchTask shells. Same bytes + extractor version
returns the existing nodes (ADR 004).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rkc_common import iter_okf, plugin_root
from rkc_ids import make_id, slug


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def find_existing(knowledge: Path, ingest_key: str) -> dict | None:
    sources = knowledge / "research" / "sources"
    if not sources.exists():
        return None
    for path, fm, _body in iter_okf(knowledge):
        if fm.get("type") == "SourceDocument" and fm.get("ingest_key") == ingest_key:
            task_id = None
            for p2, fm2, _ in iter_okf(knowledge):
                if fm2.get("type") != "ResearchTask":
                    continue
                for link in fm2.get("links") or []:
                    if isinstance(link, dict) and link.get("rel") == "ingested_from" and link.get("target") == fm.get("id"):
                        task_id = fm2.get("id")
                        break
            return {
                "source_id": fm.get("id"),
                "task_id": task_id,
                "sha256": (fm.get("source_hash") or "").split(":")[-1],
                "ingest_key": ingest_key,
                "idempotent": True,
            }
    return None


def ingest_file(src: Path, knowledge: Path, vendor: str, subject: str, extractor_version: str = "1"):
    digest = sha256_file(src)
    ingest_key = hashlib.sha256(f"{digest}|{extractor_version}".encode()).hexdigest()
    existing = find_existing(knowledge, ingest_key)
    if existing:
        return existing
    asset_dir = knowledge / "research" / "source-assets" / digest
    asset_dir.mkdir(parents=True, exist_ok=True)
    dest = asset_dir / "original.md"
    if not dest.exists():
        shutil.copy2(src, dest)
    rel_asset = f"research/source-assets/{digest}/original.md"
    source_id = make_id("SourceDocument", subject)
    task_id = make_id("ResearchTask", subject)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    src_md = knowledge / "research" / "sources" / f"{source_id}.md"
    src_md.parent.mkdir(parents=True, exist_ok=True)
    src_md.write_text(
        f"""---
type: SourceDocument
id: {source_id}
title: {src.name}
status: draft
verified: false
generated: true
vendor: {vendor}
source_kind: deep_research
source_hash: sha256:{digest}
asset_path: {rel_asset}
original_filename: {src.name}
captured_at: {now}
ingest_version: "{extractor_version}"
ingest_key: {ingest_key}
---
Archived dump `{src.name}`.
""",
        encoding="utf-8",
    )
    task_md = knowledge / "research" / "tasks" / f"{task_id}.md"
    task_md.parent.mkdir(parents=True, exist_ok=True)
    task_md.write_text(
        f"""---
type: ResearchTask
id: {task_id}
title: Ingest {src.name}
status: draft
verified: false
generated: true
vendor: {vendor}
links:
  - rel: ingested_from
    target: {source_id}
---
Shell task created by rkc_ingest. Extractor should add Findings/Claims.
""",
        encoding="utf-8",
    )
    return {
        "source_id": source_id,
        "task_id": task_id,
        "sha256": digest,
        "ingest_key": ingest_key,
        "idempotent": False,
        "asset_path": rel_asset,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inbox", type=Path)
    ap.add_argument("--knowledge", type=Path, default=plugin_root() / "sample-knowledge")
    ap.add_argument("--vendor", default="grok")
    ap.add_argument("--subject", default="unsorted")
    ap.add_argument("--extractor-version", default="1")
    args = ap.parse_args()
    results = []
    files = [args.inbox] if args.inbox.is_file() else sorted(args.inbox.rglob("*"))
    for f in files:
        if f.is_file() and f.suffix.lower() in {".md", ".txt"}:
            results.append(
                ingest_file(f, args.knowledge, args.vendor, slug(args.subject), args.extractor_version)
            )
    print(json.dumps({"ingested": results}, indent=2))


if __name__ == "__main__":
    main()
