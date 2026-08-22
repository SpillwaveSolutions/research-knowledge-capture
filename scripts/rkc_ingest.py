#!/usr/bin/env python3
"""Idempotent inbox ingest.

Hashes, archives, writes SourceDocument + ResearchTask shells.
Same bytes + prompt hash + extractor version returns existing nodes (ADR 004).
Optional --extract runs the Phase 2 extractor after the shell lands.
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


def ingest_key_for(digest: str, extractor_version: str, prompt_hash: str = "") -> str:
    raw = f"{digest}|{prompt_hash or ''}|{extractor_version}"
    return hashlib.sha256(raw.encode()).hexdigest()


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
                "asset_path": fm.get("asset_path"),
                "idempotent": True,
            }
    return None


def ingest_file(
    src: Path,
    knowledge: Path,
    vendor: str,
    subject: str,
    extractor_version: str = "1",
    prompt_hash: str = "",
    extract: bool = False,
    subject_id: str | None = None,
    overlay: dict | None = None,
    dry_run: bool = False,
    shard: bool = True,
):
    digest = sha256_file(src)
    ingest_key = ingest_key_for(digest, extractor_version, prompt_hash)
    existing = find_existing(knowledge, ingest_key)
    if existing:
        if extract:
            existing["extract"] = _run_extract(
                knowledge,
                existing.get("asset_path"),
                vendor,
                subject,
                subject_id,
                existing.get("source_id"),
                existing.get("task_id"),
                overlay,
                extractor_version,
                prompt_hash,
                shard,
                dry_run,
            )
        return existing
    asset_dir = knowledge / "research" / "source-assets" / digest
    asset_dir.mkdir(parents=True, exist_ok=True)
    dest = asset_dir / ("original" + (src.suffix or ".md"))
    if not dest.exists():
        shutil.copy2(src, dest)
    rel_asset = f"research/source-assets/{digest}/{dest.name}"
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
prompt_hash: "{prompt_hash or ''}"
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
    result = {
        "source_id": source_id,
        "task_id": task_id,
        "sha256": digest,
        "ingest_key": ingest_key,
        "idempotent": False,
        "asset_path": rel_asset,
    }
    if extract:
        result["extract"] = _run_extract(
            knowledge,
            rel_asset,
            vendor,
            subject,
            subject_id,
            source_id,
            task_id,
            overlay,
            extractor_version,
            prompt_hash,
            shard,
            dry_run,
        )
    return result


def _run_extract(
    knowledge,
    asset_path,
    vendor,
    subject,
    subject_id,
    source_id,
    task_id,
    overlay,
    extractor_version,
    prompt_hash,
    shard,
    dry_run,
):
    from rkc_extract import EXTRACTOR_VERSION, run_extract

    return run_extract(
        knowledge=knowledge,
        asset_path=asset_path,
        subject_id=subject_id,
        subject_slug=subject,
        vendor=vendor,
        source_id=source_id,
        task_id=task_id,
        overlay=overlay,
        extractor_version=extractor_version or EXTRACTOR_VERSION,
        prompt_hash=prompt_hash,
        shard=shard,
        dry_run=dry_run,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inbox", type=Path)
    ap.add_argument("--knowledge", type=Path, default=plugin_root() / "sample-knowledge")
    ap.add_argument("--vendor", default="grok")
    ap.add_argument("--subject", default="unsorted")
    ap.add_argument("--subject-id", default=None)
    ap.add_argument("--extractor-version", default="1")
    ap.add_argument("--prompt-hash", default="")
    ap.add_argument("--prompt-file", type=Path, default=None)
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--overlay", type=Path, default=None)
    ap.add_argument("--no-shard", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    prompt_hash = args.prompt_hash
    if args.prompt_file:
        prompt_hash = hashlib.sha256(args.prompt_file.read_bytes()).hexdigest()
    overlay = json.loads(args.overlay.read_text(encoding="utf-8")) if args.overlay else None
    extractor_version = args.extractor_version
    if args.extract and extractor_version == "1":
        extractor_version = "2"
    results = []
    files = [args.inbox] if args.inbox.is_file() else sorted(args.inbox.rglob("*"))
    for f in files:
        if f.is_file() and f.suffix.lower() in {".md", ".txt"}:
            results.append(
                ingest_file(
                    f,
                    args.knowledge,
                    args.vendor,
                    slug(args.subject),
                    extractor_version,
                    prompt_hash,
                    extract=args.extract,
                    subject_id=args.subject_id,
                    overlay=overlay,
                    dry_run=args.dry_run,
                    shard=not args.no_shard,
                )
            )
    print(json.dumps({"ingested": results}, indent=2, default=str))


if __name__ == "__main__":
    main()
