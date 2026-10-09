from __future__ import annotations

from collections import Counter
from dataclasses import replace
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asolaria_tournament.commitment import canonical_commitment
from asolaria_tournament.privacy import forbidden_text_matches
from asolaria_tournament.relic_engine import (
    CUBES_PER_FIELD,
    DIRECTIONS_PER_FLOOR,
    RECURSIVE_FLOORS,
    SHARED_OMEGA_BINDINGS,
    build_relic_archive,
    build_relic_receipt,
    compile_cube_route,
    decode_relic_field,
    derive_omega_ledger,
    reunify_relic_archive,
    transform_chunks,
)


SEED = canonical_commitment("RELIC-PUBLIC-FIXTURE-SEED-V1", {"fixture": "alpha"})
PAYLOAD = bytes(range(256)) * 8


class RelicEngineTests(unittest.TestCase):
    def test_cube_route_has_four_floors_and_forty_directions_each(self) -> None:
        ledger = derive_omega_ledger(SEED)
        route = compile_cube_route("A", ledger)
        self.assertEqual(len(route.cubes), CUBES_PER_FIELD)
        self.assertEqual(CUBES_PER_FIELD, 160)
        counts = Counter(cube.floor for cube in route.cubes)
        self.assertEqual(
            counts,
            Counter({floor: DIRECTIONS_PER_FLOOR for floor in RECURSIVE_FLOORS}),
        )
        self.assertEqual({cube.direction_index for cube in route.cubes}, set(range(40)))
        self.assertEqual(
            {cube.omega_slot for cube in route.cubes},
            set(range(SHARED_OMEGA_BINDINGS)),
        )

    def test_omega_ledger_preserves_twenty_seven_plus_one(self) -> None:
        ledger = derive_omega_ledger(SEED)
        self.assertEqual(len(ledger.bindings), 27)
        self.assertEqual(len(set(ledger.bindings)), 27)
        self.assertEqual(len(ledger.unified_root), 64)

    def test_dual_fields_are_distinct_and_reunify_exactly(self) -> None:
        archive = build_relic_archive(PAYLOAD, SEED)
        self.assertNotEqual(
            archive.field("A").payload,
            archive.field("B").payload,
        )
        self.assertEqual(decode_relic_field(archive, "A"), PAYLOAD)
        self.assertEqual(decode_relic_field(archive, "B"), PAYLOAD)
        self.assertEqual(reunify_relic_archive(archive), PAYLOAD)

    def test_transform_is_independent_of_chunk_boundaries(self) -> None:
        ledger = derive_omega_ledger(SEED)
        route = compile_cube_route("A", ledger)
        whole = b"".join(transform_chunks((PAYLOAD,), route, ledger))
        split = b"".join(
            transform_chunks(
                (PAYLOAD[:17], PAYLOAD[17:511], PAYLOAD[511:]),
                route,
                ledger,
            )
        )
        self.assertEqual(whole, split)

    def test_suffix_change_does_not_rewrite_encoded_prefix(self) -> None:
        prefix = b"causal-prefix:"
        left = build_relic_archive(prefix + b"left", SEED)
        right = build_relic_archive(prefix + b"right-and-longer", SEED)
        for field in ("A", "B"):
            self.assertEqual(
                left.field(field).payload[: len(prefix)],
                right.field(field).payload[: len(prefix)],
            )

    def test_encoded_payload_tamper_fails_closed(self) -> None:
        archive = build_relic_archive(PAYLOAD, SEED)
        original = archive.field("A")
        tampered_payload = bytes([original.payload[0] ^ 1]) + original.payload[1:]
        tampered_field = replace(original, payload=tampered_payload)
        tampered = replace(
            archive,
            encoded_fields=(tampered_field, archive.field("B")),
        )
        with self.assertRaisesRegex(ValueError, "encoded payload integrity"):
            decode_relic_field(tampered, "A")

    def test_manifest_preserves_axes_without_materializing_topology(self) -> None:
        archive = build_relic_archive(PAYLOAD, SEED)
        manifest = archive.public_manifest()
        self.assertEqual(manifest["topology_nodes_per_pass"], 93312)
        self.assertEqual(manifest["logical_address_exponent"], 100000000)
        self.assertEqual(manifest["cubes_per_field"], 160)
        self.assertEqual(manifest["execution"]["fused_payload_passes_total"], 2)
        self.assertFalse(manifest["local_matrix_accessed"])
        self.assertFalse(manifest["claims"]["hutter_result"])

    def test_receipt_is_path_free_and_claim_bounded(self) -> None:
        archive = build_relic_archive(PAYLOAD, SEED)
        receipt = build_relic_receipt(archive)
        self.assertEqual(forbidden_text_matches(receipt), [])
        self.assertIn("exact_restore=1", receipt)
        self.assertIn("shared_binding_commitments=27", receipt)
        self.assertIn("compression_claim=0", receipt)
        self.assertIn("hutter_result=0", receipt)
        self.assertIn("physical_claim=0", receipt)
        self.assertIn("local_matrix_accessed=0", receipt)
        self.assertNotIn(PAYLOAD.hex(), receipt)


if __name__ == "__main__":
    unittest.main()
