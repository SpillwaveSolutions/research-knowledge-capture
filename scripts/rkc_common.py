#!/usr/bin/env python3
"""Shared OKF helpers for Research Knowledge Capture."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

FM_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
ACTOR = "grok-bot/research-knowledge-capture"
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
PROTECTED_STATUS = {"reviewed", "accepted"}
SKIP_DIR_NAMES = {"source-assets", "catalogs", "pr-summaries"}
KEY_ORDER = [
    "type",
    "id",
    "title",
    "description",
    "status",
    "verified",
    "generated",
    "vendor",
    "source_kind",
    "source_hash",
    "asset_path",
    "original_filename",
    "origin_path",
    "captured_at",
    "ingest_version",
    "ingest_key",
    "prompt_hash",
    "claim_kind",
    "claim_key",
    "kind",
    "verbatim",
    "text",
    "locator",
    "confidence",
    "as_of",
    "truth_state",
    "author",
    "timestamp",
    "tags",
    "links",
]
_YAML_FALLBACK_WARNED = False


def plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_registry() -> dict:
    return json.loads((plugin_root() / "schemas/okf-concepts/registry.json").read_text())


def _unescape_double(s: str) -> str:
    """Unescape JSON/YAML double-quoted scalar sequences used by dump_frontmatter."""
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            mapping = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}
            if nxt in mapping:
                out.append(mapping[nxt])
                i += 2
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _scalar(v: str):
    v = v.strip()
    if v in {"true", "True"}:
        return True
    if v in {"false", "False"}:
        return False
    if v in {"null", "None", "~", ""}:
        return None
    if len(v) >= 2 and v[0] == v[-1] and v[0] in {"'", '"'}:
        inner = v[1:-1]
        if v[0] == '"':
            inner = _unescape_double(inner)
        return inner
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
            if isinstance(item, dict):
                stack.append((ind, item))
            continue
        if ":" not in stripped:
            continue
        k, v = stripped.split(":", 1)
        k, v = k.strip(), v.strip()
        if v == "" or v in {"|", ">"}:
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


class ParseError(Exception):
    def __init__(self, path: Path, cause: BaseException):
        self.path = path
        self.cause = cause
        super().__init__(f"{path}: unparsable: {cause}")


def parse_okf(path: Path) -> tuple[dict, str]:
    global _YAML_FALLBACK_WARNED
    text = path.read_text(encoding="utf-8")
    m = FM_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    if yaml:
        data = yaml.safe_load(raw) or {}
    else:
        if not _YAML_FALLBACK_WARNED:
            print(
                "rkc: PyYAML is not installed; using _mini_yaml fallback. "
                "Install with: pip install pyyaml",
                file=sys.stderr,
            )
            _YAML_FALLBACK_WARNED = True
        data = _mini_yaml(raw)
    if not isinstance(data, dict):
        data = {}
    return data, body


def iter_okf(knowledge_root: Path, *, collect_errors: list | None = None):
    research = knowledge_root / "research"
    if not research.exists():
        return
    for p in sorted(research.rglob("*.md")):
        if p.name.lower() in {"index.md", "readme.md"}:
            continue
        if any(part in SKIP_DIR_NAMES for part in p.parts):
            continue
        try:
            fm, body = parse_okf(p)
        except Exception as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            msg = f"{p}: unparsable: {e}"
            if collect_errors is not None:
                collect_errors.append(msg)
                continue
            raise ParseError(p, e) from e
        yield p, fm, body


def iter_type(knowledge: Path, type_name: str):
    """Walk one concept folder. Does not scan claims/evidence when asking for sources."""
    folder = FOLDER_FOR[type_name]
    base = knowledge / "research" / folder
    if not base.exists():
        return
    for p in sorted(base.rglob("*.md")):
        if p.name.lower() in {"index.md", "readme.md"}:
            continue
        try:
            fm, body = parse_okf(p)
        except Exception:
            continue
        if fm.get("type") == type_name:
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


def is_protected(fm: dict) -> bool:
    if fm.get("verified") is True:
        return True
    return (fm.get("status") or "") in PROTECTED_STATUS


def _needs_quote(s: str) -> bool:
    if s == "" or s[0] in " &*!|>%@`'\"" or s.strip() != s:
        return True
    if s.lower() in {"true", "false", "null", "yes", "no", "on", "off"}:
        return True
    if any(c in s for c in "\n#{}[]"):
        return True
    if s.startswith("-") or s.startswith(":"):
        return True
    if ": " in s:
        return True
    if s.rstrip().endswith(":"):
        return True
    return False


def yaml_scalar(v) -> str:
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return "null"
    if isinstance(v, int) and not isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return str(v)
    s = str(v)
    if _needs_quote(s):
        return json.dumps(s, ensure_ascii=False)
    return s


def dump_frontmatter(fm: dict) -> str:
    keys = [k for k in KEY_ORDER if k in fm]
    keys.extend(k for k in fm if k not in keys and not str(k).startswith("_"))
    lines: list[str] = []
    for k in keys:
        v = fm[k]
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
                continue
            if all(isinstance(x, dict) for x in v):
                lines.append(f"{k}:")
                for item in v:
                    first = True
                    for ik, iv in item.items():
                        prefix = "  - " if first else "    "
                        lines.append(f"{prefix}{ik}: {yaml_scalar(iv)}")
                        first = False
            else:
                inner = ", ".join(yaml_scalar(x) for x in v)
                lines.append(f"{k}: [{inner}]")
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for ik, iv in v.items():
                lines.append(f"  {ik}: {yaml_scalar(iv)}")
        else:
            lines.append(f"{k}: {yaml_scalar(v)}")
    return "\n".join(lines)


def write_okf(path: Path, fm: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (body or "").lstrip("\n")
    if body and not body.endswith("\n"):
        body += "\n"
    path.write_text(f"---\n{dump_frontmatter(fm)}\n---\n\n{body}", encoding="utf-8")


def add_link(path: Path, rel: str, target: str) -> bool:
    if rel not in OWNED_RELS:
        raise ValueError(f"unknown rel {rel!r}")
    fm, body = parse_okf(path)
    links = [l for l in (fm.get("links") or []) if isinstance(l, dict)]
    for link in links:
        if link.get("rel") == rel and link.get("target") == target:
            return False
    links.append({"rel": rel, "target": target})
    fm["links"] = links
    write_okf(path, fm, body)
    return True


def concept_dir(knowledge: Path, type_name: str, subject_slug: str | None = None, shard: bool = False) -> Path:
    folder = FOLDER_FOR[type_name]
    base = knowledge / "research" / folder
    if shard and type_name in {"Claim", "Evidence"} and subject_slug:
        return base / subject_slug
    return base


def _title_from_slug(value: str) -> str:
    return (value or "unsorted").replace("-", " ").strip().title() or "Unsorted"


def ensure_subject(knowledge: Path, subject_slug: str, title: str | None = None, *, dry_run: bool = False) -> tuple[str, Path | None, bool]:
    """Return (id, path, created). Path is None on dry-run create."""
    from rkc_ids import make_id, slug as make_slug

    subject_slug = make_slug(subject_slug)
    prefix = f"subject.{subject_slug}."
    for path, fm, _body in iter_type(knowledge, "Subject"):
        if (fm.get("id") or "").startswith(prefix):
            return fm["id"], path, False
    sid = make_id("Subject", subject_slug)
    path = concept_dir(knowledge, "Subject") / f"{sid}.md"
    if dry_run:
        return sid, None, True
    write_okf(
        path,
        {
            "type": "Subject",
            "id": sid,
            "title": title or _title_from_slug(subject_slug),
            "status": "draft",
            "verified": False,
            "generated": True,
            "truth_state": "proposed",
            "author": ACTOR,
            "timestamp": _now_iso(),
            "tags": ["extracted"],
            "links": [],
        },
        f"# {title or _title_from_slug(subject_slug)}\n",
    )
    return sid, path, True


def ensure_area(knowledge: Path, area_slug: str, title: str | None = None, *, dry_run: bool = False) -> tuple[str, Path | None, bool]:
    from rkc_ids import make_id, slug as make_slug

    area_slug = make_slug(area_slug)
    prefix = f"area.{area_slug}."
    for path, fm, _body in iter_type(knowledge, "ResearchArea"):
        if (fm.get("id") or "").startswith(prefix):
            return fm["id"], path, False
    aid = make_id("ResearchArea", area_slug)
    path = concept_dir(knowledge, "ResearchArea") / f"{aid}.md"
    if dry_run:
        return aid, None, True
    write_okf(
        path,
        {
            "type": "ResearchArea",
            "id": aid,
            "title": title or _title_from_slug(area_slug),
            "status": "draft",
            "verified": False,
            "generated": True,
            "truth_state": "proposed",
            "author": ACTOR,
            "timestamp": _now_iso(),
            "tags": ["extracted"],
            "links": [],
        },
        f"# {title or _title_from_slug(area_slug)}\n",
    )
    return aid, path, True


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
