#!/usr/bin/env python3
"""Idempotent inbox ingest.

Hashes, archives, writes SourceDocument + ResearchTask shells.
Same bytes + prompt hash + extractor version returns existing nodes (ADR 004).
Optional --extract runs the Phase 2 extractor after the shell lands.

Lookup is O(1) via research/catalogs/ingest-index.json. The tree walk is a
rebuild path (--rebuild-index), not the per-file hot path.
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
from rkc_common import (
    add_link,
    ensure_area,
    ensure_subject,
    iter_type,
    plugin_root,
    write_okf,
)
from rkc_ids import make_id, slug

GENERIC_NAMES = {"index.md", "index.txt", "readme.md", "readme.txt"}
INDEX_REL = Path("research") / "catalogs" / "ingest-index.json"
MAX_SOURCE_BYTES = 200 * 1024
VENDOR_CONVENTION = (
    "grok",
    "gemini",
    "claude",
    "deepseek",
    "chatgpt",
    "article",
    "perplexity",
    "unknown",
)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def ingest_key_for(digest: str, extractor_version: str, prompt_hash: str = "") -> str:
    raw = f"{digest}|{prompt_hash or ''}|{extractor_version}"
    return hashlib.sha256(raw.encode()).hexdigest()


def source_title(src: Path) -> str:
    if src.name.lower() in GENERIC_NAMES and src.parent.name not in {"", ".", "/"}:
        return src.parent.name
    return src.name


def index_path(knowledge: Path) -> Path:
    return knowledge / INDEX_REL


def load_ingest_index(knowledge: Path) -> dict:
    p = index_path(knowledge)
    if not p.exists():
        return {"version": 1, "keys": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "keys": {}}
    if not isinstance(data, dict):
        return {"version": 1, "keys": {}}
    data.setdefault("version", 1)
    data.setdefault("keys", {})
    return data


def save_ingest_index(knowledge: Path, index: dict) -> None:
    p = index_path(knowledge)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rebuild_ingest_index(knowledge: Path) -> dict:
    """Scan sources + tasks only. Does not parse claims or evidence."""
    task_by_source: dict[str, str] = {}
    for _path, fm, _body in iter_type(knowledge, "ResearchTask"):
        tid = fm.get("id")
        for link in fm.get("links") or []:
            if isinstance(link, dict) and link.get("rel") == "ingested_from" and link.get("target"):
                task_by_source[link["target"]] = tid
    keys = {}
    for _path, fm, _body in iter_type(knowledge, "SourceDocument"):
        key = fm.get("ingest_key")
        if not key:
            continue
        sid = fm.get("id")
        keys[key] = {
            "source_id": sid,
            "task_id": task_by_source.get(sid),
            "sha256": (fm.get("source_hash") or "").split(":")[-1],
            "asset_path": fm.get("asset_path"),
            "ingest_key": key,
        }
    index = {"version": 1, "keys": keys}
    save_ingest_index(knowledge, index)
    return index


class IngestSession:
    def __init__(self, knowledge: Path, *, rebuild: bool = False):
        self.knowledge = knowledge
        if rebuild or not index_path(knowledge).exists():
            self.index = rebuild_ingest_index(knowledge)
        else:
            self.index = load_ingest_index(knowledge)
        self.dirty = False
        self.extract_idx = None

    def find(self, ingest_key: str) -> dict | None:
        row = (self.index.get("keys") or {}).get(ingest_key)
        if not row:
            return None
        return {**row, "idempotent": True}

    def record(self, ingest_key: str, row: dict) -> None:
        self.index.setdefault("keys", {})[ingest_key] = {
            "source_id": row.get("source_id"),
            "task_id": row.get("task_id"),
            "sha256": row.get("sha256"),
            "asset_path": row.get("asset_path"),
            "ingest_key": ingest_key,
        }
        self.dirty = True

    def flush(self) -> None:
        if self.dirty:
            save_ingest_index(self.knowledge, self.index)
            self.dirty = False


def find_existing(knowledge: Path, ingest_key: str, session: IngestSession | None = None) -> dict | None:
    sess = session or IngestSession(knowledge)
    return sess.find(ingest_key)


def _link_spine(subject_path: Path | None, task_id: str, area: str | None, knowledge: Path, subject_id: str, dry_run: bool) -> dict:
    out = {"subject_id": subject_id, "area_id": None}
    if dry_run:
        return out
    if subject_path and task_id:
        add_link(subject_path, "has_task", task_id)
    if area:
        aid, apath, _created = ensure_area(knowledge, area)
        out["area_id"] = aid
        if apath and subject_id:
            add_link(apath, "has_subject", subject_id)
    return out


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
    source_kind: str = "deep_research",
    area: str | None = None,
    session: IngestSession | None = None,
    max_source_bytes: int = MAX_SOURCE_BYTES,
    max_candidates: int = 400,
    force_large: bool = False,
):
    knowledge = Path(knowledge)
    sess = session or IngestSession(knowledge)
    digest = sha256_file(src)
    ingest_key = ingest_key_for(digest, extractor_version, prompt_hash)
    subject = slug(subject)
    title = source_title(src)
    origin = str(src.resolve())
    existing = sess.find(ingest_key)
    if existing:
        sid, spath, _ = ensure_subject(knowledge, subject, title, dry_run=dry_run)
        existing["subject_id"] = existing.get("subject_id") or sid
        spine = _link_spine(spath, existing.get("task_id"), area, knowledge, sid, dry_run)
        existing.update(spine)
        if extract:
            existing["extract"] = _run_extract(
                knowledge,
                existing.get("asset_path"),
                vendor,
                subject,
                existing.get("subject_id") or subject_id or sid,
                existing.get("source_id"),
                existing.get("task_id"),
                overlay,
                extractor_version,
                prompt_hash,
                shard,
                dry_run,
                sess,
                max_source_bytes,
                max_candidates,
                force_large,
            )
        return existing

    asset_dir = knowledge / "research" / "source-assets" / digest
    if not dry_run:
        asset_dir.mkdir(parents=True, exist_ok=True)
    dest = asset_dir / ("original" + (src.suffix or ".md"))
    if not dry_run and not dest.exists():
        shutil.copy2(src, dest)
    rel_asset = f"research/source-assets/{digest}/{dest.name}"
    source_id = make_id("SourceDocument", subject)
    task_id = make_id("ResearchTask", subject)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sid, spath, _created = ensure_subject(knowledge, subject, title, dry_run=dry_run)
    subject_id = subject_id or sid
    if not dry_run:
        src_md = knowledge / "research" / "sources" / f"{source_id}.md"
        write_okf(
            src_md,
            {
                "type": "SourceDocument",
                "id": source_id,
                "title": title,
                "status": "draft",
                "verified": False,
                "generated": True,
                "vendor": vendor,
                "source_kind": source_kind,
                "source_hash": f"sha256:{digest}",
                "asset_path": rel_asset,
                "original_filename": src.name,
                "origin_path": origin,
                "captured_at": now,
                "ingest_version": str(extractor_version),
                "ingest_key": ingest_key,
                "prompt_hash": prompt_hash or "",
            },
            f"Archived dump `{src.name}`.\n",
        )
        task_md = knowledge / "research" / "tasks" / f"{task_id}.md"
        write_okf(
            task_md,
            {
                "type": "ResearchTask",
                "id": task_id,
                "title": f"Ingest {title}",
                "status": "draft",
                "verified": False,
                "generated": True,
                "vendor": vendor,
                "links": [{"rel": "ingested_from", "target": source_id}],
            },
            "Shell task created by rkc_ingest. Extractor should add Findings/Claims.\n",
        )
    spine = _link_spine(spath, task_id, area, knowledge, subject_id, dry_run)
    result = {
        "source_id": source_id,
        "task_id": task_id,
        "sha256": digest,
        "ingest_key": ingest_key,
        "idempotent": False,
        "asset_path": rel_asset,
        "origin_path": origin,
        "title": title,
        "subject_id": subject_id,
        "area_id": spine.get("area_id"),
    }
    if not dry_run:
        sess.record(ingest_key, result)
        sess.flush()
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
            sess,
            max_source_bytes,
            max_candidates,
            force_large,
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
    session: IngestSession | None,
    max_source_bytes,
    max_candidates,
    force_large,
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
        idx=None if session is None else session.extract_idx,
        session=session,
        max_source_bytes=max_source_bytes,
        max_candidates=max_candidates,
        force_large=force_large,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inbox", type=Path)
    ap.add_argument("--knowledge", type=Path, default=plugin_root() / "sample-knowledge")
    ap.add_argument("--vendor", default="grok", help="Free text. Convention: " + ", ".join(VENDOR_CONVENTION))
    ap.add_argument("--subject", default="unsorted")
    ap.add_argument("--subject-id", default=None)
    ap.add_argument("--area", default=None, help="ResearchArea slug. Created if missing; linked via has_subject.")
    ap.add_argument("--source-kind", default="deep_research")
    ap.add_argument("--extractor-version", default="1")
    ap.add_argument("--prompt-hash", default="")
    ap.add_argument("--prompt-file", type=Path, default=None)
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--overlay", type=Path, default=None)
    ap.add_argument("--no-shard", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rebuild-index", action="store_true")
    ap.add_argument("--max-source-bytes", type=int, default=MAX_SOURCE_BYTES)
    ap.add_argument("--max-candidates", type=int, default=400)
    ap.add_argument("--force-large", action="store_true")
    ap.add_argument("--errors-file", type=Path, default=None)
    args = ap.parse_args()
    prompt_hash = args.prompt_hash
    if args.prompt_file:
        prompt_hash = hashlib.sha256(args.prompt_file.read_bytes()).hexdigest()
    overlay = json.loads(args.overlay.read_text(encoding="utf-8")) if args.overlay else None
    extractor_version = args.extractor_version
    if args.extract and extractor_version == "1":
        extractor_version = "2"
    knowledge = args.knowledge
    session = IngestSession(knowledge, rebuild=args.rebuild_index)
    results = []
    errors = []
    files = [args.inbox] if args.inbox.is_file() else sorted(args.inbox.rglob("*"))
    files = [f for f in files if f.is_file() and f.suffix.lower() in {".md", ".txt"}]
    total = len(files)
    for i, f in enumerate(files, 1):
        try:
            rec = ingest_file(
                f,
                knowledge,
                args.vendor,
                slug(args.subject),
                extractor_version,
                prompt_hash,
                extract=args.extract,
                subject_id=args.subject_id,
                overlay=overlay,
                dry_run=args.dry_run,
                shard=not args.no_shard,
                source_kind=args.source_kind,
                area=args.area,
                session=session,
                max_source_bytes=args.max_source_bytes,
                max_candidates=args.max_candidates,
                force_large=args.force_large,
            )
            results.append(rec)
            ext = rec.get("extract") or {}
            n_claims = len(ext.get("new_claims") or [])
            skipped = ext.get("skipped") or ""
            print(
                f"[rkc-ingest] {i}/{total} {f} subject={slug(args.subject)} "
                f"idempotent={rec.get('idempotent')} claims={n_claims}"
                + (f" skipped={skipped}" if skipped else ""),
                file=sys.stderr,
            )
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            err = {"path": str(f), "error": str(e)}
            errors.append(err)
            print(f"[rkc-ingest] {i}/{total} {f} ERROR {e}", file=sys.stderr)
    session.flush()
    err_path = args.errors_file
    if err_path is None:
        err_path = knowledge / "research" / "catalogs" / "ingest-errors.jsonl"
    if errors:
        err_path.parent.mkdir(parents=True, exist_ok=True)
        with err_path.open("a", encoding="utf-8") as fh:
            for row in errors:
                fh.write(json.dumps(row) + "\n")
    print(json.dumps({"ingested": results, "errors": errors}, indent=2, default=str))
    return 1 if errors and not results else 0


if __name__ == "__main__":
    raise SystemExit(main())
