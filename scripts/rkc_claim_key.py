#!/usr/bin/env python3
"""Stable claim_key = sha256(normalize(text)|kind|subject_id)"""
from __future__ import annotations
import hashlib, re

def normalize(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"\s+", " ", t).strip()
    t = t.strip(".,;:!?\"'`")
    return t

def claim_key(text: str, claim_kind: str, subject_id: str) -> str:
    raw = f"{normalize(text)}|{claim_kind}|{subject_id}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"claimkey.sha256:{digest}"
