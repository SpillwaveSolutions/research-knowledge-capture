#!/usr/bin/env python3
"""Spine repair: Subjects, has_task, ResearchArea, has_subject."""
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

from rkc_common import parse_okf  # noqa: E402
from rkc_ingest import ingest_file  # noqa: E402
from rkc_spine import apply_areas, link_tasks, list_subjects  # noqa: E402
from rkc_validate import spine_issues, validate  # noqa: E402

SAMPLE = REPO / "sample-knowledge"


class SpineRepairTests(unittest.TestCase):
    def test_link_tasks_creates_subject_and_is_idempotent(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            k = tmp / "knowledge"
            a = tmp / "articles" / "post-one" / "index.md"
            b = tmp / "articles" / "post-two" / "index.md"
            a.parent.mkdir(parents=True)
            b.parent.mkdir(parents=True)
            a.write_text("# one\n", encoding="utf-8")
            b.write_text("# two\n", encoding="utf-8")
            ingest_file(a, k, "article", "published-medium", source_kind="published_medium")
            ingest_file(b, k, "article", "published-medium", source_kind="published_medium")
            # 0.2.1 ingest already writes the spine; strip has_task to simulate 0.2.0.
            for p in (k / "research" / "subjects").glob("*.md"):
                fm, body = parse_okf(p)
                fm["links"] = []
                from rkc_common import write_okf

                write_okf(p, fm, body)
            first = link_tasks(k, dry_run=False)
            self.assertGreaterEqual(first["has_task_written"], 2)
            second = link_tasks(k, dry_run=False)
            self.assertEqual(second["has_task_written"], 0)
            self.assertEqual(validate(k), [])
        finally:
            shutil.rmtree(tmp)

    def test_area_map_prefixes(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            k = tmp / "knowledge"
            inbox = tmp / "d.md"
            inbox.write_text("# hello from lumenfield civic loop\n", encoding="utf-8")
            ingest_file(inbox, k, "grok", "ref-claude-api", area=None)
            spec = [
                {
                    "slug": "claude-platform",
                    "title": "Claude platform",
                    "subjects": [],
                    "prefixes": ["ref-claude"],
                }
            ]
            result = apply_areas(k, spec, dry_run=False, default_area=None)
            self.assertEqual(result["created_areas"], 1)
            self.assertEqual(result["has_subject_written"], 1)
            self.assertEqual(spine_issues(k), [])
            self.assertEqual(validate(k), [])
        finally:
            shutil.rmtree(tmp)

    def test_list_subjects_flags_missing(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            k = tmp / "knowledge"
            inbox = tmp / "d.md"
            inbox.write_text("# hello from lumenfield\n", encoding="utf-8")
            ingest_file(inbox, k, "grok", "loop-policy")
            rows = list_subjects(k)
            slugs = {r["slug"] for r in rows}
            self.assertIn("loop-policy", slugs)
        finally:
            shutil.rmtree(tmp)

    def test_sample_already_spined(self):
        result = link_tasks(SAMPLE, dry_run=True)
        self.assertEqual(result["created_subjects"], 0)
        issues = spine_issues(SAMPLE)
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
