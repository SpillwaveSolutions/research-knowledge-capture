#!/usr/bin/env python3
"""Bulk-ingest defects: slugs, YAML, catalog, spine, extractor caps."""
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

from rkc_common import (  # noqa: E402
    _mini_yaml,
    _needs_quote,
    dump_frontmatter,
    parse_okf,
)
from rkc_extract import candidates_from_text, is_claim_sentence, run_extract  # noqa: E402
from rkc_ids import slug, valid_id  # noqa: E402
from rkc_ingest import IngestSession, ingest_file, source_title  # noqa: E402
from rkc_validate import spine_issues, validate  # noqa: E402


class SlugTests(unittest.TestCase):
    def test_short_unchanged(self):
        self.assertEqual(slug("Loop Policy"), "loop-policy")

    def test_long_inputs_do_not_collide(self):
        a = "ref-cowork-plugins-knowledge-work-partner-built-zoom-plugin-skills-video-sdk"
        b = "ref-cowork-plugins-knowledge-work-partner-built-zoom-plugin-skills-meeting-sdk"
        sa, sb = slug(a), slug(b)
        self.assertNotEqual(sa, sb)
        self.assertLessEqual(len(sa), 64)
        self.assertLessEqual(len(sb), 64)
        self.assertTrue(valid_id(f"subject.{sa}.01J8X000000000000000000001"))


class YamlTests(unittest.TestCase):
    def test_trailing_colon_needs_quote(self):
        self.assertTrue(_needs_quote("Everything powerful is available in the SDK:"))
        self.assertFalse(_needs_quote("plain title"))

    def test_dump_roundtrip_trailing_colon(self):
        dumped = dump_frontmatter({"title": "available in the SDK:"})
        self.assertIn('"available in the SDK:"', dumped)

    def test_mini_yaml_unescapes_newlines(self):
        raw = 'text: "line one\\nline two"\n'
        data = _mini_yaml(raw)
        self.assertEqual(data["text"], "line one\nline two")


class ProvenanceTests(unittest.TestCase):
    def test_index_md_uses_parent_name(self):
        self.assertEqual(source_title(Path("/articles/medium_published/my-post/index.md")), "my-post")
        self.assertEqual(source_title(Path("/inbox/dump.md")), "dump.md")

    def test_ingest_writes_origin_and_subject(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            k = tmp / "knowledge"
            article = tmp / "articles" / "why-harness-engineering" / "index.md"
            article.parent.mkdir(parents=True)
            article.write_text("# Why harness engineering is defined as a discipline.\n", encoding="utf-8")
            rec = ingest_file(article, k, "article", "harness-engineering", source_kind="published_medium")
            src = k / "research" / "sources" / f"{rec['source_id']}.md"
            fm, _ = parse_okf(src)
            self.assertEqual(fm["title"], "why-harness-engineering")
            self.assertEqual(fm["original_filename"], "index.md")
            self.assertEqual(fm["origin_path"], str(article.resolve()))
            self.assertEqual(fm["source_kind"], "published_medium")
            self.assertTrue(rec["subject_id"])
            subjects = list((k / "research" / "subjects").glob("*.md"))
            self.assertEqual(len(subjects), 1)
            s_fm, _ = parse_okf(subjects[0])
            self.assertEqual(s_fm["type"], "Subject")
            targets = [l["target"] for l in s_fm.get("links") or [] if l.get("rel") == "has_task"]
            self.assertEqual(targets, [rec["task_id"]])
        finally:
            shutil.rmtree(tmp)

    def test_area_writes_has_subject(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            k = tmp / "knowledge"
            inbox = tmp / "d.md"
            inbox.write_text("# hello from lumenfield civic loop\n", encoding="utf-8")
            rec = ingest_file(inbox, k, "grok", "loop-policy", area="civic-governance")
            self.assertTrue(rec["area_id"])
            areas = list((k / "research" / "areas").glob("*.md"))
            self.assertEqual(len(areas), 1)
            fm, _ = parse_okf(areas[0])
            targets = [l["target"] for l in fm.get("links") or [] if l.get("rel") == "has_subject"]
            self.assertEqual(targets, [rec["subject_id"]])
            self.assertEqual(spine_issues(k), [])
        finally:
            shutil.rmtree(tmp)

    def test_ingest_index_makes_second_call_idempotent(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            k = tmp / "knowledge"
            inbox = tmp / "d.md"
            inbox.write_text("# hello from lumenfield\n", encoding="utf-8")
            a = ingest_file(inbox, k, "grok", "loop-policy")
            idx = k / "research" / "catalogs" / "ingest-index.json"
            self.assertTrue(idx.exists())
            data = json.loads(idx.read_text())
            self.assertIn(a["ingest_key"], data["keys"])
            b = ingest_file(inbox, k, "grok", "loop-policy")
            self.assertTrue(b["idempotent"])
            self.assertEqual(a["source_id"], b["source_id"])
        finally:
            shutil.rmtree(tmp)


class ValidateParseTests(unittest.TestCase):
    def test_names_unparsable_file(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            k = tmp / "knowledge"
            (k / "research" / "subjects").mkdir(parents=True)
            bad = k / "research" / "subjects" / "broken.md"
            bad.write_text(
                "---\ntype: Subject\nid: subject.loop-policy.01J8X000000000000000000001\n"
                "title: Everything powerful is available in the SDK:\n---\n\n# x\n",
                encoding="utf-8",
            )
            # Force PyYAML path if present: unquoted trailing colon is invalid.
            try:
                import yaml  # noqa: F401
            except ImportError:
                self.skipTest("PyYAML not installed")
            errs = validate(k)
            self.assertTrue(any("unparsable" in e and "broken.md" in e for e in errs), errs)
        finally:
            shutil.rmtree(tmp)


class ExtractorHygieneTests(unittest.TestCase):
    def test_skips_headings_and_export_artifacts(self):
        text = (
            "# Title\n\n"
            "3.11 Workflow pattern 3: parallelization (sectioning and voting) is a heading\n\n"
            "Agents are harder to debug because the execution path is not deterministic in production.\n\n"
            "OpenAI guidance recommends identity fileciteturn0file0 citeturn10view1 and examples in context.\n"
        )
        self.assertFalse(is_claim_sentence("3.11 Workflow pattern 3: parallelization (sectioning and voting)"))
        cands = candidates_from_text(text)
        joined = " ".join(c["text"] for c in cands)
        self.assertNotIn("3.11", joined)
        self.assertNotIn("filecite", joined)
        self.assertTrue(any("harder to debug" in c["text"] for c in cands), cands)

    def test_large_file_skips_extract(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            k = tmp / "knowledge"
            blob = tmp / "huge.md"
            # Enough bytes, few claim-like sentences.
            body = "# Dump\n\n" + ("word " * 50 + "is defined as filler.\n") * 20
            blob.write_text(body, encoding="utf-8")
            rec = ingest_file(
                blob,
                k,
                "grok",
                "api-ref",
                extract=True,
                extractor_version="2",
                max_source_bytes=200,
            )
            ext = rec["extract"]
            self.assertTrue(ext["ok"], ext)
            self.assertEqual(ext.get("skipped"), "source_too_large")
            self.assertEqual(ext.get("new_claims"), [])
            claims = list((k / "research" / "claims").rglob("*.md"))
            self.assertEqual(claims, [])
        finally:
            shutil.rmtree(tmp)

    def test_force_large_extracts(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            k = tmp / "knowledge"
            blob = tmp / "ok.md"
            blob.write_text(
                "Loop policy is defined as the civic threshold that gates dusk-window alerts.\n",
                encoding="utf-8",
            )
            rec = ingest_file(
                blob,
                k,
                "grok",
                "loop-policy",
                extract=True,
                extractor_version="2",
                max_source_bytes=10,
                force_large=True,
            )
            self.assertTrue(rec["extract"]["ok"], rec["extract"])
            self.assertNotEqual(rec["extract"].get("skipped"), "source_too_large")
            self.assertTrue(rec["extract"]["new_claims"])
        finally:
            shutil.rmtree(tmp)


class CatalogRebuildTests(unittest.TestCase):
    def test_rebuild_from_sources_only(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            k = tmp / "knowledge"
            inbox = tmp / "d.md"
            inbox.write_text("# hello from lumenfield\n", encoding="utf-8")
            rec = ingest_file(inbox, k, "grok", "loop-policy")
            idx = k / "research" / "catalogs" / "ingest-index.json"
            idx.unlink()
            sess = IngestSession(k, rebuild=True)
            found = sess.find(rec["ingest_key"])
            self.assertIsNotNone(found)
            self.assertEqual(found["source_id"], rec["source_id"])
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
