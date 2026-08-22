#!/usr/bin/env python3
"""Segment a research dump with global line/char locators.

Locators are 1-indexed inclusive line ranges, matching Evidence.locator.
Blank lines are skipped; every nonempty line belongs to exactly one segment.
A single paragraph larger than max_chars is kept intact (no mid-sentence split).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from rkc_claim_key import normalize

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def _line_offsets(lines: list[str]) -> list[int]:
    offsets = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1
    return offsets


def segment_markdown(text: str, max_chars: int = 2000) -> list[dict]:
    text = (text or "").replace("\r\n", "\n")
    lines = text.splitlines()
    offsets = _line_offsets(lines)
    n = len(lines)
    blocks: list[dict] = []
    heading = ""
    i = 0
    while i < n:
        raw = lines[i]
        if not raw.strip():
            i += 1
            continue
        hm = HEADING_RE.match(raw)
        if hm:
            heading = hm.group(2).strip()
            blocks.append(
                {
                    "kind": "heading",
                    "start_line": i + 1,
                    "end_line": i + 1,
                    "heading": heading,
                    "text": raw,
                }
            )
            i += 1
            continue
        j = i + 1
        while j < n and lines[j].strip() and not HEADING_RE.match(lines[j]):
            j += 1
        blocks.append(
            {
                "kind": "para",
                "start_line": i + 1,
                "end_line": j,
                "heading": heading,
                "text": "\n".join(lines[i:j]),
            }
        )
        i = j

    def slice_text(start: int, end: int) -> str:
        return "\n".join(lines[start - 1 : end])

    segs: list[dict] = []
    buf: list[dict] = []

    def flush() -> None:
        if not buf:
            return
        start = buf[0]["start_line"]
        end = buf[-1]["end_line"]
        start_char = offsets[start - 1] if start - 1 < len(offsets) else 0
        end_char = offsets[end - 1] + len(lines[end - 1]) if end - 1 < len(lines) else start_char
        segs.append(
            {
                "index": len(segs),
                "heading": buf[-1].get("heading") or buf[0].get("heading") or "",
                "start_line": start,
                "end_line": end,
                "start_char": start_char,
                "end_char": end_char,
                "text": slice_text(start, end),
            }
        )
        buf.clear()

    for block in blocks:
        if buf:
            start = buf[0]["start_line"]
            if len(slice_text(start, block["end_line"])) > max_chars:
                flush()
        buf.append(block)
    flush()
    return segs


def locate_quote(text: str, quote: str) -> dict | None:
    """Map a quote onto 1-indexed inclusive line range in text.

    Evidence.verbatim compares normalize(joined lines) to normalize(text),
    so the returned `text` is the exact file span (full lines).
    """
    text = (text or "").replace("\r\n", "\n")
    quote = (quote or "").replace("\r\n", "\n").strip()
    if not quote:
        return None
    idx = text.find(quote)
    if idx < 0:
        nq = normalize(quote)
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if normalize(line) == nq:
                start = sum(len(x) + 1 for x in lines[:i])
                return {
                    "start_line": i + 1,
                    "end_line": i + 1,
                    "start_char": start,
                    "end_char": start + len(line),
                    "text": line,
                    "variant": "line_range",
                }
        for width in (2, 3):
            for i in range(0, len(lines) - width + 1):
                span = "\n".join(lines[i : i + width])
                if normalize(span) == nq or nq in normalize(span):
                    if nq in normalize(span):
                        return {
                            "start_line": i + 1,
                            "end_line": i + width,
                            "text": span,
                            "variant": "line_range",
                        }
        return None
    start_line = text[:idx].count("\n") + 1
    end_line = text[: idx + len(quote)].count("\n") + 1
    span = "\n".join(text.splitlines()[start_line - 1 : end_line])
    return {
        "start_line": start_line,
        "end_line": end_line,
        "start_char": idx,
        "end_char": idx + len(quote),
        "text": span,
        "variant": "line_range",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--max-chars", type=int, default=2000)
    args = ap.parse_args()
    text = args.path.read_text(encoding="utf-8")
    segs = segment_markdown(text, args.max_chars)
    print(json.dumps({"path": str(args.path), "segments": segs}, indent=2))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
