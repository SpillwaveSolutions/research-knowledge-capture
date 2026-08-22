#!/usr/bin/env python3
"""RKC Phase 1 eval: validate, pack spine, claim_key, quote verify, unknown rel."""
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

from rkc_claim_key import claim_key, normalize  # noqa: E402
from rkc_ids import make_id, valid_id  # noqa: E402
from rkc_ingest import ingest_file  # noqa: E402
from rkc_pack import pack  # noqa: E402
from rkc_validate import validate  # noqa: E402

SAMPLE = REPO / "sample-knowledge"
SUBJ = "subject.loop-policy.01J8X000000000000000000001"
QID = "question.loop-policy.01J8X000000000000000000004"
FIND = "finding.loop-policy.01J8X000000000000000000005"
CLM1 = "claim.loop-policy.01J8X000000000000000000006"
EV1 = "evidence.loop-policy.01J8X000000000000000000007"
CLAIM1 = 'The Northstar loop-policy detector recorded a false-alert rate of 1.4% on the autumn 2026 Lumenfield civic corpus.'


class IdTests(unittest.TestCase):
    def test_sample_ids_valid(self):
        for i in (SUBJ, QID, FIND, CLM1, EV1, "area.loop-policy.01J8X000000000000000000000", "task.loop-policy.01J8X000000000000000000002", "source.loop-policy.01J8X000000000000000000003", "source.loop-policy.01J8X00000000000000000000A", "claim.loop-policy.01J8X000000000000000000008", "evidence.loop-policy.01J8X000000000000000000009"):
            self.assertTrue(valid_id(i), i)

    def test_make_id_shape(self):
        i = make_id("Claim", "Loop Policy")
        self.assertTrue(valid_id(i))
        self.assertTrue(i.startswith("claim.loop-policy."))


class ClaimKeyTests(unittest.TestCase):
    def test_stable(self):
        a = claim_key(CLAIM1, "numeric", SUBJ)
        b = claim_key(CLAIM1.upper() + ".", "numeric", SUBJ)
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("claimkey.sha256:"))

    def test_kind_and_subject_split_identity(self):
        a = claim_key(CLAIM1, "numeric", SUBJ)
        b = claim_key(CLAIM1, "causal", SUBJ)
        c = claim_key(CLAIM1, "numeric", "subject.other.01J8X000000000000000000099")
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)

    def test_sample_claim_key_matches(self):
        self.assertEqual(claim_key(CLAIM1, "numeric", SUBJ), "claimkey.sha256:9cfecee3e7765b9d4fb801c5de6ce5b1a2857f8ca3198ea7fe07b1853821bd9f")


class ValidateSampleTests(unittest.TestCase):
    def test_sample_ok(self):
        errs = validate(SAMPLE)
        self.assertEqual(errs, [])


class PackSpineTests(unittest.TestCase):
    def test_subject_pack_reaches_claim_and_evidence(self):
        d = pack(SAMPLE, SUBJ, max_hops=2, max_nodes=20)
        types = {n["type"] for n in d["nodes"]}
        ids = {n["id"] for n in d["nodes"]}
        self.assertIn("Finding", types)
        self.assertIn("Claim", types)
        self.assertIn("Evidence", types)
        self.assertIn(CLM1, ids)
        self.assertIn(EV1, ids)
        self.assertIn(FIND, ids)
        self.assertFalse(d["truncated"])

    def test_question_inbound_answers(self):
        d = pack(SAMPLE, QID, max_hops=2, max_nodes=20)
        ids = {n["id"] for n in d["nodes"]}
        self.assertIn(FIND, ids)
        self.assertIn(CLM1, ids)

    def test_root_always_present(self):
        d = pack(SAMPLE, SUBJ, max_hops=2, max_nodes=3)
        self.assertEqual(d["nodes"][0]["id"], SUBJ)
        self.assertTrue(d["truncated"])

    def test_fail_closed_zero_nodes(self):
        with self.assertRaises(SystemExit):
            pack(SAMPLE, SUBJ, max_hops=2, max_nodes=0)


class FailClosedTests(unittest.TestCase):
    def _copy_sample(self) -> Path:
        tmp = Path(tempfile.mkdtemp())
        shutil.copytree(SAMPLE, tmp / "k")
        return tmp / "k"

    def test_unknown_rel(self):
        k = self._copy_sample()
        p = k / "research" / "subjects" / "subject.loop-policy.01J8X000000000000000000001.md"
        text = p.read_text()
        text = text.replace("  - rel: has_task", "  - rel: owns_topic\n    target: x\n  - rel: has_task")
        p.write_text(text)
        errs = validate(k)
        self.assertTrue(any("unknown rel" in e for e in errs), errs)
        shutil.rmtree(k.parent)

    def test_accepted_claim_needs_evidence(self):
        k = self._copy_sample()
        p = k / "research" / "claims" / "claim.loop-policy.01J8X000000000000000000006.md"
        text = p.read_text()
        text = text.replace("  - rel: evidenced_by\n    target: evidence.loop-policy.01J8X000000000000000000007\n", "")
        p.write_text(text)
        errs = validate(k)
        self.assertTrue(any("evidenced_by" in e for e in errs), errs)
        shutil.rmtree(k.parent)

    def test_verbatim_mismatch(self):
        k = self._copy_sample()
        p = k / "research" / "evidence" / "evidence.loop-policy.01J8X000000000000000000007.md"
        text = p.read_text()
        text = text.replace(CLAIM1, "This quote is not in the asset.")
        p.write_text(text)
        errs = validate(k)
        self.assertTrue(any("verbatim" in e for e in errs), errs)
        shutil.rmtree(k.parent)


class IngestTests(unittest.TestCase):
    def test_idempotent_on_bytes(self):
        tmp = Path(tempfile.mkdtemp())
        inbox = tmp / "dump.md"
        inbox.write_text("# hello from lumenfield\n", encoding="utf-8")
        k = tmp / "knowledge"
        a = ingest_file(inbox, k, "grok", "loop-policy")
        b = ingest_file(inbox, k, "grok", "loop-policy")
        self.assertFalse(a["idempotent"])
        self.assertTrue(b["idempotent"])
        self.assertEqual(a["source_id"], b["source_id"])
        self.assertEqual(a["sha256"], b["sha256"])
        asset = k / "research" / "source-assets" / a["sha256"] / "original.md"
        self.assertTrue(asset.exists())
        shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
