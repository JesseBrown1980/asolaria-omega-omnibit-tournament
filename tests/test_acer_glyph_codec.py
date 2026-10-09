from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from asolaria_tournament.acer_glyph_codec import (
    ALL_VIEW_SELECTORS,
    BLOCK_FIXED,
    DIRECTION_CANDIDATES,
    DIRECTION_COMPOSITION,
    FOOTER,
    HEADER,
    MODE_GLYPH_LZW2,
    MAX_PRIME_LAG,
    NESTED_CARTESIAN_CANDIDATES_HELD,
    Projection,
    RECORD_LENGTH,
    Traversal,
    CodecError,
    completed_block_prefix,
    decode,
    decode_with_report,
    encode,
    encode_with_report,
    project_block,
    restore_block,
)


class AcerGlyphCodecTests(unittest.TestCase):
    def test_selector_axes_and_cardinalities_are_independent(self) -> None:
        self.assertEqual(DIRECTION_COMPOSITION, "FAMILY_UNION")
        self.assertEqual(DIRECTION_CANDIDATES, 168)
        self.assertEqual(NESTED_CARTESIAN_CANDIDATES_HELD, 6912)
        self.assertEqual(len(ALL_VIEW_SELECTORS), 168)
        self.assertEqual({item.family for item in ALL_VIEW_SELECTORS}, {6, 12, 24})
        self.assertEqual(
            {item.traversal for item in ALL_VIEW_SELECTORS},
            {Traversal.NORMAL, Traversal.ANTI},
        )
        self.assertEqual(
            {item.projection for item in ALL_VIEW_SELECTORS},
            {Projection.A, Projection.B},
        )
        with self.assertRaises(CodecError):
            type(ALL_VIEW_SELECTORS[0])(6, 0, 1, 0).validate()

    def test_every_view_is_exact_at_boundary_lengths(self) -> None:
        prefix = bytes(range(64))
        for selector in ALL_VIEW_SELECTORS:
            for length in (0, 1, 5, 6, 7, 11, 12, 13, 23, 24, 25):
                block = bytes((index * 29 + length) & 0xFF for index in range(length))
                residual = project_block(block, prefix, selector)
                self.assertEqual(restore_block(residual, prefix, selector), block)

    def test_projection_needs_only_the_bounded_prime_lag_tail(self) -> None:
        prefix = bytes(range(256)) * 20
        block = b"bounded causal tail" * 20
        for selector in ALL_VIEW_SELECTORS:
            full = project_block(block, prefix, selector)
            tail = project_block(block, prefix[-MAX_PRIME_LAG:], selector)
            self.assertEqual(full, tail)

    def test_exact_replay_for_empty_repeated_full_alphabet_and_random(self) -> None:
        rng = random.Random(0xA50A)
        cases = (
            b"",
            b"A" * 2048,
            bytes(range(256)) * 4,
            bytes(rng.randrange(256) for _ in range(1537)),
        )
        for source in cases:
            with self.subTest(length=len(source)):
                archive, encoded = encode_with_report(source, block_size=257)
                restored, decoded = decode_with_report(archive)
                self.assertEqual(restored, source)
                self.assertEqual(encoded.source_sha256, decoded.source_sha256)
                self.assertEqual(
                    encoded.final_unified_omega, decoded.final_unified_omega
                )

    def test_deterministic_archive_and_cache_free_recalculation(self) -> None:
        source = (b"noun verb word tuple omega " * 80) + bytes(range(64))
        first = encode(source, block_size=128)
        second = encode(source, block_size=128)
        self.assertEqual(first, second)
        self.assertEqual(decode(first), source)
        self.assertEqual(decode(first), source)

    def test_raw_and_glyph_modes_are_both_real(self) -> None:
        rng = random.Random(12345)
        random_source = bytes(rng.randrange(256) for _ in range(1024))
        _, random_report = encode_with_report(random_source, block_size=256)
        self.assertGreater(random_report.raw_blocks, 0)

        repeated_source = b"ASOLARIA-GLYPH-" * 256
        archive, repeated_report = encode_with_report(repeated_source, block_size=256)
        self.assertGreater(repeated_report.glyph_blocks, 0)
        self.assertTrue(
            any(block.mode == "GLYPH_LZW2" for block in repeated_report.blocks)
        )
        self.assertEqual(decode(archive), repeated_source)

    def test_selector_is_recomputed_from_previous_decoded_block(self) -> None:
        source = (b"previous block trains only the next selector" * 20)
        archive, report = encode_with_report(source, block_size=96)
        self.assertEqual(
            report.selector_evaluations,
            max(0, report.block_count - 1) * DIRECTION_CANDIDATES,
        )
        tampered = bytearray(archive)
        # Header, record length, index, raw_len, mode, then family.
        family_offset = HEADER.size + RECORD_LENGTH.size + 9
        tampered[family_offset] = 12
        with self.assertRaises(CodecError):
            decode(tampered)

    def test_later_suffix_cannot_change_completed_archive_prefix(self) -> None:
        common = (b"block-zero-prefix" * 4)[:64] + (b"block-one-prefix" * 4)[:64]
        left = common + (b"A" * 128)
        right = common + (b"Z" * 128)
        left_archive = encode(left, block_size=64)
        right_archive = encode(right, block_size=64)
        self.assertEqual(
            completed_block_prefix(left_archive, 2),
            completed_block_prefix(right_archive, 2),
        )

    def test_small_accepted_domain_is_collision_free(self) -> None:
        archives: set[bytes] = set()
        inputs = [b""]
        alphabet = (0, 1, 2)
        for first in alphabet:
            inputs.append(bytes((first,)))
            for second in alphabet:
                inputs.append(bytes((first, second)))
                for third in alphabet:
                    inputs.append(bytes((first, second, third)))
        for source in inputs:
            archive = encode(source, block_size=8)
            self.assertNotIn(archive, archives)
            self.assertEqual(decode(archive), source)
            archives.add(archive)

    def test_body_reserved_omega_footer_and_trailing_tamper_fail_closed(self) -> None:
        source = b"tamper-resistant-glyph-catalog " * 40
        archive = encode(source, block_size=128)
        base = HEADER.size + RECORD_LENGTH.size

        reserved = bytearray(archive)
        reserved[base + 13] = 1
        with self.assertRaises(CodecError):
            decode(reserved)

        omega = bytearray(archive)
        omega[base + BLOCK_FIXED.size - 1] ^= 1
        with self.assertRaises(CodecError):
            decode(omega)

        (record_len,) = RECORD_LENGTH.unpack_from(archive, HEADER.size)
        body_start = base + BLOCK_FIXED.size
        self.assertGreater(record_len, BLOCK_FIXED.size)
        body = bytearray(archive)
        body[body_start] ^= 0x80
        with self.assertRaises(CodecError):
            decode(body)

        footer = bytearray(archive)
        footer_start = len(footer) - FOOTER.size
        footer[footer_start + 28] ^= 1
        with self.assertRaises(CodecError):
            decode(footer)

        with self.assertRaises(CodecError):
            decode(archive + b"TRAIL")

        block_size = bytearray(archive)
        # magic(8), version(2), flags(2), then Omega-bound block_size(4)
        block_size[15] ^= 1
        with self.assertRaises(CodecError):
            decode(block_size)

    def test_truncation_output_cap_and_actual_byte_charge(self) -> None:
        source = b"charge every required byte" * 50
        archive, report = encode_with_report(source, block_size=100)
        with self.assertRaises(CodecError):
            decode(archive[:-1])
        with self.assertRaises(CodecError):
            decode(archive, max_output_bytes=len(source) - 1)
        charge = report.charge(
            decoder_artifact_bytes=1234, external_data_oracle_bytes=0
        )
        self.assertEqual(
            charge["research_archive_plus_one_decoder_bytes"],
            len(archive) + 1234,
        )
        self.assertEqual(charge["external_data_oracle_bytes"], 0)

    def test_numeric_limits_and_byte_charges_reject_bool_and_float(self) -> None:
        source = b"typed limits" * 20
        archive, report = encode_with_report(source, block_size=32)
        for invalid in (True, 1.0):
            with self.assertRaises(CodecError):
                encode(source, block_size=invalid)
            with self.assertRaises(CodecError):
                decode(archive, max_output_bytes=invalid)
            with self.assertRaises(CodecError):
                report.charge(decoder_artifact_bytes=invalid)
        with self.assertRaises(CodecError):
            report.charge(
                decoder_artifact_bytes=1, external_data_oracle_bytes=float("nan")
            )

        ordinary = report.hutter_relaxed_charge(
            compressor_artifact_bytes=100,
            decoder_artifact_bytes=20,
            command_line_bytes=3,
            additional_required_artifact_bytes=7,
        )
        self.assertEqual(
            ordinary["hutter_relaxed_total_bytes"],
            len(archive) + 100 + 2 * 20 + 3 + 7,
        )
        same = report.hutter_relaxed_charge(
            compressor_artifact_bytes=20,
            decoder_artifact_bytes=20,
            compressor_equals_decoder=True,
        )
        self.assertEqual(
            same["hutter_relaxed_total_bytes"], len(archive) + 20 + 20
        )

    def test_wire_mode_values_are_stable(self) -> None:
        self.assertEqual(MODE_GLYPH_LZW2, 1)


if __name__ == "__main__":
    unittest.main()
