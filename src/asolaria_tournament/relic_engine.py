"""Relic dual-field Omnibit cube engine.

This is a deterministic, reversible, privacy-safe baseline. It compiles logical
cube descriptors into one fused stream transform per reflection field. It is
not encryption, compression, a physical-quantum implementation, or a Hutter
Prize result.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Iterator

from .commitment import canonical_bytes, canonical_commitment

SEAT = "relic"
REFLECTION_FIELDS = ("A", "B")
RECURSIVE_FLOORS = (64, 256, 1024, 4096)
DIRECTION_FAMILIES = (("RNQ", 8), ("TRI", 12), ("PI_LENS", 20))
DIRECTIONS_PER_FLOOR = sum(count for _, count in DIRECTION_FAMILIES)
CUBES_PER_FIELD = len(RECURSIVE_FLOORS) * DIRECTIONS_PER_FLOOR
SHARED_OMEGA_BINDINGS = 27
UNIFIED_OMEGA_ROOTS = 1
TOPOLOGY_NODES_PER_PASS = 93_312
LOGICAL_ADDRESS_EXPONENT = 100_000_000
MASK_BLOCK_BYTES = hashlib.sha256().digest_size


def _require_ascii(label: str, value: str) -> None:
    if not value or not value.isascii():
        raise ValueError(f"{label} must be non-empty ASCII")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class OmegaLedger:
    """Public binding commitments, never secret key material."""

    seed_commitment: str
    bindings: tuple[str, ...]
    unified_root: str

    def public_dict(self) -> dict[str, object]:
        return {
            "shared_binding_count": len(self.bindings),
            "shared_bindings": list(self.bindings),
            "unified_root_count": UNIFIED_OMEGA_ROOTS,
            "unified_root": self.unified_root,
            "binding_semantics": "PUBLIC_DOMAIN_SEPARATED_COMMITMENTS",
        }


@dataclass(frozen=True)
class CubeAddress:
    floor: int
    family: str
    direction: int
    direction_index: int
    reflection_field: str
    omega_slot: int

    def public_dict(self) -> dict[str, object]:
        return {
            "floor": self.floor,
            "family": self.family,
            "direction": self.direction,
            "direction_index": self.direction_index,
            "reflection_field": self.reflection_field,
            "omega_slot": self.omega_slot,
        }


@dataclass(frozen=True)
class CubeRoute:
    reflection_field: str
    cubes: tuple[CubeAddress, ...]
    route_root: str


@dataclass(frozen=True)
class EncodedField:
    reflection_field: str
    route_root: str
    payload: bytes
    payload_sha256: str

    def public_dict(self) -> dict[str, object]:
        return {
            "reflection_field": self.reflection_field,
            "route_root": self.route_root,
            "payload_bytes": len(self.payload),
            "payload_sha256": self.payload_sha256,
        }


@dataclass(frozen=True)
class DualFieldArchive:
    schema: str
    source_bytes: int
    source_sha256: str
    omega_ledger: OmegaLedger
    encoded_fields: tuple[EncodedField, EncodedField]
    manifest_commitment: str

    def field(self, reflection_field: str) -> EncodedField:
        for item in self.encoded_fields:
            if item.reflection_field == reflection_field:
                return item
        raise ValueError(f"archive does not contain field {reflection_field}")

    def public_manifest(self) -> dict[str, object]:
        manifest = _manifest_core(
            source_bytes=self.source_bytes,
            source_sha256=self.source_sha256,
            omega_ledger=self.omega_ledger,
            encoded_fields=self.encoded_fields,
        )
        manifest["manifest_commitment"] = self.manifest_commitment
        return manifest


def derive_omega_ledger(seed_commitment: str) -> OmegaLedger:
    """Derive 27 public binding IDs and exactly one unifying commitment."""
    _require_ascii("seed_commitment", seed_commitment)
    bindings = tuple(
        canonical_commitment(
            "RELIC-OMEGA-BINDING-V1",
            {"seat": SEAT, "slot": slot, "seed_commitment": seed_commitment},
        )
        for slot in range(SHARED_OMEGA_BINDINGS)
    )
    unified_root = canonical_commitment(
        "RELIC-UNIFIED-OMEGA-ROOT-V1",
        {"seat": SEAT, "bindings": bindings},
    )
    return OmegaLedger(seed_commitment, bindings, unified_root)


def compile_cube_route(
    reflection_field: str,
    omega_ledger: OmegaLedger,
) -> CubeRoute:
    """Compile 4 floors x 40 directions into 160 logical cube descriptors."""
    if reflection_field not in REFLECTION_FIELDS:
        raise ValueError("reflection_field must be A or B")
    if len(omega_ledger.bindings) != SHARED_OMEGA_BINDINGS:
        raise ValueError("exactly 27 Omega binding commitments are required")

    cubes: list[CubeAddress] = []
    for floor_index, floor in enumerate(RECURSIVE_FLOORS):
        family_offset = 0
        for family, count in DIRECTION_FAMILIES:
            for direction in range(count):
                direction_index = family_offset + direction
                cubes.append(
                    CubeAddress(
                        floor=floor,
                        family=family,
                        direction=direction,
                        direction_index=direction_index,
                        reflection_field=reflection_field,
                        omega_slot=(
                            floor_index * DIRECTIONS_PER_FLOOR + direction_index
                        )
                        % SHARED_OMEGA_BINDINGS,
                    )
                )
            family_offset += count

    if len(cubes) != CUBES_PER_FIELD:
        raise AssertionError("cube route cardinality drift")
    route_root = canonical_commitment(
        "RELIC-OMNIBIT-CUBE-ROUTE-V1",
        {
            "seat": SEAT,
            "reflection_field": reflection_field,
            "unified_omega_root": omega_ledger.unified_root,
            "cubes": [cube.public_dict() for cube in cubes],
        },
    )
    return CubeRoute(reflection_field, tuple(cubes), route_root)


def _mask_block(
    route: CubeRoute,
    omega_ledger: OmegaLedger,
    block_index: int,
) -> bytes:
    if block_index < 0:
        raise ValueError("block_index must be non-negative")
    framed = (
        b"ASOLARIA-RELIC-FUSED-CUBE-MASK-V1\x00"
        + bytes.fromhex(route.route_root)
        + bytes.fromhex(omega_ledger.unified_root)
        + block_index.to_bytes(8, "big")
    )
    return hashlib.sha256(framed).digest()


def transform_chunks(
    chunks: Iterable[bytes | bytearray | memoryview],
    route: CubeRoute,
    omega_ledger: OmegaLedger,
) -> Iterator[bytes]:
    """Apply a reversible fused route with chunk-boundary-independent output.

    The public commitment-derived mask provides deterministic routing only. It
    is deliberately not represented as encryption or secret-key protection.
    """
    block_index = 0
    mask = b""
    mask_offset = 0

    for chunk in chunks:
        source = bytes(chunk)
        output = bytearray(len(source))
        cursor = 0
        while cursor < len(source):
            if mask_offset >= len(mask):
                mask = _mask_block(route, omega_ledger, block_index)
                block_index += 1
                mask_offset = 0
            take = min(len(source) - cursor, len(mask) - mask_offset)
            for index in range(take):
                output[cursor + index] = (
                    source[cursor + index] ^ mask[mask_offset + index]
                )
            cursor += take
            mask_offset += take
        yield bytes(output)


def transform_bytes(
    payload: bytes,
    route: CubeRoute,
    omega_ledger: OmegaLedger,
) -> bytes:
    return b"".join(transform_chunks((payload,), route, omega_ledger))


def _manifest_core(
    *,
    source_bytes: int,
    source_sha256: str,
    omega_ledger: OmegaLedger,
    encoded_fields: tuple[EncodedField, EncodedField],
) -> dict[str, object]:
    return {
        "schema": "ASOLARIA-RELIC-DUAL-FIELD-ARCHIVE-V1",
        "seat": SEAT,
        "local_matrix": "OPAQUE_NONREPLICATED",
        "local_matrix_accessed": False,
        "source_bytes": source_bytes,
        "source_sha256": source_sha256,
        "topology_nodes_per_pass": TOPOLOGY_NODES_PER_PASS,
        "logical_address_exponent": LOGICAL_ADDRESS_EXPONENT,
        "reflection_fields": list(REFLECTION_FIELDS),
        "normal_anti_binding": "UNRESOLVED",
        "recursive_floors": list(RECURSIVE_FLOORS),
        "direction_families": {
            family: count for family, count in DIRECTION_FAMILIES
        },
        "directions_per_floor": DIRECTIONS_PER_FLOOR,
        "cubes_per_field": CUBES_PER_FIELD,
        "cubes_total": CUBES_PER_FIELD * len(REFLECTION_FIELDS),
        "omega": omega_ledger.public_dict(),
        "encoded_fields": [field.public_dict() for field in encoded_fields],
        "execution": {
            "logical_cube_passes_per_field": CUBES_PER_FIELD,
            "fused_payload_passes_total": len(REFLECTION_FIELDS),
            "streaming_supported": True,
        },
        "claims": {
            "compression_claim": False,
            "hutter_result": False,
            "physical_quantum_claim": False,
            "whole_wikipedia_replay": "UNVERIFIED",
        },
    }


def build_relic_archive(
    payload: bytes | bytearray | memoryview,
    omega_seed_commitment: str,
) -> DualFieldArchive:
    """Build two independently routed fields without reading local seat state."""
    source = bytes(payload)
    ledger = derive_omega_ledger(omega_seed_commitment)
    encoded: list[EncodedField] = []
    for reflection_field in REFLECTION_FIELDS:
        route = compile_cube_route(reflection_field, ledger)
        routed = transform_bytes(source, route, ledger)
        encoded.append(
            EncodedField(
                reflection_field=reflection_field,
                route_root=route.route_root,
                payload=routed,
                payload_sha256=_sha256(routed),
            )
        )
    encoded_fields = (encoded[0], encoded[1])
    core = _manifest_core(
        source_bytes=len(source),
        source_sha256=_sha256(source),
        omega_ledger=ledger,
        encoded_fields=encoded_fields,
    )
    return DualFieldArchive(
        schema="ASOLARIA-RELIC-DUAL-FIELD-ARCHIVE-V1",
        source_bytes=len(source),
        source_sha256=_sha256(source),
        omega_ledger=ledger,
        encoded_fields=encoded_fields,
        manifest_commitment=canonical_commitment(
            "RELIC-DUAL-FIELD-ARCHIVE-MANIFEST-V1", core
        ),
    )


def decode_relic_field(
    archive: DualFieldArchive,
    reflection_field: str,
) -> bytes:
    """Decode one field and fail closed on ledger, route, payload, or source drift."""
    expected_ledger = derive_omega_ledger(archive.omega_ledger.seed_commitment)
    if expected_ledger != archive.omega_ledger:
        raise ValueError("Omega ledger integrity failure")
    route = compile_cube_route(reflection_field, expected_ledger)
    encoded = archive.field(reflection_field)
    if route.route_root != encoded.route_root:
        raise ValueError("cube route integrity failure")
    if _sha256(encoded.payload) != encoded.payload_sha256:
        raise ValueError("encoded payload integrity failure")

    restored = transform_bytes(encoded.payload, route, expected_ledger)
    if len(restored) != archive.source_bytes:
        raise ValueError("restored length mismatch")
    if _sha256(restored) != archive.source_sha256:
        raise ValueError("restored source hash mismatch")
    return restored


def reunify_relic_archive(archive: DualFieldArchive) -> bytes:
    """Decode A and B independently, then require byte-identical reunification."""
    restored_a = decode_relic_field(archive, "A")
    restored_b = decode_relic_field(archive, "B")
    if restored_a != restored_b:
        raise ValueError("dual-field reunification mismatch")
    return restored_a


def _tuple_value(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (tuple, list)):
        return ",".join(_tuple_value(item) for item in value)
    return (
        str(value)
        .replace("%", "%25")
        .replace("|", "%7C")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def _hbp_row(kind: str, **fields: object) -> str:
    return "|".join(
        [kind, *(f"{key}={_tuple_value(value)}" for key, value in fields.items())]
    )


def build_relic_receipt(archive: DualFieldArchive) -> str:
    """Verify the archive and return a path-free, payload-free HBP receipt."""
    restored = reunify_relic_archive(archive)
    manifest = archive.public_manifest()
    metadata_bytes = len(canonical_bytes(manifest))
    field_payload_bytes = sum(len(field.payload) for field in archive.encoded_fields)
    rows = [
        _hbp_row(
            "RELICRUNHDR",
            schema="ASOLARIA-RELIC-DUAL-FIELD-RUN-V1",
            seat="RELIC",
            engine="FUSED_OMNIBIT_CUBE_ROUTE_V1",
            evidence="MEASURED",
            json=0,
        ),
        _hbp_row(
            "RELICCUBES",
            floors=RECURSIVE_FLOORS,
            direction_families="RNQ8,TRI12,PI_LENS20",
            directions_per_floor=DIRECTIONS_PER_FLOOR,
            cubes_per_field=CUBES_PER_FIELD,
            cubes_total=CUBES_PER_FIELD * len(REFLECTION_FIELDS),
            cube_level_is_glyph_level=False,
            fused_payload_passes=2,
            json=0,
        ),
    ]
    for field in archive.encoded_fields:
        rows.append(
            _hbp_row(
                "RELICFIELD",
                field=field.reflection_field,
                route_root=field.route_root,
                payload_bytes=len(field.payload),
                payload_sha256=field.payload_sha256,
                exact_restore=True,
                json=0,
            )
        )
    rows.extend(
        [
            _hbp_row(
                "RELICOMEGA",
                shared_binding_commitments=len(archive.omega_ledger.bindings),
                unified_roots=UNIFIED_OMEGA_ROOTS,
                unified_root=archive.omega_ledger.unified_root,
                secret_key_material=False,
                json=0,
            ),
            _hbp_row(
                "RELICAXES",
                topology_nodes_per_pass=TOPOLOGY_NODES_PER_PASS,
                logical_address_exponent=LOGICAL_ADDRESS_EXPONENT,
                historical_population="SEPARATE_AXIS",
                normal_anti_binding="UNRESOLVED",
                json=0,
            ),
            _hbp_row(
                "RELICACCOUNTING",
                source_bytes=len(restored),
                field_payload_bytes=field_payload_bytes,
                public_manifest_bytes=metadata_bytes,
                decoder_bytes="UNCOUNTED",
                hutter_eligible=False,
                json=0,
            ),
            _hbp_row(
                "RELICVERIFY",
                exact_restore=True,
                source_sha256=archive.source_sha256,
                manifest_commitment=archive.manifest_commitment,
                local_matrix_accessed=False,
                local_slice_exported=False,
                json=0,
            ),
            _hbp_row(
                "RELICCLAIM",
                compression_claim=False,
                hutter_result=False,
                physical_claim=False,
                whole_wikipedia_replay="UNVERIFIED",
                json=0,
            ),
        ]
    )
    return "\n".join(rows) + "\n"
