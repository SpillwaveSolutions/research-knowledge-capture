#!/usr/bin/env python3
"""Plugin packaging lockstep across hosts."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VERSION = "0.2.4"
NAME = "research-knowledge-capture"


class PluginPackagingTests(unittest.TestCase):
    def test_manifest_versions_stay_in_lockstep(self) -> None:
        claude = json.loads((REPO / ".claude-plugin/plugin.json").read_text())
        codex = json.loads((REPO / ".codex-plugin/plugin.json").read_text())
        cursor = json.loads((REPO / ".cursor-plugin/plugin.json").read_text())
        root = json.loads((REPO / "plugin.json").read_text())
        claude_market = json.loads((REPO / ".claude-plugin/marketplace.json").read_text())
        grok = json.loads((REPO / ".grok-plugin/marketplace.json").read_text())
        root_market = json.loads((REPO / "marketplace.json").read_text())
        found = {
            claude["version"],
            codex["version"],
            cursor["version"],
            root["version"],
            claude_market["plugins"][0]["version"],
            grok["version"],
            grok["plugins"][0]["version"],
            root_market["plugins"][0]["version"],
        }
        self.assertEqual(found, {VERSION})

    def test_names_match(self) -> None:
        for path in (
            "plugin.json",
            ".claude-plugin/plugin.json",
            ".codex-plugin/plugin.json",
            ".cursor-plugin/plugin.json",
        ):
            data = json.loads((REPO / path).read_text())
            self.assertEqual(data["name"], NAME, path)

    def test_agent_plugins_schema(self) -> None:
        root = json.loads((REPO / "plugin.json").read_text())
        self.assertTrue(root["$schema"].startswith("https://agent-plugins.org/"))

    def test_codex_skills_resolve(self) -> None:
        manifest = json.loads((REPO / ".codex-plugin/plugin.json").read_text())
        self.assertTrue((REPO / manifest["skills"]).is_dir())

    def test_cursor_pointers_resolve(self) -> None:
        manifest = json.loads((REPO / ".cursor-plugin/plugin.json").read_text())
        self.assertTrue((REPO / manifest["skills"]).is_dir())
        self.assertTrue((REPO / manifest["rules"]).is_dir())
        self.assertTrue((REPO / manifest["commands"]).is_dir())

    def test_skill_frontmatter(self) -> None:
        for skill in sorted((REPO / "skills").glob("*/SKILL.md")):
            text = skill.read_text()
            match = re.match(r"^---\n(.*?)\n---", text, re.S)
            self.assertIsNotNone(match, skill)
            block = match.group(1)
            self.assertRegex(block, r"(?m)^name: [a-z0-9-]+$")
            self.assertRegex(block, r"(?m)^description: .+$")


if __name__ == "__main__":
    unittest.main()
