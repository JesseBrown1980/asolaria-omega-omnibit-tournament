from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "tools" / "movable-flashlight"
SOURCE = TOOL_DIR / "light_dark_flashlight.py"
PIN = "445677f416139ea9a5a7f07298ce362aad6bef5f742d8726570c00515efa08b4"


def load_tool():
    sys.path.insert(0, str(TOOL_DIR))
    spec = importlib.util.spec_from_file_location("light_dark_flashlight", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load flashlight source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MovableFlashlightTests(unittest.TestCase):
    def test_source_pin(self) -> None:
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(), PIN)

    def test_region_thirds_cover_width(self) -> None:
        module = load_tool()
        regions = module.region_slices(12)
        covered = [
            index
            for region in ("left", "center", "right")
            for index in range(*regions[region].indices(12))
        ]
        self.assertEqual(covered, list(range(12)))

    def test_sign_means_pixel_intensity_change(self) -> None:
        first = (10.0, 20.0)
        last = (12.0, 17.0)
        net_signed = tuple(after - before for before, after in zip(first, last))
        self.assertGreater(net_signed[0], 0)
        self.assertLess(net_signed[1], 0)


if __name__ == "__main__":
    unittest.main()
