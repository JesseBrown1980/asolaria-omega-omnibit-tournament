from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from asolaria_tournament.commitment import canonical_commitment
from asolaria_tournament.flashlight import FlashlightProbe, move_probe
from asolaria_tournament.privacy import forbidden_text_matches, violations
from asolaria_tournament.tournament import build_manifest
from scripts.verify_public_tree import forbidden_path_component
from scripts.verify_receipt_privacy import parse_sha256_sidecar, receipt_kind


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((ROOT / "config" / "base.json").read_text())

    def test_commitment_is_canonical(self) -> None:
        left = canonical_commitment("TEST", {"b": 2, "a": 1})
        right = canonical_commitment("TEST", {"a": 1, "b": 2})
        self.assertEqual(left, right)

    def test_axes_remain_distinct(self) -> None:
        self.assertEqual(self.config["topology_nodes_per_pass"], 93312)
        self.assertEqual(self.config["logical_address_exponent"], 100000000)
        self.assertEqual(
            self.config["historical_training_population"],
            "HUNDREDS_OF_MILLIONS",
        )
        self.assertNotIn(93312, self.config["reference_rungs"])
        self.assertEqual(self.config["shared_omega_keys"]["count"], 27)
        self.assertEqual(
            self.config["shared_omega_keys"]["class"], "OPERATOR_SPECIFIED"
        )

    def test_two_fields_make_six_registered_vantages(self) -> None:
        manifests = [build_manifest(self.config, seat) for seat in self.config["seats"]]
        vantages = [v for manifest in manifests for v in manifest["vantages"]]
        self.assertEqual(len(vantages), 6)
        self.assertEqual({v["view_binding"] for v in vantages}, {"NORMAL", "ANTI"})

    def test_movable_flashlight_exports_commitment_only(self) -> None:
        result = move_probe(
            FlashlightProbe(
                seat="acer",
                reflection_field="A",
                direction_port=7,
                traversal_sign=-1,
                rung=4096,
                pid="PID-TEST",
                slice_commitment="sha256:test",
                omega_binding="omega:test",
            )
        )
        self.assertFalse(result["local_slice_exported"])
        self.assertEqual(len(result["view_commitment"]), 64)

    def test_private_path_is_rejected(self) -> None:
        private_path = "C:" + "\\Users" + "\\seat\\private"
        self.assertTrue(forbidden_text_matches(private_path))

    def test_repository_passes_privacy_gate(self) -> None:
        self.assertEqual(violations(ROOT), [])

    def test_public_tree_rejects_private_storage_roots(self) -> None:
        for root in (
            "corpus",
            "matrices",
            "weights",
            "models",
            "private",
            "secrets",
            "local",
            "runs",
        ):
            self.assertEqual(forbidden_path_component(f"{root}/fixture.txt"), root)
        self.assertIsNone(forbidden_path_component("provenance/receipts/public.hbp"))

    def test_receipt_sha256_sidecar_contract(self) -> None:
        digest = "a" * 64
        self.assertEqual(
            parse_sha256_sidecar(f"{digest} *receipt.hbp\n", "receipt.hbp"),
            digest,
        )
        self.assertEqual(receipt_kind(Path("receipt.hbp.sha256")), "sidecar")
        with self.assertRaises(ValueError):
            parse_sha256_sidecar(f"{digest} *other.hbp\n", "receipt.hbp")


if __name__ == "__main__":
    unittest.main()
