"""Build privacy-safe three-seat, NORMAL/ANTI tournament manifests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .commitment import canonical_commitment


def build_manifest(config: dict[str, Any], seat: str) -> dict[str, Any]:
    if seat not in config["seats"]:
        raise ValueError("seat is not registered")
    views = [item["id"] for item in config["view_bindings"]]
    if views != ["NORMAL", "ANTI"]:
        raise ValueError("exactly ordered NORMAL/ANTI view bindings are required")

    public = deepcopy(config)
    public["active_seat"] = seat
    public["local_matrix"] = "OPAQUE_NONREPLICATED"
    public["vantages"] = [
        {
            "seat": seat,
            "view_binding": view,
            "class": "OPERATOR_SPECIFIED",
        }
        for view in views
    ]
    public["manifest_commitment"] = canonical_commitment(
        "ASOLARIA-TOURNAMENT-MANIFEST-V1", public
    )
    return public
