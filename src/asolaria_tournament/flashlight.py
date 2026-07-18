"""Privacy-safe adapter for the movable mathematical flashlight."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .commitment import canonical_commitment

ALLOWED_FIELDS = frozenset({"A", "B"})
ALLOWED_SIGNS = frozenset({-1, 1})
REFERENCE_RUNGS = frozenset({2, 4, 8, 16, 32, 64, 256, 1024, 4096})


@dataclass(frozen=True)
class FlashlightProbe:
    seat: str
    reflection_field: str
    direction_port: int
    traversal_sign: int
    rung: int
    pid: str
    slice_commitment: str
    omega_binding: str

    def validate(self) -> None:
        if self.seat not in {"acer", "liris", "relic"}:
            raise ValueError("unknown seat")
        if self.reflection_field not in ALLOWED_FIELDS:
            raise ValueError("reflection field must be A or B")
        if not 0 <= self.direction_port < 8:
            raise ValueError("direction port must be in [0, 7]")
        if self.traversal_sign not in ALLOWED_SIGNS:
            raise ValueError("traversal sign must be -1 or +1")
        if self.rung not in REFERENCE_RUNGS:
            raise ValueError("unregistered rung")
        for label, value in (
            ("pid", self.pid),
            ("slice_commitment", self.slice_commitment),
            ("omega_binding", self.omega_binding),
        ):
            if not value or not value.isascii():
                raise ValueError(f"{label} must be non-empty ASCII")


def move_probe(probe: FlashlightProbe) -> dict[str, object]:
    """Move a public probe without reading or returning a local slice."""
    probe.validate()
    public = asdict(probe)
    return {
        "schema": "ASOLARIA-MOVABLE-FLASHLIGHT-PROBE-V1",
        "probe": public,
        "view_commitment": canonical_commitment("MOVABLE-FLASHLIGHT-V1", public),
        "local_slice_exported": False,
        "physical_claim": False,
    }
