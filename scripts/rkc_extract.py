#!/usr/bin/env python3
"""Phase 2 extractor: segment, claim_key merge, fail-closed overlay, PR summary.

Heuristic path is deterministic (no LLM). Overlay JSON is the agent/LLM path;
quotes are verified against the archived asset before any write.

Never auto-supersedes reviewed|accepted|verified nodes (ADR 004).
Same claim_key → attach Evidence (ADR 005). Near-match → same_as.
contradicts only when claim_kind matches and as_of overlaps.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rkc_claim_key import claim_key, jaccard, normalize, polarity, tokens
from rkc_common import (
    ACTOR,
    OWNED_RELS,
    add_link,
    concept_dir,
    ensure_subject as ensure_subject_node,
    is_protected,
    iter_okf,
    knowledge_root,
    plugin_root,
    write_okf,
)
from rkc_ids import make_id, slug, subject_slug_from_id, valid_id
from rkc_segment import locate_quote, segment_markdown

EXTRACTOR_VERSION = "2"
KINDS = {"factual", "numeric", "definitional", "predictive", "causal"}
SKIP_PREFIX = re.compile(
    r"^(method|vendor|source|note|see also|references?|disclaimer|"
    r"table of contents|contents|appendix|bibliography|footnotes?|"
    r"license|copyright|changelog)\s*:",
    re.I,
)
HEADING_OR_SECTION = re.compile(r"^(?:#{1,6}\s+|\d+(?:\.\d+)+\s+\S)")
EXPORT_ARTIFACT = re.compile(r"\b(?:filecite|citeturn)\w*\b", re.I)
HAS_VERB = re.compile(
    r"\b(is|are|was|were|be|been|being|has|have|had|do|does|did|"
    r"can|could|will|would|may|might|shall|should|"
    r"recorded|holds|showed|caused|refers|means|tracks)\b",
    re.I,
)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")
SAME_AS_THRESHOLD = 0.78
CONTRA_THRESHOLD = 0.5
MAX_SOURCE_BYTES = 200 * 1024
MAX_CANDIDATES = 400
MAX_JACCARD = 64


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def as_of_overlap(a, b) -> bool:
    if not a or not b:
        return True
    return str(a) == str(b)


def classify_kind(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\bis defined as\b|\brefers to\b|\bmeans that\b", t):
        return "definitional"
    if re.search(r"\bwill\b|\bexpected to\b|\bforecast\b|\bprojected to\b", t):
        return "predictive"
    if re.search(r"\bcaused\b|\bbecause\b|\bdue to\b|\bled to\b|\bresulted in\b|\btracks a\b", t):
        return "causal"
    if re.search(r"\d+(?:\.\d+)?%|\d{1,3}(?:,\d{3})+|\b\d+\.\d+\b", t):
        return "numeric"
    if len(text) >= 50 and re.search(r"\b(recorded|holds|showed|is|are|was|were)\b", t):
        return "factual"
    return None


def split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    parts = SENT_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip()]


def strip_artifacts(text: str) -> str:
    text = EXPORT_ARTIFACT.sub("", text or "")
    return re.sub(r"\s+", " ", text).strip()


def is_claim_sentence(text: str) -> bool:
    if len(text) < 40 or len(text) > 400:
        return False
    if text.endswith("?"):
        return False
    if text.lstrip().startswith("#"):
        return False
    if HEADING_OR_SECTION.match(text):
        return False
    if SKIP_PREFIX.match(text):
        return False
    if not HAS_VERB.search(text):
        return False
    return classify_kind(text) is not None


def title_from(text: str, n: int = 72) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if len(t) <= n:
        return t.rstrip(".")
    cut = t[:n]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


def _index_claim(idx: dict, rec: dict) -> None:
    text = rec["fm"].get("description") or rec.get("body") or ""
    for tok in tokens(text):
        idx.setdefault("token_index", {}).setdefault(tok, []).append(rec)


def index_nodes(knowledge: Path) -> dict:
    by_type: dict[str, list[dict]] = {}
    by_id: dict[str, dict] = {}
    claims_by_key: dict[str, list[dict]] = {}
    evidence_index: list[dict] = []
    idx: dict = {
        "by_type": by_type,
        "by_id": by_id,
        "claims_by_key": claims_by_key,
        "evidence": evidence_index,
        "token_index": {},
    }
    for path, fm, body in iter_okf(knowledge):
        rec = {"path": path, "fm": fm, "body": body}
        t = fm.get("type")
        by_type.setdefault(t, []).append(rec)
        if fm.get("id"):
            by_id[fm["id"]] = rec
        if t == "Claim":
            ck = fm.get("claim_key")
            if ck:
                claims_by_key.setdefault(ck, []).append(rec)
            _index_claim(idx, rec)
        if t == "Evidence":
            evidence_index.append(rec)
    return idx


def find_subject(knowledge: Path, subject_slug: str, idx: dict | None = None) -> dict | None:
    idx = idx or index_nodes(knowledge)
    prefix = f"subject.{subject_slug}."
    for rec in idx["by_type"].get("Subject", []):
        if (rec["fm"].get("id") or "").startswith(prefix):
            return rec
    return None


def ensure_subject(knowledge: Path, subject_slug: str, title: str | None, dry_run: bool, idx: dict) -> tuple[str, bool]:
    rec = find_subject(knowledge, subject_slug, idx)
    if rec:
        return rec["fm"]["id"], False
    sid, path, created = ensure_subject_node(knowledge, subject_slug, title, dry_run=dry_run)
    if created and path is not None and not dry_run:
        from rkc_common import parse_okf

        fm, body = parse_okf(path)
        rec = {"path": path, "fm": fm, "body": body}
        idx.setdefault("by_type", {}).setdefault("Subject", []).append(rec)
        idx.setdefault("by_id", {})[sid] = rec
    return sid, created


def remember_evidence(idx: dict, evid_id: str, loc: dict, source_hash: str, text: str) -> None:
    rec = {
        "fm": {
            "id": evid_id,
            "locator": loc,
            "source_hash": source_hash,
            "text": text,
        },
        "path": None,
        "body": "",
    }
    idx["evidence"].append(rec)
    idx["by_id"][evid_id] = rec


def existing_evidence_for(claim_id: str, loc: dict, source_hash: str, idx: dict) -> bool:
    for rec in idx["evidence"]:
        fm = rec["fm"]
        locator = fm.get("locator") or {}
        same_span = (
            locator.get("start_line") == loc.get("start_line")
            and locator.get("end_line") == loc.get("end_line")
            and locator.get("asset_path") == loc.get("asset_path")
        )
        same_hash = (fm.get("source_hash") or "") == source_hash
        if not (same_span or (same_hash and normalize(fm.get("text") or "") == normalize(loc.get("text") or ""))):
            continue
        # linked from this claim?
        claim = idx["by_id"].get(claim_id)
        if not claim:
            continue
        evid_id = fm.get("id")
        for link in claim["fm"].get("links") or []:
            if isinstance(link, dict) and link.get("rel") == "evidenced_by" and link.get("target") == evid_id:
                return True
    return False


def write_evidence(
    knowledge: Path,
    subject_slug: str,
    quote_span: dict,
    asset_path: str,
    source_hash: str,
    vendor: str,
    shard: bool,
    dry_run: bool,
) -> str:
    eid = make_id("Evidence", subject_slug)
    if dry_run:
        return eid
    path = concept_dir(knowledge, "Evidence", subject_slug, shard) / f"{eid}.md"
    write_okf(
        path,
        {
            "type": "Evidence",
            "id": eid,
            "title": title_from(quote_span["text"], 64),
            "status": "draft",
            "verified": False,
            "generated": True,
            "kind": "quote",
            "verbatim": True,
            "text": quote_span["text"],
            "locator": {
                "variant": "line_range",
                "asset_path": asset_path,
                "start_line": quote_span["start_line"],
                "end_line": quote_span["end_line"],
            },
            "source_hash": source_hash,
            "truth_state": "proposed",
            "author": ACTOR,
            "timestamp": now_iso(),
            "tags": ["extracted", vendor],
        },
        f"# Evidence\n\n{quote_span['text']}\n",
    )
    return eid


def write_claim(
    knowledge: Path,
    subject_slug: str,
    subject_id: str,
    text: str,
    kind: str,
    vendor: str,
    as_of: str | None,
    confidence: float,
    extra_links: list[dict],
    shard: bool,
    dry_run: bool,
) -> str:
    cid = make_id("Claim", subject_slug)
    if dry_run:
        return cid
    path = concept_dir(knowledge, "Claim", subject_slug, shard) / f"{cid}.md"
    links = list(extra_links)
    write_okf(
        path,
        {
            "type": "Claim",
            "id": cid,
            "title": title_from(text),
            "description": text,
            "status": "draft",
            "verified": False,
            "generated": True,
            "claim_kind": kind,
            "claim_key": claim_key(text, kind, subject_id),
            "confidence": confidence,
            "as_of": as_of or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "truth_state": "proposed",
            "author": ACTOR,
            "timestamp": now_iso(),
            "tags": ["extracted", kind],
            "links": links,
        },
        f"# Claim\n\n{text}\n",
    )
    return cid


def candidates_from_text(asset_text: str, max_candidates: int = MAX_CANDIDATES) -> list[dict]:
    out = []
    seen = set()
    truncated = False
    for seg in segment_markdown(asset_text):
        body_lines = []
        for line in seg["text"].splitlines():
            if re.match(r"^#{1,6}\s+", line):
                continue
            if HEADING_OR_SECTION.match(line.strip()):
                continue
            body_lines.append(line)
        blob = strip_artifacts(" ".join(body_lines))
        for sent in split_sentences(blob):
            sent = strip_artifacts(sent)
            if not is_claim_sentence(sent):
                continue
            kind = classify_kind(sent)
            if not kind:
                continue
            key = normalize(sent)
            if key in seen:
                continue
            loc = locate_quote(asset_text, sent)
            if not loc:
                continue
            seen.add(key)
            confidence = 0.55
            if not HAS_VERB.search(sent):
                confidence = 0.35
            out.append(
                {
                    "text": sent,
                    "claim_kind": kind,
                    "quote": loc["text"],
                    "span": loc,
                    "confidence": confidence,
                }
            )
            if len(out) >= max_candidates:
                truncated = True
                break
        if truncated:
            break
    return out


def candidates_from_overlay(overlay: dict, asset_text: str) -> tuple[list[dict], list[str]]:
    errors = []
    out = []
    for i, raw in enumerate(overlay.get("claims") or []):
        if not isinstance(raw, dict):
            errors.append(f"overlay.claims[{i}] is not an object")
            continue
        text = (raw.get("text") or "").strip()
        kind = raw.get("claim_kind")
        quote = (raw.get("quote") or text).strip()
        if not text:
            errors.append(f"overlay.claims[{i}] missing text")
            continue
        if kind not in KINDS:
            errors.append(f"overlay.claims[{i}] invalid claim_kind {kind!r}")
            continue
        loc = locate_quote(asset_text, quote)
        if not loc:
            errors.append(f"overlay.claims[{i}] quote not found in asset")
            continue
        links = []
        for rel_name in ("contradicts", "same_as", "supersedes"):
            tgt = raw.get(rel_name)
            if tgt:
                if rel_name not in OWNED_RELS:
                    errors.append(f"overlay.claims[{i}] unknown rel {rel_name}")
                    continue
                if not valid_id(str(tgt)):
                    errors.append(f"overlay.claims[{i}] {rel_name} target not a valid id")
                    continue
                links.append({"rel": rel_name, "target": str(tgt)})
        out.append(
            {
                "text": text,
                "claim_kind": kind,
                "quote": loc["text"],
                "span": loc,
                "confidence": float(raw.get("confidence") or 0.7),
                "as_of": raw.get("as_of"),
                "overlay_links": links,
            }
        )
    return out, errors


def match_existing(cand: dict, subject_id: str, idx: dict) -> tuple[str, dict | None]:
    """Return action, existing claim rec. action: merge|same_as|contradicts|new"""
    ck = claim_key(cand["text"], cand["claim_kind"], subject_id)
    hits = idx["claims_by_key"].get(ck) or []
    if hits:
        return "merge", hits[0]
    cand_tokens = tokens(cand["text"])
    token_index = idx.get("token_index") or {}
    scored: list[tuple[int, dict]] = []
    seen_ids: set[str] = set()
    for tok in cand_tokens:
        for rec in token_index.get(tok, []):
            fm = rec["fm"]
            rid = fm.get("id")
            if not rid or rid in seen_ids:
                continue
            if (fm.get("claim_kind") or cand["claim_kind"]) != cand["claim_kind"]:
                continue
            seen_ids.add(rid)
            other = fm.get("description") or rec.get("body") or ""
            overlap = len(cand_tokens & tokens(other))
            if overlap:
                scored.append((overlap, rec))
    scored.sort(key=lambda row: -row[0])
    best = None
    best_score = 0.0
    for _overlap, rec in scored[:MAX_JACCARD]:
        fm = rec["fm"]
        other = fm.get("description") or rec.get("body") or ""
        score = jaccard(cand["text"], other)
        if score > best_score:
            best_score = score
            best = rec
    if best is None:
        return "new", None
    other = best["fm"].get("description") or best["body"]
    if (
        best_score >= CONTRA_THRESHOLD
        and polarity(cand["text"]) != 0
        and polarity(other) != 0
        and polarity(cand["text"]) != polarity(other)
        and as_of_overlap(cand.get("as_of"), best["fm"].get("as_of"))
    ):
        return "contradicts", best
    if best_score >= SAME_AS_THRESHOLD:
        return "same_as", best
    return "new", None


def run_extract(
    knowledge: Path,
    asset_path: str,
    asset_text: str | None = None,
    subject_id: str | None = None,
    subject_slug: str | None = None,
    vendor: str = "grok",
    source_id: str | None = None,
    task_id: str | None = None,
    overlay: dict | None = None,
    extractor_version: str = EXTRACTOR_VERSION,
    prompt_hash: str = "",
    shard: bool = True,
    dry_run: bool = False,
    as_of: str | None = None,
    idx: dict | None = None,
    session=None,
    max_source_bytes: int = MAX_SOURCE_BYTES,
    max_candidates: int = MAX_CANDIDATES,
    force_large: bool = False,
) -> dict:
    knowledge = Path(knowledge)
    if idx is None:
        idx = index_nodes(knowledge)
    if session is not None:
        session.extract_idx = idx
    errors: list[str] = []
    asset_file = Path(asset_path)
    if not asset_file.is_absolute():
        cand = knowledge / asset_path
        asset_file = cand if cand.exists() else plugin_root() / asset_path
        if not asset_file.exists():
            asset_file = knowledge / asset_path
    if asset_text is None:
        if not asset_file.exists():
            return {"ok": False, "errors": [f"missing asset {asset_path}"]}
        asset_text = asset_file.read_text(encoding="utf-8").replace("\r\n", "\n")
    rel_asset = asset_path
    if str(asset_file).startswith(str(knowledge)):
        rel_asset = str(asset_file.relative_to(knowledge))
    if asset_file.exists():
        source_hash = f"sha256:{hashlib.sha256(asset_file.read_bytes()).hexdigest()}"
        nbytes = asset_file.stat().st_size
    else:
        source_hash = f"sha256:{sha256_text(asset_text)}"
        nbytes = len(asset_text.encode("utf-8"))

    subject_slug = slug(subject_slug or (subject_slug_from_id(subject_id) if subject_id else "unsorted"))
    created_subject = False
    if not subject_id:
        overlay_sid = (overlay or {}).get("subject_id")
        if overlay_sid and valid_id(overlay_sid):
            subject_id = overlay_sid
        else:
            subject_id, created_subject = ensure_subject(
                knowledge, subject_slug, (overlay or {}).get("subject_title"), dry_run, idx
            )

    empty = {
        "ok": True,
        "errors": [],
        "extractor_version": extractor_version,
        "prompt_hash": prompt_hash or "",
        "vendor": vendor,
        "subject_id": subject_id,
        "asset_path": rel_asset,
        "source_hash": source_hash,
        "segments": 0,
        "new_claims": [],
        "merged_claims": [],
        "same_as": [],
        "contradictions": [],
        "skipped_accepted": [],
        "skipped_duplicate_evidence": [],
        "new_evidence": [],
        "new_findings": [],
        "created_subject": subject_id if created_subject else None,
        "pr_summary_path": None,
        "dry_run": dry_run,
        "bytes": nbytes,
    }

    if overlay is None and nbytes > max_source_bytes and not force_large:
        print(
            f"[rkc-extract] skip {rel_asset}: {nbytes} bytes > {max_source_bytes} "
            "(archive-only; pass --force-large to extract)",
            file=sys.stderr,
        )
        empty["skipped"] = "source_too_large"
        empty["ok"] = True
        return empty

    segs = segment_markdown(asset_text)
    if overlay:
        cands, oerr = candidates_from_overlay(overlay, asset_text)
        errors.extend(oerr)
    else:
        cands = candidates_from_text(asset_text, max_candidates=max_candidates)
        if len(cands) >= max_candidates:
            print(
                f"[rkc-extract] capped {rel_asset} at {max_candidates} candidates",
                file=sys.stderr,
            )

    print(
        f"[rkc-extract] {rel_asset} bytes={nbytes} segs={len(segs)} cands={len(cands)}",
        file=sys.stderr,
    )

    if errors:
        return {"ok": False, "errors": errors, "segments": len(segs)}

    summary = {
        **empty,
        "segments": len(segs),
        "capped_candidates": overlay is None and len(cands) >= max_candidates,
    }

    finding_assert_targets: list[str] = []

    for cand in cands:
        cand.setdefault("as_of", as_of or (overlay or {}).get("as_of"))
        action, existing = match_existing(cand, subject_id, idx)
        loc_with_asset = {**cand["span"], "asset_path": rel_asset}

        if action == "merge" and existing:
            claim_id = existing["fm"]["id"]
            if existing_evidence_for(claim_id, loc_with_asset, source_hash, idx):
                summary["skipped_duplicate_evidence"].append(claim_id)
                finding_assert_targets.append(claim_id)
                continue
            evid_id = write_evidence(
                knowledge, subject_slug, cand["span"], rel_asset, source_hash, vendor, shard, dry_run
            )
            summary["new_evidence"].append(evid_id)
            if not dry_run:
                add_link(existing["path"], "evidenced_by", evid_id)
                remember_evidence(idx, evid_id, loc_with_asset, source_hash, cand["span"]["text"])
                existing["fm"].setdefault("links", []).append({"rel": "evidenced_by", "target": evid_id})
            summary["merged_claims"].append(claim_id)
            finding_assert_targets.append(claim_id)
            continue

        extra_links = list(cand.get("overlay_links") or [])
        if action == "same_as" and existing:
            extra_links.append({"rel": "same_as", "target": existing["fm"]["id"]})
        if action == "contradicts" and existing:
            extra_links.append({"rel": "contradicts", "target": existing["fm"]["id"]})

        cleaned = []
        for link in extra_links:
            if link.get("rel") == "supersedes":
                tgt = idx["by_id"].get(link.get("target"))
                if tgt and is_protected(tgt["fm"]):
                    summary["skipped_accepted"].append(link.get("target"))
                    continue
            cleaned.append(link)
        extra_links = cleaned

        evid_id = write_evidence(
            knowledge, subject_slug, cand["span"], rel_asset, source_hash, vendor, shard, dry_run
        )
        extra_links.append({"rel": "evidenced_by", "target": evid_id})
        cid = write_claim(
            knowledge,
            subject_slug,
            subject_id,
            cand["text"],
            cand["claim_kind"],
            vendor,
            cand.get("as_of"),
            cand.get("confidence") or 0.55,
            extra_links,
            shard,
            dry_run,
        )
        summary["new_claims"].append(cid)
        summary["new_evidence"].append(evid_id)
        if action == "same_as" and existing:
            summary["same_as"].append({"new": cid, "of": existing["fm"]["id"]})
        if action == "contradicts" and existing:
            summary["contradictions"].append({"new": cid, "against": existing["fm"]["id"]})
        finding_assert_targets.append(cid)
        if not dry_run:
            remember_evidence(idx, evid_id, loc_with_asset, source_hash, cand["span"]["text"])
            rec = {
                "fm": {
                    "id": cid,
                    "claim_kind": cand["claim_kind"],
                    "description": cand["text"],
                },
                "path": None,
                "body": cand["text"],
            }
            idx["claims_by_key"].setdefault(
                claim_key(cand["text"], cand["claim_kind"], subject_id), []
            ).append(rec)
            idx.setdefault("by_type", {}).setdefault("Claim", []).append(rec)
            idx.setdefault("by_id", {})[cid] = rec
            _index_claim(idx, rec)

    # Finding
    overlay_finding = (overlay or {}).get("finding") if overlay else None
    if finding_assert_targets and (overlay_finding is not None or not overlay):
        fid = make_id("Finding", subject_slug)
        title = None
        body = None
        if isinstance(overlay_finding, dict):
            title = overlay_finding.get("title")
            body = overlay_finding.get("text")
        title = title or title_from(
            f"Extracted finding ({len(finding_assert_targets)} claims) from {Path(rel_asset).name}"
        )
        body = body or "Synthesized from extractor v{v}. Draft. Human PR gate.".format(v=extractor_version)
        links = [{"rel": "asserts", "target": t} for t in dict.fromkeys(finding_assert_targets)]
        qid = (overlay or {}).get("question_id") or (
            ((overlay or {}).get("question") or {}).get("id") if isinstance((overlay or {}).get("question"), dict) else None
        )
        if qid and valid_id(str(qid)):
            links.append({"rel": "answers", "target": str(qid)})
        if not dry_run:
            path = concept_dir(knowledge, "Finding") / f"{fid}.md"
            write_okf(
                path,
                {
                    "type": "Finding",
                    "id": fid,
                    "title": title,
                    "description": body,
                    "status": "draft",
                    "verified": False,
                    "generated": True,
                    "confidence": 0.5,
                    "as_of": as_of or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "truth_state": "proposed",
                    "author": ACTOR,
                    "timestamp": now_iso(),
                    "tags": ["extracted"],
                    "links": links,
                },
                f"# Finding\n\n{body}\n",
            )
            if task_id and task_id in idx["by_id"]:
                add_link(idx["by_id"][task_id]["path"], "produced", fid)
        summary["new_findings"].append(fid)

    summary["pr_summary_path"] = write_pr_summary(knowledge, summary, dry_run)
    return summary


def write_pr_summary(knowledge: Path, summary: dict, dry_run: bool) -> str | None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    digest = (summary.get("source_hash") or "none").split(":")[-1][:12]
    name = f"extract-{digest}-{stamp}.md"
    rel = f"research/catalogs/pr-summaries/{name}"
    lines = [
        f"# Ingest PR summary",
        "",
        f"- extractor_version: {summary.get('extractor_version')}",
        f"- prompt_hash: {summary.get('prompt_hash') or '(none)'}",
        f"- vendor: {summary.get('vendor')}",
        f"- subject: {summary.get('subject_id')}",
        f"- asset: {summary.get('asset_path')}",
        f"- segments: {summary.get('segments')}",
        "",
        "## Counts",
        f"- new_claims: {len(summary.get('new_claims') or [])}",
        f"- merged_claims: {len(summary.get('merged_claims') or [])}",
        f"- same_as: {len(summary.get('same_as') or [])}",
        f"- contradictions: {len(summary.get('contradictions') or [])}",
        f"- skipped_accepted: {len(summary.get('skipped_accepted') or [])}",
        f"- skipped_duplicate_evidence: {len(summary.get('skipped_duplicate_evidence') or [])}",
        f"- new_evidence: {len(summary.get('new_evidence') or [])}",
        f"- new_findings: {len(summary.get('new_findings') or [])}",
        "",
        "## New claims",
    ]
    for cid in summary.get("new_claims") or []:
        lines.append(f"- `{cid}`")
    if not summary.get("new_claims"):
        lines.append("- (none)")
    lines += ["", "## Merged (evidence attached to existing claim)"]
    for cid in summary.get("merged_claims") or []:
        lines.append(f"- `{cid}`")
    if not summary.get("merged_claims"):
        lines.append("- (none)")
    lines += ["", "## Contradictions flagged (new draft → existing)"]
    for row in summary.get("contradictions") or []:
        lines.append(f"- `{row.get('new')}` contradicts `{row.get('against')}`")
    if not summary.get("contradictions"):
        lines.append("- (none)")
    lines += ["", "## Skipped accepted / verified (no auto-supersede)"]
    for cid in summary.get("skipped_accepted") or []:
        lines.append(f"- `{cid}`")
    if not summary.get("skipped_accepted"):
        lines.append("- (none)")
    lines.append("")
    text = "\n".join(lines)
    if dry_run:
        return None
    path = knowledge / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return rel


def load_overlay(path: Path | None) -> dict | None:
    if not path:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_source(knowledge: Path, source_id: str | None, asset: str | None) -> tuple[str, str | None]:
    if source_id:
        for rec in index_nodes(knowledge)["by_type"].get("SourceDocument", []):
            if rec["fm"].get("id") == source_id:
                ap = rec["fm"].get("asset_path")
                return ap, source_id
        raise SystemExit(f"unknown SourceDocument {source_id}")
    if not asset:
        raise SystemExit("provide --asset or --source-id")
    return asset, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--knowledge", type=Path, default=None)
    ap.add_argument("--asset", type=str, default=None)
    ap.add_argument("--source-id", type=str, default=None)
    ap.add_argument("--subject-id", type=str, default=None)
    ap.add_argument("--subject", type=str, default=None)
    ap.add_argument("--task-id", type=str, default=None)
    ap.add_argument("--vendor", default="grok")
    ap.add_argument("--overlay", type=Path, default=None)
    ap.add_argument("--prompt-hash", default="")
    ap.add_argument("--prompt-file", type=Path, default=None)
    ap.add_argument("--extractor-version", default=EXTRACTOR_VERSION)
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--shard", action="store_true", default=True)
    ap.add_argument("--no-shard", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-source-bytes", type=int, default=MAX_SOURCE_BYTES)
    ap.add_argument("--max-candidates", type=int, default=MAX_CANDIDATES)
    ap.add_argument("--force-large", action="store_true")
    args = ap.parse_args()
    kr = knowledge_root(args.knowledge) if args.knowledge else knowledge_root()
    if args.knowledge and (args.knowledge / "research").exists():
        kr = args.knowledge
    prompt_hash = args.prompt_hash
    if args.prompt_file:
        prompt_hash = hashlib.sha256(args.prompt_file.read_bytes()).hexdigest()
    asset, source_id = resolve_source(kr, args.source_id, args.asset)
    overlay = load_overlay(args.overlay)
    summary = run_extract(
        knowledge=kr,
        asset_path=asset,
        subject_id=args.subject_id,
        subject_slug=args.subject,
        vendor=args.vendor,
        source_id=source_id or args.source_id,
        task_id=args.task_id,
        overlay=overlay,
        extractor_version=args.extractor_version,
        prompt_hash=prompt_hash,
        shard=False if args.no_shard else True,
        dry_run=args.dry_run,
        as_of=args.as_of,
        max_source_bytes=args.max_source_bytes,
        max_candidates=args.max_candidates,
        force_large=args.force_large,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
