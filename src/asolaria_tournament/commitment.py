"""Deterministic domain-separated commitments."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def canonical_commitment(domain: str, value: Any) -> str:
    if not domain or not domain.isascii():
        raise ValueError("domain must be non-empty ASCII")
    body = canonical_bytes(value)
    framed = (
        b"ASOLARIA-COMMITMENT-V1\x00"
        + len(domain).to_bytes(4, "big")
        + domain.encode("ascii")
        + len(body).to_bytes(8, "big")
        + body
    )
    return hashlib.sha256(framed).hexdigest()
