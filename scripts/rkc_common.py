#!/usr/bin/env python3
"""Shared OKF helpers for Research Knowledge Capture."""
from __future__ import annotations

import json
import re
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

FM_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
OWNED_RELS = {
    "has_subject",
    "related_to",
    "has_task",
    "ingested_from",
    "asks",
    "answers",
    "produced",
    "asserts",
    "evidenced_by",
    "contradicts",
    "supersedes",
    "same_as",
}
OWNED_TYPES = {
    "ResearchArea",
    "Subject",
    "ResearchTask",
    "SourceDocument",
    "ResearchQuestion",
    "Claim",
    "Evidence",
    "Finding",
}
FOLDER_FOR = {
    "ResearchArea": "areas",
    "Subject": "subjects",
    "ResearchTask": "tasks",
    "SourceDocument": "sources",
    "ResearchQuestion": "questions",
    "Claim": "claims",
    "Evidence": "evidence",
    "Finding": "findings",
}


def plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_registry() -> dict:
    return json.loads((plugin_root() / "schemas/okf-concepts/registry.json").read_text())


def _scalar(v: str):
    v = v.strip()
    if v in {"true", "True"}:
        return True
    if v in {"false", "False"}:
        return False
    if v in {"null", "None", "~", ""}:
        return None
    if len(v) >= 2 and v[0] == v[-1] and v[0] in {"'", '"'}:
        return v[1:-1]
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+\.\d+", v):
        return float(v)
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_scalar(p.strip()) for p in inner.split(",")]
    return v


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _mini_yaml(raw: str) -> dict:
    """Subset parser: scalars, nested maps, list-of-maps, inline lists."""
    root: dict = {}
    stack: list[tuple[int, dict | list]] = [(-1, root)]
    pending_list_item: dict | None = None

    def container() -> dict | list:
        return stack[-1][1]

    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.strip().startswith("#"):
            continue
        ind = _indent(line)
        stripped = line.strip()
        while len(stack) > 1 and ind <= stack[-1][0]:
            stack.pop()
        parent = container()
        if stripped.startswith("- "):
            rest = stripped[2:]
            item: dict | str
            if ":" in rest:
                k, v = rest.split(":", 1)
                item = {k.strip(): _scalar(v)} if v.strip() else {k.strip(): {}}
            else:
                item = _scalar(rest)
            if isinstance(parent, list):
                parent.append(item)
            else:
                # should not happen if previous key opened a list
                pass
            if isinstance(item, dict):
                stack.append((ind, item))
            continue
        if ":" not in stripped:
            continue
        k, v = stripped.split(":", 1)
        k, v = k.strip(), v.strip()
        if v == "" or v in {"|", ">"}:
            # peek next non-empty line to decide list vs map
            nxt = None
            for look in lines[i:]:
                if look.strip() and not look.strip().startswith("#"):
                    nxt = look
                    break
            if nxt is not None and nxt.lstrip().startswith("- "):
                new: dict | list = []
            else:
                new = {}
            if isinstance(parent, dict):
                parent[k] = new
            elif isinstance(parent, list) and parent and isinstance(parent[-1], dict):
                parent[-1][k] = new
            stack.append((ind, new))
        else:
            val = _scalar(v)
            if isinstance(parent, dict):
                parent[k] = val
            elif isinstance(parent, list) and parent and isinstance(parent[-1], dict):
                parent[-1][k] = val
    return root


def parse_okf(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    m = FM_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    if yaml:
        data = yaml.safe_load(raw) or {}
    else:
        data = _mini_yaml(raw)
    if not isinstance(data, dict):
        data = {}
    return data, body


def iter_okf(knowledge_root: Path):
    research = knowledge_root / "research"
    if not research.exists():
        return
    for p in sorted(research.rglob("*.md")):
        if p.name.lower() in {"index.md", "readme.md"}:
            continue
        if "source-assets" in p.parts or "catalogs" in p.parts:
            continue
        fm, body = parse_okf(p)
        yield p, fm, body


def knowledge_root(start: Path | None = None) -> Path:
    start = start or Path.cwd()
    for cand in [start, start / "knowledge", plugin_root() / "sample-knowledge"]:
        if (cand / "research").exists():
            return cand
        if cand.name == "knowledge" and cand.exists():
            return cand
    return plugin_root() / "sample-knowledge"


def resolve_asset(root: Path, asset_path: str) -> Path:
    p = Path(asset_path or "")
    candidates = []
    if p.is_absolute():
        candidates.append(p)
    else:
        rel = str(p)
        stripped = rel[len("knowledge/") :] if rel.startswith("knowledge/") else rel
        candidates.extend(
            [
                root / p,
                root / stripped,
                plugin_root() / p,
                plugin_root() / stripped,
                root.parent / p,
            ]
        )
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return candidates[0] if candidates else p
