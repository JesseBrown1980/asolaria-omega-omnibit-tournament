"""Build privacy-safe three-seat, two-field tournament manifests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .commitment import canonical_commitment


def build_manifest(config: dict[str, Any], seat: str) -> dict[str, Any]:
    if seat not in config["seats"]:
        raise ValueError("seat is not registered")
    fields = [item["id"] for item in config["reflection_fields"]]
    if fields != ["A", "B"]:
        raise ValueError("exactly ordered reflection fields A/B are required")

    public = deepcopy(config)
    public["active_seat"] = seat
    public["local_matrix"] = "OPAQUE_NONREPLICATED"
    public["vantages"] = [
        {
            "seat": seat,
            "reflection_field": field,
            "normal_anti_binding": "UNRESOLVED",
        }
        for field in fields
    ]
    public["manifest_commitment"] = canonical_commitment(
        "ASOLARIA-TOURNAMENT-MANIFEST-V1", public
    )
    return public
