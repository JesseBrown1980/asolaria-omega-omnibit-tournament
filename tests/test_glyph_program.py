from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asolaria_tournament.glyph_program import (
    MAX_CODE_WIDTH,
    GlyphRole,
    Tuple60,
    Verb,
    lzw_decode,
    lzw_encode,
    pack_codes,
    unpack_codes,
)


class GlyphProgramTests(unittest.TestCase):
    def test_language_types_are_explicit(self) -> None:
        self.assertEqual({role.value for role in GlyphRole}, {"NOUN", "WORD"})
        self.assertEqual(
            {verb.value for verb in Verb},
            {"EMIT", "CONCAT", "CATALOG_INSERT"},
        )

    def test_tuple60_preserves_every_axis(self) -> None:
        axes = tuple(range(60))
        value = Tuple60.from_iterable(iter(axes))
        self.assertEqual(value.axes, axes)
        self.assertEqual(len(value), 60)

    def test_tuple60_rejects_shape_and_type_drift(self) -> None:
        with self.assertRaises(ValueError):
            Tuple60(tuple(range(59)))
        with self.assertRaises(TypeError):
            Tuple60(tuple(range(59)) + (True,))
        with self.assertRaises(ValueError):
            Tuple60(tuple(range(59)) + (1 << 63,))

    def test_256_to_1024_round_trip_and_catalog_match(self) -> None:
        symbols = tuple((index * 17 + index // 7) % 256 for index in range(4096))
        encoded = lzw_encode(symbols, alphabet_size=256, capacity=1024)
        decoded = lzw_decode(encoded.codes, alphabet_size=256, capacity=1024)

        self.assertEqual(decoded.symbols, symbols)
        self.assertEqual(decoded.catalog.entries, encoded.catalog.entries)
        self.assertEqual(decoded.catalog_digest, encoded.catalog_digest)
        self.assertTrue(encoded.catalog_frozen)

    def test_two_rungs_recalculate_exact_source(self) -> None:
        source = tuple(b"glyph words recalculate; " * 200)
        rung_1024 = lzw_encode(source, alphabet_size=256, capacity=1024)
        rung_4096 = lzw_encode(
            rung_1024.codes,
            alphabet_size=1024,
            capacity=4096,
        )

        back_to_1024 = lzw_decode(
            rung_4096.codes,
            alphabet_size=1024,
            capacity=4096,
        )
        back_to_source = lzw_decode(
            back_to_1024.symbols,
            alphabet_size=256,
            capacity=1024,
        )

        self.assertEqual(back_to_1024.catalog_digest, rung_4096.catalog_digest)
        self.assertEqual(back_to_source.catalog_digest, rung_1024.catalog_digest)
        self.assertEqual(back_to_source.symbols, source)

    def test_kwkwk_is_decoded_and_commits_to_same_catalog(self) -> None:
        # AAA emits [A, dictionary[A+A]], exercising code == next_code.
        encoded = lzw_encode((65, 65, 65), alphabet_size=256, capacity=1024)
        self.assertEqual(encoded.codes, (65, 256))

        decoded = lzw_decode(encoded.codes, alphabet_size=256, capacity=1024)
        self.assertEqual(decoded.symbols, (65, 65, 65))
        self.assertEqual(decoded.catalog_digest, encoded.catalog_digest)

    def test_invalid_codes_are_rejected_strictly(self) -> None:
        with self.assertRaises(ValueError):
            lzw_decode((256,), alphabet_size=256, capacity=1024)
        with self.assertRaises(ValueError):
            lzw_decode((65, 257), alphabet_size=256, capacity=1024)
        with self.assertRaises(ValueError):
            lzw_decode((65, 256), alphabet_size=256, capacity=256)

    def test_dictionary_freezes_without_implicit_reset(self) -> None:
        source = tuple(b"ABABABA-ABABABA")
        encoded = lzw_encode(source, alphabet_size=256, capacity=256)
        decoded = lzw_decode(encoded.codes, alphabet_size=256, capacity=256)

        self.assertTrue(encoded.catalog_frozen)
        self.assertEqual(encoded.catalog_size, 256)
        self.assertEqual(decoded.symbols, source)
        self.assertEqual(decoded.catalog_digest, encoded.catalog_digest)

    def test_empty_stream_has_reproducible_base_catalog(self) -> None:
        encoded = lzw_encode((), alphabet_size=256, capacity=1024)
        decoded = lzw_decode((), alphabet_size=256, capacity=1024)
        self.assertEqual(encoded.codes, ())
        self.assertEqual(decoded.symbols, ())
        self.assertEqual(decoded.catalog_digest, encoded.catalog_digest)

    def test_output_cap_is_enforced_before_expansion(self) -> None:
        encoded = lzw_encode((65,) * 64, alphabet_size=256, capacity=1024)
        with self.assertRaises(ValueError):
            lzw_decode(
                encoded.codes,
                alphabet_size=256,
                capacity=1024,
                max_output_symbols=63,
            )

    def test_fixed_width_pack_round_trip(self) -> None:
        codes = (0, 1, 255, 256, 1023, 17)
        payload = pack_codes(codes, width=10)
        self.assertEqual(len(payload), 8)
        self.assertEqual(unpack_codes(payload, count=len(codes), width=10), codes)

    def test_fixed_width_unpack_rejects_framing_and_padding_drift(self) -> None:
        payload = pack_codes((1,), width=10)
        with self.assertRaises(ValueError):
            unpack_codes(payload + b"\x00", count=1, width=10)
        with self.assertRaises(ValueError):
            unpack_codes(payload[:-1], count=1, width=10)

        nonzero_padding = payload[:-1] + bytes((payload[-1] | 0x01,))
        with self.assertRaises(ValueError):
            unpack_codes(nonzero_padding, count=1, width=10)

    def test_fixed_width_bounds_are_explicit(self) -> None:
        with self.assertRaises(ValueError):
            pack_codes((1024,), width=10)
        with self.assertRaises(ValueError):
            pack_codes((0,), width=0)
        with self.assertRaises(ValueError):
            pack_codes((0,), width=MAX_CODE_WIDTH + 1)
        with self.assertRaises(TypeError):
            unpack_codes(bytearray(), count=0, width=1)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
