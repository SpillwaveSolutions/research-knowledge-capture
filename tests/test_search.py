#!/usr/bin/env python3
"""Thin rkc_search: AND terms, type filter, limit, json. No Layer 1 index."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

from rkc_search import main, search  # noqa: E402

SAMPLE = REPO / "sample-knowledge"
FIND = "finding.loop-policy.01J8X000000000000000000005"
QID = "question.loop-policy.01J8X000000000000000000004"
SUBJ = "subject.loop-policy.01J8X000000000000000000001"


class SearchUnitTests(unittest.TestCase):
    def test_and_terms_hit_finding(self):
        results, engine = search(SAMPLE, "false civic alerts", use_rg=False, limit=5)
        self.assertEqual(engine, "scan")
        ids = {r["id"] for r in results}
        self.assertIn(FIND, ids)
        self.assertTrue(all(r["score"] > 0 for r in results))

    def test_type_filter_finding_only(self):
        results, _engine = search(
            SAMPLE, "lumenfield", types=["Finding"], use_rg=False, limit=5
        )
        self.assertTrue(results)
        self.assertTrue(all(r["type"] == "Finding" for r in results))

    def test_prefers_finding_seed_type(self):
        results, _engine = search(SAMPLE, "false civic alerts", use_rg=False, limit=5)
        types = [r["type"] for r in results]
        self.assertIn("Finding", types)
        self.assertEqual(results[0]["type"], "Finding")

    def test_limit(self):
        results, _engine = search(SAMPLE, "lumenfield", use_rg=False, limit=2)
        self.assertLessEqual(len(results), 2)

    def test_empty_query(self):
        results, engine = search(SAMPLE, "   ", use_rg=False)
        self.assertEqual(results, [])
        self.assertEqual(engine, "scan")

    def test_unknown_terms(self):
        results, _engine = search(SAMPLE, "xyzzy-no-such-token", use_rg=False)
        self.assertEqual(results, [])

    def test_rejects_pkc_question_type(self):
        results, _engine = search(
            SAMPLE, "false-alert", types=["Question"], use_rg=False
        )
        self.assertEqual(results, [])


class SearchCliTests(unittest.TestCase):
    def test_json_shape(self):
        rc = main(
            [
                "false-alert",
                "--root",
                str(SAMPLE),
                "--engine",
                "scan",
                "--limit",
                "5",
                "--json",
            ]
        )
        self.assertEqual(rc, 0)

    def test_json_payload(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "rkc_search.py"),
                "false civic alerts",
                "--root",
                str(SAMPLE),
                "--engine",
                "scan",
                "--type",
                "ResearchQuestion,Finding",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["query"], "false civic alerts")
        self.assertEqual(data["engine"], "scan")
        self.assertLessEqual(data["count"], 5)
        types = {r["type"] for r in data["results"]}
        self.assertTrue(types <= {"ResearchQuestion", "Finding"})
        self.assertTrue({QID, FIND} & {r["id"] for r in data["results"]})

    def test_rejects_question_alias(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "rkc_search.py"),
                "loop-policy",
                "--root",
                str(SAMPLE),
                "--type",
                "Question",
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("ResearchQuestion", proc.stderr)

    def test_pack_summary_cli(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "rkc_pack.py"),
                SUBJ,
                "--root",
                str(SAMPLE),
                "--summary",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("## Pack summary", proc.stdout)
        self.assertIn("hops=2", proc.stdout)
        self.assertIn("Finding=", proc.stdout)
        self.assertNotIn('"packer_version"', proc.stdout)


class SearchIsolationTests(unittest.TestCase):
    def test_does_not_write(self):
        tmp = Path(tempfile.mkdtemp())
        # search is read-only; a missing tree just yields no hits
        results, _engine = search(tmp, "loop-policy", use_rg=False)
        self.assertEqual(results, [])
        self.assertEqual(list(tmp.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
