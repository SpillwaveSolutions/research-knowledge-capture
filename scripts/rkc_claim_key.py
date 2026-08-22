#!/usr/bin/env python3
"""Stable claim_key = sha256(normalize(text)|kind|subject_id)"""
from __future__ import annotations
import hashlib, re

STOP = {
    "the", "a", "an", "of", "on", "in", "to", "and", "or", "for",
    "is", "are", "was", "were", "from", "with", "by", "that", "this",
    "as", "at", "it", "be",
}

NEG_RE = re.compile(r"\b(not|never|no|none|false|decrease|drop|below|reduce|fewer|less|against)\b")
POS_RE = re.compile(r"\b(increase|rise|above|more|higher|true|grow|grew)\b")


def normalize(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"\s+", " ", t).strip()
    t = t.strip(".,;:!?\"'`")
    return t


def claim_key(text: str, claim_kind: str, subject_id: str) -> str:
    raw = f"{normalize(text)}|{claim_kind}|{subject_id}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"claimkey.sha256:{digest}"


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", normalize(text)) if t not in STOP}


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def polarity(text: str) -> int:
    t = normalize(text)
    n = len(NEG_RE.findall(t))
    p = len(POS_RE.findall(t))
    if n > p:
        return -1
    if p > n:
        return 1
    return 0
