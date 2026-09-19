#!/usr/bin/env python3
"""Minimal `rg -l` stand-in for tests. Not a real ripgrep.

Understands:
  -l / --files-with-matches
  -i / --ignore-case
  -F / --fixed-strings
  --glob GLOB (including !negations)
  --no-messages --color never
  pattern PATH
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import sys
from pathlib import Path


def match_globs(rel: str, globs: list[str]) -> bool:
    include = [g for g in globs if not g.startswith("!")]
    exclude = [g[1:] for g in globs if g.startswith("!")]
    ok = True
    if include:
        ok = any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(Path(rel).name, g) for g in include)
    for g in exclude:
        if fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(Path(rel).name, g):
            return False
    return ok


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("-l", "--files-with-matches", action="store_true")
    p.add_argument("-i", "--ignore-case", action="store_true")
    p.add_argument("-F", "--fixed-strings", action="store_true")
    p.add_argument("--glob", action="append", default=[])
    p.add_argument("--no-messages", action="store_true")
    p.add_argument("--color", default="never")
    p.add_argument("pattern")
    p.add_argument("path", nargs="?", default=".")
    args = p.parse_args(argv)

    root = Path(args.path).resolve()
    flags = re.I if args.ignore_case else 0
    if args.fixed_strings:
        needle = args.pattern.lower() if args.ignore_case else args.pattern
        pred = lambda text: needle in (text.lower() if args.ignore_case else text)
    else:
        try:
            rx = re.compile(args.pattern, flags)
        except re.error:
            return 2
        pred = lambda text: rx.search(text) is not None

    hits = 0
    if root.is_file():
        files = [root]
        base = root.parent
    else:
        files = sorted(root.rglob("*"))
        base = root
    for path in files:
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(base).as_posix()
        except ValueError:
            rel = path.name
        if args.glob and not match_globs(rel, args.glob):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if pred(text):
            print(path)
            hits += 1
    return 0 if hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
