#!/usr/bin/env python3
"""Fail-closed RKC validator. Unknown type/rel is an error."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rkc_claim_key import normalize
from rkc_common import OWNED_RELS, OWNED_TYPES, iter_okf, knowledge_root, plugin_root, resolve_asset
from rkc_ids import valid_id

STATUS = {"draft", "reviewed", "accepted", "rejected", "superseded"}
KINDS = {"factual", "numeric", "definitional", "predictive", "causal"}
EPISTEMIC = {"asserted", "source_supported", "corroborated", "disputed"}


def derive_epistemic(fm: dict, evidence_by_claim: dict) -> str:
    cid = fm.get("id")
    evs = evidence_by_claim.get(cid, [])
    hashes = {e.get("source_hash") or (e.get("locator") or {}).get("asset_path") for e in evs}
    hashes.discard(None)
    if any(l.get("rel") == "contradicts" for l in fm.get("links") or []):
        return "disputed"
    if len(hashes) >= 2:
        return "corroborated"
    if evs:
        return "source_supported"
    return "asserted"


def validate(root: Path) -> list[str]:
    errors = []
    nodes = {}
    evidence_by_claim = {}
    parse_errors: list[str] = []
    files = list(iter_okf(root, collect_errors=parse_errors))
    errors.extend(parse_errors)
    for path, fm, body in files:
        t = fm.get("type")
        if t not in OWNED_TYPES:
            errors.append(f"{path}: unknown or unowned type {t!r}")
            continue
        nid = fm.get("id")
        if nid and not valid_id(nid):
            errors.append(f"{path}: invalid id {nid!r}")
        if nid:
            if nid in nodes:
                errors.append(f"{path}: duplicate id {nid}")
            nodes[nid] = (path, fm)
        st = fm.get("status")
        if st and st not in STATUS:
            errors.append(f"{path}: invalid status {st!r}")
        if t == "Claim":
            ck = fm.get("claim_kind")
            if ck and ck not in KINDS:
                errors.append(f"{path}: invalid claim_kind {ck!r}")
        for link in fm.get("links") or []:
            if not isinstance(link, dict):
                continue
            rel = link.get("rel")
            if rel and rel not in OWNED_RELS:
                errors.append(f"{path}: unknown rel {rel!r}")
            if rel == "evidenced_by" and nid:
                evidence_by_claim.setdefault(nid, []).append(link)
        if t == "Evidence" and fm.get("verbatim") is True:
            loc = fm.get("locator") or {}
            variant = loc.get("variant")
            text = fm.get("text") or ""
            asset = resolve_asset(root, loc.get("asset_path") or "")
            if variant in {"line_range", "char_range"}:
                if asset.exists() and variant == "line_range":
                    lines = asset.read_text(encoding="utf-8", errors="replace").splitlines()
                    sl = int(loc.get("start_line") or 1) - 1
                    el = int(loc.get("end_line") or sl + 1)
                    span = "\n".join(lines[sl:el])
                    if normalize(span) != normalize(text):
                        errors.append(f"{path}: verbatim quote does not match asset span")
                elif not asset.exists():
                    errors.append(f"{path}: missing source asset {loc.get('asset_path')}")
        if t == "Claim" and fm.get("status") == "accepted":
            links = fm.get("links") or []
            if not any(isinstance(l, dict) and l.get("rel") == "evidenced_by" for l in links):
                errors.append(f"{path}: accepted Claim missing evidenced_by")
    return errors


def spine_issues(root: Path) -> list[str]:
    """Subjects without incoming has_subject, tasks without incoming has_task."""
    parse_errors: list[str] = []
    files = list(iter_okf(root, collect_errors=parse_errors))
    has_subject_targets: set[str] = set()
    has_task_targets: set[str] = set()
    subjects = []
    tasks = []
    for path, fm, _body in files:
        nid = fm.get("id")
        t = fm.get("type")
        for link in fm.get("links") or []:
            if not isinstance(link, dict):
                continue
            if link.get("rel") == "has_subject" and link.get("target"):
                has_subject_targets.add(link["target"])
            if link.get("rel") == "has_task" and link.get("target"):
                has_task_targets.add(link["target"])
        if t == "Subject" and nid:
            subjects.append((path, nid))
        if t == "ResearchTask" and nid:
            tasks.append((path, nid))
    issues = []
    for path, nid in subjects:
        if nid not in has_subject_targets:
            issues.append(f"{path}: Subject has no incoming has_subject")
    for path, nid in tasks:
        if nid not in has_task_targets:
            issues.append(f"{path}: ResearchTask has no incoming has_task")
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--hook", action="store_true")
    ap.add_argument(
        "--spine",
        action="store_true",
        help="Fail when a Subject lacks incoming has_subject or a ResearchTask lacks incoming has_task.",
    )
    args = ap.parse_args()
    root = knowledge_root(args.root)
    errs = validate(root)
    warnings = spine_issues(root)
    if args.spine:
        errs.extend(warnings)
    elif warnings:
        print(f"RKC spine warnings ({len(warnings)})", file=sys.stderr)
        for w in warnings:
            print(" warning:", w, file=sys.stderr)
    if errs:
        print("RKC validate FAILED")
        for e in errs:
            print(" -", e)
        sys.exit(1)
    print(f"RKC validate OK ({root})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
