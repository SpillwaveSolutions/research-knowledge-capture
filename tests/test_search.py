#!/usr/bin/env python3
"""Thin rkc_search: AND terms, type filter, limit, json. No Layer 1 index."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

from rkc_search import find_rg, main, search  # noqa: E402

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


FAKE_RG = REPO / "tests" / "fixtures" / "fake_rg.py"
RG_VARS = ("RKC_RG_PATH", "OKF_RG_PATH", "SECOND_BRAIN_RG_PATH")


class SearchEngineParityTests(unittest.TestCase):
    """The rg rung is the production default when ripgrep is present. It must
    return exactly what the scan rung returns, and it must be testable without
    a real ripgrep on PATH."""

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in RG_VARS}
        for k in RG_VARS:
            os.environ.pop(k, None)
        FAKE_RG.chmod(0o755)
        os.environ["RKC_RG_PATH"] = str(FAKE_RG)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_find_rg_honors_override(self):
        self.assertEqual(Path(find_rg()).resolve(), FAKE_RG.resolve())

    def test_find_rg_fails_closed_on_unusable_override(self):
        # Set-but-unusable disables rg; it must not fall through to PATH.
        os.environ["RKC_RG_PATH"] = "/definitely/not/a/real/rg-binary"
        self.assertIsNone(find_rg())

    def test_rg_matches_scan(self):
        # rg prefilters on the first term only; the remaining AND, the type
        # filter, and every score are computed in Python for both rungs.
        for q in ("loop-policy", "false civic alerts", "lumenfield", "detector loop"):
            with self.subTest(q=q):
                scan, scan_engine = search(SAMPLE, q, use_rg=False, limit=25)
                accel, rg_engine = search(SAMPLE, q, use_rg=True, limit=25)
                self.assertEqual((scan_engine, rg_engine), ("scan", "rg"))
                self.assertEqual([h["path"] for h in accel], [h["path"] for h in scan])
                self.assertEqual([h["score"] for h in accel], [h["score"] for h in scan])

    def test_titleless_stem_match_is_invisible_on_both_engines(self):
        # Filenames are not content. A node with no `title` whose filename
        # matched the query used to be a scan hit but never an rg hit.
        tmp = Path(tempfile.mkdtemp())
        d = tmp / "research" / "findings"
        d.mkdir(parents=True)
        (d / "zebra-note.md").write_text(
            "---\ntype: Finding\nid: finding.other.001\ndescription: nothing relevant\nstatus: draft\n---\n\nbody about giraffes\n",
            encoding="utf-8",
        )
        (d / "hit.md").write_text(
            "---\ntype: Finding\nid: finding.other.002\ntitle: Zebra crossing\nstatus: draft\n---\n\nplain\n",
            encoding="utf-8",
        )
        scan, _ = search(tmp, "zebra", use_rg=False)
        accel, engine = search(tmp, "zebra", use_rg=True)
        self.assertEqual(engine, "rg")
        self.assertEqual([h["path"] for h in scan], ["/research/findings/hit.md"])
        self.assertEqual([h["path"] for h in accel], [h["path"] for h in scan])
        self.assertEqual([h["score"] for h in accel], [h["score"] for h in scan])

    def test_symlinked_root_agrees_across_engines(self):
        # Issue #35. rg prints resolved paths. An unresolved root did not
        # match them, so _rel fell through to a full absolute path and the
        # two engines disagreed. /var -> /private/var on macOS does this to
        # every tempfile root; a symlinked checkout or bind mount is the same
        # shape on Linux, which is why CI never saw it.
        real = Path(tempfile.mkdtemp())
        d = real / "research" / "findings"
        d.mkdir(parents=True)
        (d / "hit.md").write_text(
            "---\ntype: Finding\nid: finding.other.003\ntitle: Zebra crossing\nstatus: draft\n---\n\nplain\n",
            encoding="utf-8",
        )
        link = Path(tempfile.mkdtemp()) / "via-symlink"
        link.symlink_to(real, target_is_directory=True)

        scan, _ = search(link, "zebra", use_rg=False)
        accel, engine = search(link, "zebra", use_rg=True)
        self.assertEqual(engine, "rg")
        self.assertEqual([h["path"] for h in scan], ["/research/findings/hit.md"])
        self.assertEqual([h["path"] for h in accel], [h["path"] for h in scan])

    def test_scan_parses_each_file_once(self):
        import rkc_common
        import rkc_search

        calls = {"n": 0}
        real = rkc_common.parse_okf

        def counting(path):
            calls["n"] += 1
            return real(path)

        rkc_common.parse_okf = counting
        rkc_search.parse_okf = counting
        try:
            n_files = sum(1 for _ in rkc_common.iter_okf(SAMPLE))
            calls["n"] = 0
            search(SAMPLE, "loop-policy", use_rg=False)
            self.assertEqual(calls["n"], n_files)
        finally:
            rkc_common.parse_okf = real
            rkc_search.parse_okf = real

if __name__ == "__main__":
    unittest.main()
