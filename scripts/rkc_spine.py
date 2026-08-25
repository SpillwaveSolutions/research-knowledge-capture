#!/usr/bin/env python3
"""Repair the Area → Subject → Task spine on an existing knowledge tree.

0.2.0 ingest wrote ResearchTasks (and sometimes Subjects) with no has_task or
has_subject edges and no ResearchArea nodes. This command is idempotent.

  python3 scripts/rkc_spine.py --knowledge knowledge --link-tasks
  python3 scripts/rkc_spine.py --knowledge knowledge --list-subjects
  python3 scripts/rkc_spine.py --knowledge knowledge --area-map areas.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rkc_common import add_link, ensure_area, ensure_subject, iter_type, knowledge_root
from rkc_ids import subject_slug_from_id


def load_area_map(path: Path | None) -> list[dict]:
    if not path:
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "areas" in data:
        areas = data["areas"]
    elif isinstance(data, list):
        areas = data
    else:
        raise SystemExit("area-map must be a list or {\"areas\": [...]}")
    out = []
    for row in areas:
        if not isinstance(row, dict) or not row.get("slug"):
            raise SystemExit(f"area-map entry missing slug: {row!r}")
        out.append(
            {
                "slug": row["slug"],
                "title": row.get("title") or row["slug"].replace("-", " ").title(),
                "subjects": [str(s) for s in (row.get("subjects") or [])],
                "prefixes": [str(p) for p in (row.get("prefixes") or [])],
            }
        )
    return out


def collect_tasks(knowledge: Path) -> list[tuple[Path, dict]]:
    return [(p, fm) for p, fm, _ in iter_type(knowledge, "ResearchTask")]


def collect_subjects(knowledge: Path) -> list[tuple[Path, dict]]:
    return [(p, fm) for p, fm, _ in iter_type(knowledge, "Subject")]


def incoming_has_subject(knowledge: Path) -> set[str]:
    targets: set[str] = set()
    for _p, fm, _ in iter_type(knowledge, "ResearchArea"):
        for link in fm.get("links") or []:
            if isinstance(link, dict) and link.get("rel") == "has_subject" and link.get("target"):
                targets.add(link["target"])
    return targets


def match_area(subject_slug: str, areas: list[dict]) -> dict | None:
    for area in areas:
        if subject_slug in area["subjects"]:
            return area
    for area in areas:
        for prefix in area["prefixes"]:
            if prefix and subject_slug.startswith(prefix):
                return area
    return None


def link_tasks(knowledge: Path, *, dry_run: bool) -> dict:
    created_subjects = 0
    linked = 0
    skipped = 0
    by_slug: dict[str, tuple[str, Path | None]] = {}
    for path, fm in collect_subjects(knowledge):
        sid = fm.get("id") or ""
        slug = subject_slug_from_id(sid)
        by_slug[slug] = (sid, path)
    for path, fm in collect_tasks(knowledge):
        tid = fm.get("id")
        if not tid:
            continue
        slug = subject_slug_from_id(tid)
        if slug not in by_slug:
            title = fm.get("title") or slug.replace("-", " ").title()
            if dry_run:
                created_subjects += 1
                linked += 1
                continue
            sid, spath, created = ensure_subject(knowledge, slug, title, dry_run=False)
            by_slug[slug] = (sid, spath)
            if created:
                created_subjects += 1
        sid, spath = by_slug[slug]
        if dry_run:
            linked += 1
            continue
        if spath and add_link(spath, "has_task", tid):
            linked += 1
            by_slug[slug] = (sid, spath)
        else:
            skipped += 1
    return {"created_subjects": created_subjects, "has_task_written": linked, "has_task_existing": skipped}


def apply_areas(knowledge: Path, areas: list[dict], *, dry_run: bool, default_area: str | None) -> dict:
    created_areas = 0
    linked = 0
    skipped = 0
    unmatched = []
    for path, fm in collect_subjects(knowledge):
        sid = fm.get("id")
        if not sid:
            continue
        slug = subject_slug_from_id(sid)
        area = match_area(slug, areas)
        if area is None and default_area:
            area = {"slug": default_area, "title": default_area.replace("-", " ").title(), "subjects": [], "prefixes": []}
        if area is None:
            unmatched.append(slug)
            continue
        if dry_run:
            linked += 1
            continue
        aid, apath, created = ensure_area(knowledge, area["slug"], area["title"], dry_run=False)
        if created:
            created_areas += 1
        if apath and add_link(apath, "has_subject", sid):
            linked += 1
        else:
            skipped += 1
    return {
        "created_areas": created_areas,
        "has_subject_written": linked,
        "has_subject_existing": skipped,
        "unmatched_subjects": sorted(set(unmatched)),
    }


def list_subjects(knowledge: Path) -> list[dict]:
    linked = incoming_has_subject(knowledge)
    task_count: dict[str, int] = {}
    for _p, fm in collect_tasks(knowledge):
        slug = subject_slug_from_id(fm.get("id") or "")
        task_count[slug] = task_count.get(slug, 0) + 1
    rows = []
    seen = set()
    for path, fm in collect_subjects(knowledge):
        sid = fm.get("id") or ""
        slug = subject_slug_from_id(sid)
        seen.add(slug)
        rows.append(
            {
                "slug": slug,
                "id": sid,
                "title": fm.get("title"),
                "tasks": task_count.get(slug, 0),
                "has_subject": sid in linked,
                "path": str(path),
            }
        )
    for slug, n in sorted(task_count.items()):
        if slug in seen:
            continue
        rows.append(
            {
                "slug": slug,
                "id": None,
                "title": None,
                "tasks": n,
                "has_subject": False,
                "path": None,
                "missing_subject": True,
            }
        )
    rows.sort(key=lambda r: r["slug"])
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Create missing Subjects/Areas and write has_task / has_subject.")
    ap.add_argument("--knowledge", type=Path, default=None)
    ap.add_argument("--link-tasks", action="store_true", help="Ensure a Subject per task slug and write has_task.")
    ap.add_argument("--list-subjects", action="store_true")
    ap.add_argument("--area-map", type=Path, default=None, help="JSON list of {slug, title, subjects, prefixes}.")
    ap.add_argument("--default-area", default=None, help="Area slug for subjects that miss the map.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not (args.link_tasks or args.list_subjects or args.area_map):
        ap.error("pass --link-tasks, --list-subjects, and/or --area-map")
    kr = args.knowledge or knowledge_root()
    if args.knowledge and (args.knowledge / "research").exists():
        kr = args.knowledge
    summary: dict = {"knowledge": str(kr), "dry_run": args.dry_run}
    if args.list_subjects:
        summary["subjects"] = list_subjects(kr)
    if args.link_tasks:
        summary["tasks"] = link_tasks(kr, dry_run=args.dry_run)
    if args.area_map or args.default_area:
        areas = load_area_map(args.area_map)
        summary["areas"] = apply_areas(kr, areas, dry_run=args.dry_run, default_area=args.default_area)
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
