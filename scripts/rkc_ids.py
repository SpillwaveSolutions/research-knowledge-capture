#!/usr/bin/env python3
"""RKC ID convention: <type-slug>.<subject-slug>.<ulid>"""
from __future__ import annotations
import re, time, os

TYPE_SLUGS = {
    "ResearchArea": "area",
    "Subject": "subject",
    "ResearchTask": "task",
    "SourceDocument": "source",
    "ResearchQuestion": "question",
    "Claim": "claim",
    "Evidence": "evidence",
    "Finding": "finding",
}

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
ID_RE = re.compile(
    r"^(area|subject|task|source|question|claim|evidence|finding)\.[a-z0-9-]{1,64}\.[0-9A-HJKMNP-TV-Z]{26}$"
)


def _encode(n: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(CROCKFORD[n & 31])
        n >>= 5
    return "".join(reversed(chars))


def ulid() -> str:
    ms = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")
    return _encode(ms, 10) + _encode(rand, 16)


def slug(s: str) -> str:
    s = (s or "unsorted").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:64] or "unsorted"


def subject_slug_from_id(value: str) -> str:
    parts = (value or "").split(".")
    if len(parts) >= 3:
        return parts[1]
    return slug(value)


def make_id(type_name: str, subject_slug: str) -> str:
    ts = TYPE_SLUGS[type_name]
    return f"{ts}.{slug(subject_slug)}.{ulid()}"


def valid_id(value: str) -> bool:
    return bool(value and ID_RE.match(value) and len(value) <= 128)
