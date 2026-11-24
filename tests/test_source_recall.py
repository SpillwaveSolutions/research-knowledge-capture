"""Exercise search and its source locators on fresh, versioned research."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from rkc_common import iter_okf
from rkc_ingest import ingest_file
from rkc_search import search
from rkc_validate import validate


class SourceRecallTests(unittest.TestCase):
    def test_claim_recall_and_superseding_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "knowledge"

            def capture(label, value, supersedes=None):
                source = root / f"{label}.md"
                fact = f"The {label} relay archives amber samples for {value} evenings."
                source.write_text(f"# {label.title()} retention\n\n{fact}\n", encoding="utf-8")
                claim = {"text": fact, "quote": fact, "claim_kind": "numeric"}
                if supersedes:
                    claim["supersedes"] = supersedes
                result = ingest_file(source, bundle, "claude", "relay-policy", extract=True,
                                     overlay={"claims": [claim], "finding": {"title": f"{label} relay", "text": fact}})
                self.assertTrue(result["extract"]["ok"], result)
                return result["extract"]["new_claims"][0], result["asset_path"], fact

            original = capture("east", 12)
            capture("west", 81)
            for version in ("original", "updated"):
                wanted, archived, fact = original if version == "original" else capture("east", 37, original[0])
                self.assertEqual(validate(bundle), [])
                nodes = {fm["id"]: (path, fm) for path, fm, _ in iter_okf(bundle) if "id" in fm}
                for query in ("east relay", "amber samples east", "east archives evenings"):
                    with self.subTest(query=query, version=version):
                        hits, _ = search(bundle, query, types=["Claim"], limit=3)
                        ids = [row["id"] for row in hits]
                        self.assertIn(wanted, ids, ids)
                        # Search includes historical claims. Follow supersedes edges in the candidates.
                        superseded = {edge["target"] for hit in ids for edge in nodes[hit][1]["links"]
                                      if edge["rel"] == "supersedes"}
                        current = [hit for hit in ids if hit not in superseded]
                        self.assertEqual(current, [wanted])
                        claim = nodes[current[0]][1]
                        evidence_id, = [edge["target"] for edge in claim["links"] if edge["rel"] == "evidenced_by"]
                        evidence = nodes[evidence_id][1]
                        locator = evidence["locator"]
                        self.assertEqual(locator["asset_path"], archived)
                        stored = (bundle / locator["asset_path"]).read_text(encoding="utf-8")
                        self.assertEqual(stored, (root / "east.md").read_text(encoding="utf-8"))
                        lines = stored.splitlines()[locator["start_line"] - 1:locator["end_line"]]
                        self.assertEqual(lines, [fact])
                        self.assertEqual(evidence["text"], fact)
                        self.assertIn(fact, nodes[wanted][0].read_text())
                self.assertEqual(search(bundle, "ultraviolet glacier", limit=3)[0], [])
            self.assertIn("12 evenings", (bundle / original[1]).read_text())


if __name__ == "__main__":
    unittest.main()
