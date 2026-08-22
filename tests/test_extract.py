#!/usr/bin/env python3
"""Phase 2 extractor: segmentation, claim_key merge, overlay, PR summary."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

from rkc_claim_key import claim_key  # noqa: E402
from rkc_common import is_protected, iter_okf, parse_okf  # noqa: E402
from rkc_extract import run_extract  # noqa: E402
from rkc_ingest import ingest_file  # noqa: E402
from rkc_segment import locate_quote, segment_markdown  # noqa: E402
from rkc_validate import validate  # noqa: E402

SAMPLE = REPO / "sample-knowledge"
FIXTURES = REPO / "tests" / "fixtures"
SUBJ = "subject.loop-policy.01J8X000000000000000000001"
CLM1 = "claim.loop-policy.01J8X000000000000000000006"
CLAIM1 = "The Northstar loop-policy detector recorded a false-alert rate of 1.4% on the autumn 2026 Lumenfield civic corpus."
DUMP1 = SAMPLE / "research/source-assets/3134869d568209bfb387f9a6b8eeada1e0596b64e90460b623fa58e187f77169/original.md"


def _copy_sample() -> Path:
    tmp = Path(tempfile.mkdtemp())
    dest = tmp / "k"
    shutil.copytree(SAMPLE, dest)
    return dest


class SegmentTests(unittest.TestCase):
    def test_nonempty_lines_covered(self):
        text = DUMP1.read_text(encoding="utf-8")
        segs = segment_markdown(text, max_chars=80)
        self.assertGreaterEqual(len(segs), 2)
        covered = set()
        for s in segs:
            for ln in range(s["start_line"], s["end_line"] + 1):
                line = text.splitlines()[ln - 1]
                if line.strip():
                    covered.add(ln)
        nonempty = {i + 1 for i, l in enumerate(text.splitlines()) if l.strip()}
        self.assertEqual(covered, nonempty)

    def test_large_dump_splits(self):
        paras = [f"Paragraph {i} with enough civic loop text to be a block." for i in range(40)]
        text = "# Title\n\n" + "\n\n".join(paras)
        segs = segment_markdown(text, max_chars=120)
        self.assertGreater(len(segs), 5)

    def test_locate_quote_line(self):
        text = DUMP1.read_text(encoding="utf-8")
        loc = locate_quote(text, CLAIM1)
        self.assertIsNotNone(loc)
        self.assertEqual(loc["start_line"], 3)
        self.assertEqual(loc["end_line"], 3)


class MergeTests(unittest.TestCase):
    def test_reextract_same_asset_skips_duplicate_evidence(self):
        k = _copy_sample()
        rel = "research/source-assets/3134869d568209bfb387f9a6b8eeada1e0596b64e90460b623fa58e187f77169/original.md"
        s = run_extract(k, rel, subject_id=SUBJ, subject_slug="loop-policy", vendor="grok", shard=True)
        self.assertTrue(s["ok"], s)
        self.assertIn(CLM1, s["skipped_duplicate_evidence"] + s["merged_claims"])
        self.assertEqual(s["new_claims"], [])
        self.assertEqual(validate(k), [])
        shutil.rmtree(k.parent)

    def test_corroborating_dump_merges_onto_accepted(self):
        k = _copy_sample()
        dump = FIXTURES / "dumps" / "corroborating-1.4.md"
        inbox = k.parent / "in.md"
        shutil.copy2(dump, inbox)
        ing = ingest_file(inbox, k, "grok", "loop-policy")
        s = run_extract(
            k,
            ing["asset_path"],
            subject_id=SUBJ,
            subject_slug="loop-policy",
            vendor="grok",
            source_id=ing["source_id"],
            task_id=ing["task_id"],
        )
        self.assertTrue(s["ok"], s)
        self.assertIn(CLM1, s["merged_claims"])
        self.assertEqual(s["new_claims"], [])
        self.assertTrue(s["new_evidence"])
        fm, _ = parse_okf(k / "research/claims/claim.loop-policy.01J8X000000000000000000006.md")
        self.assertEqual(fm["status"], "accepted")
        self.assertTrue(fm["verified"])
        self.assertTrue(is_protected(fm))
        evid = [l["target"] for l in fm["links"] if l.get("rel") == "evidenced_by"]
        self.assertGreaterEqual(len(evid), 2)
        self.assertTrue(s["pr_summary_path"])
        self.assertTrue((k / s["pr_summary_path"]).exists())
        self.assertEqual(validate(k), [])
        shutil.rmtree(k.parent)

    def test_near_match_same_as(self):
        k = _copy_sample()
        dump = FIXTURES / "dumps" / "near-match-1.4.md"
        dest = k / "research/source-assets/near/original.md"
        dest.parent.mkdir(parents=True)
        shutil.copy2(dump, dest)
        s = run_extract(
            k,
            "research/source-assets/near/original.md",
            subject_id=SUBJ,
            subject_slug="loop-policy",
        )
        self.assertTrue(s["ok"], s)
        self.assertTrue(s["same_as"] or s["merged_claims"], s)
        if s["same_as"]:
            self.assertEqual(s["same_as"][0]["of"], CLM1)
            new_id = s["same_as"][0]["new"]
            rec = next(fm for p, fm, b in iter_okf(k) if fm.get("id") == new_id)
            self.assertEqual(rec["status"], "draft")
            rels = {l.get("rel") for l in rec.get("links") or []}
            self.assertIn("same_as", rels)
        self.assertEqual(validate(k), [])
        shutil.rmtree(k.parent)


class OverlayTests(unittest.TestCase):
    def test_overlay_writes_and_validates(self):
        k = _copy_sample()
        dump = FIXTURES / "dumps" / "spring-recal.md"
        dest = k / "research/source-assets/spring/original.md"
        dest.parent.mkdir(parents=True)
        shutil.copy2(dump, dest)
        overlay = json.loads((FIXTURES / "overlays/good-spring.json").read_text())
        s = run_extract(
            k,
            "research/source-assets/spring/original.md",
            subject_id=SUBJ,
            overlay=overlay,
        )
        self.assertTrue(s["ok"], s)
        self.assertEqual(len(s["new_claims"]), 1)
        self.assertEqual(len(s["new_findings"]), 1)
        self.assertEqual(validate(k), [])
        shutil.rmtree(k.parent)

    def test_bad_quote_writes_nothing(self):
        k = _copy_sample()
        before = {p.relative_to(k) for p, _, _ in iter_okf(k)}
        overlay = json.loads((FIXTURES / "overlays/bad-quote.json").read_text())
        rel = "research/source-assets/3134869d568209bfb387f9a6b8eeada1e0596b64e90460b623fa58e187f77169/original.md"
        s = run_extract(k, rel, subject_id=SUBJ, overlay=overlay)
        self.assertFalse(s["ok"])
        self.assertTrue(any("quote" in e for e in s["errors"]))
        after = {p.relative_to(k) for p, _, _ in iter_okf(k)}
        self.assertEqual(before, after)
        shutil.rmtree(k.parent)

    def test_supersede_accepted_is_skipped(self):
        k = _copy_sample()
        dump = FIXTURES / "dumps" / "spring-recal.md"
        dest = k / "research/source-assets/spring/original.md"
        dest.parent.mkdir(parents=True)
        shutil.copy2(dump, dest)
        overlay = json.loads((FIXTURES / "overlays/supersede-accepted.json").read_text())
        s = run_extract(
            k,
            "research/source-assets/spring/original.md",
            subject_id=SUBJ,
            overlay=overlay,
        )
        self.assertTrue(s["ok"], s)
        self.assertIn(CLM1, s["skipped_accepted"])
        new_id = s["new_claims"][0]
        rec = next(fm for p, fm, b in iter_okf(k) if fm.get("id") == new_id)
        rels = {l.get("rel") for l in rec.get("links") or []}
        self.assertNotIn("supersedes", rels)
        fm, _ = parse_okf(k / "research/claims/claim.loop-policy.01J8X000000000000000000006.md")
        self.assertEqual(fm["status"], "accepted")
        self.assertEqual(validate(k), [])
        shutil.rmtree(k.parent)


class HeuristicAndPrTests(unittest.TestCase):
    def test_spring_heuristic_kinds(self):
        k = _copy_sample()
        dump = FIXTURES / "dumps" / "spring-recal.md"
        dest = k / "research/source-assets/spring/original.md"
        dest.parent.mkdir(parents=True)
        shutil.copy2(dump, dest)
        s = run_extract(
            k,
            "research/source-assets/spring/original.md",
            subject_id=SUBJ,
            subject_slug="loop-policy",
        )
        self.assertTrue(s["ok"], s)
        self.assertGreaterEqual(len(s["new_claims"]), 3)
        kinds = set()
        for cid in s["new_claims"]:
            rec = next(fm for p, fm, b in iter_okf(k) if fm.get("id") == cid)
            kinds.add(rec.get("claim_kind"))
            self.assertEqual(rec.get("status"), "draft")
            self.assertTrue(rec.get("claim_key", "").startswith("claimkey.sha256:"))
        self.assertTrue({"numeric", "predictive", "definitional"} <= kinds, kinds)
        summary = (k / s["pr_summary_path"]).read_text()
        self.assertIn("new_claims:", summary)
        self.assertIn("skipped_accepted:", summary)
        self.assertEqual(validate(k), [])
        shutil.rmtree(k.parent)

    def test_dry_run_writes_nothing(self):
        k = _copy_sample()
        before = sorted(p.relative_to(k) for p in k.rglob("*") if p.is_file())
        dump = FIXTURES / "dumps" / "spring-recal.md"
        dest = k / "research/source-assets/spring/original.md"
        dest.parent.mkdir(parents=True)
        shutil.copy2(dump, dest)
        after_asset = sorted(p.relative_to(k) for p in k.rglob("*") if p.is_file())
        s = run_extract(
            k,
            "research/source-assets/spring/original.md",
            subject_id=SUBJ,
            dry_run=True,
        )
        self.assertTrue(s["ok"], s)
        self.assertTrue(s["new_claims"])
        self.assertIsNone(s["pr_summary_path"])
        now = sorted(p.relative_to(k) for p in k.rglob("*") if p.is_file())
        self.assertEqual(now, after_asset)
        shutil.rmtree(k.parent)

    def test_claim_key_stable_on_extracted_text(self):
        self.assertEqual(
            claim_key(CLAIM1, "numeric", SUBJ),
            "claimkey.sha256:9cfecee3e7765b9d4fb801c5de6ce5b1a2857f8ca3198ea7fe07b1853821bd9f",
        )


class IngestExtractTests(unittest.TestCase):
    def test_ingest_extract_empty_knowledge(self):
        tmp = Path(tempfile.mkdtemp())
        k = tmp / "knowledge"
        dump = FIXTURES / "dumps" / "spring-recal.md"
        inbox = tmp / "spring.md"
        shutil.copy2(dump, inbox)
        result = ingest_file(
            inbox,
            k,
            "claude",
            "loop-policy",
            extractor_version="2",
            extract=True,
            shard=True,
        )
        self.assertFalse(result["idempotent"])
        ext = result["extract"]
        self.assertTrue(ext["ok"], ext)
        self.assertTrue(ext["new_claims"])
        self.assertTrue(ext["created_subject"] or ext["subject_id"])
        self.assertEqual(validate(k), [])
        again = ingest_file(inbox, k, "claude", "loop-policy", extractor_version="2")
        self.assertTrue(again["idempotent"])
        self.assertEqual(again["source_id"], result["source_id"])
        shutil.rmtree(tmp)

    def test_prompt_hash_splits_idempotency(self):
        tmp = Path(tempfile.mkdtemp())
        k = tmp / "knowledge"
        inbox = tmp / "d.md"
        inbox.write_text("# hello from lumenfield civic loop\n", encoding="utf-8")
        a = ingest_file(inbox, k, "grok", "loop-policy", prompt_hash="")
        b = ingest_file(inbox, k, "grok", "loop-policy", prompt_hash="abc")
        self.assertFalse(b["idempotent"])
        self.assertNotEqual(a["source_id"], b["source_id"])
        shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
