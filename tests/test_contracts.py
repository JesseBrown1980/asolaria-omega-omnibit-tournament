from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asolaria_tournament.commitment import canonical_commitment
from asolaria_tournament.flashlight import FlashlightProbe, move_probe
from asolaria_tournament.privacy import forbidden_text_matches, violations
from asolaria_tournament.tournament import build_manifest


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


if __name__ == "__main__":
    unittest.main()
