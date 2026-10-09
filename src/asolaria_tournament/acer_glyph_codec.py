"""Acer research cell for causal glyph-catalog recalculation.

This is deliberately a small, falsifiable codec rather than a Hutter claim.
It implements a bounded forward-only framed archive whose decoder rebuilds two adaptive
catalogs from the already decoded stream.  Direction family, traversal, and
projection field are independent selectors.  Omega values commit to the
recalculation chain for self-consistency; they never stand in for omitted
payload bytes or provide authenticity without a separately trusted root.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import hashlib
import struct
from typing import Iterable

from .glyph_program import lzw_decode, lzw_encode, pack_codes, unpack_codes


MAGIC = b"AOGCV001"
FOOTER_MAGIC = b"AOGCFTR1"
VERSION = 1
FLAGS = 0

CATALOG_MODE = "ONLINE_REBUILT_CATALOG"
DIRECTION_COMPOSITION = "FAMILY_UNION"
DIRECTION_FAMILIES = (6, 12, 24)
DIRECTION_CANDIDATES = sum(DIRECTION_FAMILIES) * 2 * 2
NESTED_CARTESIAN_CANDIDATES_HELD = 6 * 12 * 24 * 2 * 2

DEFAULT_BLOCK_SIZE = 1024
MAX_BLOCK_SIZE = 1_000_000
MAX_OUTPUT_BYTES = 1_000_000_000
MAX_BLOCK_COUNT = 2_000_000
MAX_ARCHIVE_BYTES = 1_500_000_000
SCORE_SAMPLE_BYTES = 128

MODE_RAW_RESIDUAL = 0
MODE_GLYPH_LZW2 = 1

HEADER = struct.Struct(">8sHHI32s32s")
RECORD_LENGTH = struct.Struct(">I")
BLOCK_FIXED = struct.Struct(">IIBBBBBBIII32s32s32s32s")
FOOTER = struct.Struct(">8sIQQ32s32s")

CONFIG_DESCRIPTION = (
    b"AOGCV001|catalog=ONLINE_REBUILT_CATALOG|catalog_capacity=256,1024,4096|"
    b"wire_width=12|direction_composition=FAMILY_UNION|families=6,12,24|"
    b"traversal=NORMAL,ANTI|projection=A_XOR,B_DELTA|selector=PREVIOUS_BLOCK|"
    b"dictionary_full=FREEZE|raw_fallback=1|"
    b"omega=SELF_CONSISTENCY_COMMITMENT_NOT_PAYLOAD_OR_AUTHENTICITY"
)
CONFIG_COMMITMENT = hashlib.sha256(CONFIG_DESCRIPTION).digest()
GENESIS_DOMAIN = b"ASOLARIA-ACER-GLYPH-OMEGA-GENESIS-V1\x00"
RAW_CATALOG_DIGEST = hashlib.sha256(b"RAW-RESIDUAL-NO-CATALOG-V1\x00").digest()


class CodecError(ValueError):
    """The archive or codec configuration is invalid."""


class Traversal(IntEnum):
    NORMAL = 0
    ANTI = 1


class Projection(IntEnum):
    A = 0
    B = 1


@dataclass(frozen=True, order=True)
class ViewSelector:
    family: int
    direction: int
    traversal: Traversal
    projection: Projection

    def validate(self) -> None:
        if type(self.family) is not int or type(self.direction) is not int:
            raise CodecError("family and direction must be plain integers")
        if not isinstance(self.traversal, Traversal) or not isinstance(
            self.projection, Projection
        ):
            raise CodecError("traversal and projection must be typed enums")
        if self.family not in DIRECTION_FAMILIES:
            raise CodecError("unknown direction family")
        if not 0 <= self.direction < self.family:
            raise CodecError("direction is outside its family")
    def wire(self) -> bytes:
        self.validate()
        return bytes(
            (self.family, self.direction, int(self.traversal), int(self.projection))
        )


@dataclass(frozen=True)
class BlockReport:
    index: int
    raw_bytes: int
    body_bytes: int
    mode: str
    selector: ViewSelector
    level1_codes: int
    level2_codes: int
    omega: str


@dataclass(frozen=True)
class CodecReport:
    original_bytes: int
    archive_bytes: int
    block_count: int
    raw_blocks: int
    glyph_blocks: int
    selector_candidates: int
    selector_evaluations: int
    final_unified_omega: str
    source_sha256: str
    blocks: tuple[BlockReport, ...]

    def charge(
        self,
        *,
        decoder_artifact_bytes: int,
        external_data_oracle_bytes: int = 0,
    ) -> dict[str, int]:
        """Return the local research metric, not a Hutter Prize score.

        This deliberately counts one decoder.  The official relaxed Hutter
        formula separately charges the compressor and normally two decoder
        copies; use :meth:`hutter_relaxed_charge` only after every artifact is
        measured.
        """
        _require_plain_nonnegative_int(
            decoder_artifact_bytes, "decoder_artifact_bytes"
        )
        _require_plain_nonnegative_int(
            external_data_oracle_bytes, "external_data_oracle_bytes"
        )
        total = (
            self.archive_bytes
            + decoder_artifact_bytes
            + external_data_oracle_bytes
        )
        return {
            "archive_bytes": self.archive_bytes,
            "decoder_artifact_bytes": decoder_artifact_bytes,
            "external_data_oracle_bytes": external_data_oracle_bytes,
            "research_archive_plus_one_decoder_bytes": total,
        }

    def hutter_relaxed_charge(
        self,
        *,
        compressor_artifact_bytes: int,
        decoder_artifact_bytes: int,
        command_line_bytes: int = 0,
        additional_required_artifact_bytes: int = 0,
        compressor_equals_decoder: bool = False,
    ) -> dict[str, int]:
        """Apply the published separate-compressor Hutter size formula.

        Identity of compressor and decoder must be established outside this
        numeric helper.  When it is established, the decoder multiplier falls
        from two to one; the compressor term remains charged.
        """
        for value, label in (
            (compressor_artifact_bytes, "compressor_artifact_bytes"),
            (decoder_artifact_bytes, "decoder_artifact_bytes"),
            (command_line_bytes, "command_line_bytes"),
            (
                additional_required_artifact_bytes,
                "additional_required_artifact_bytes",
            ),
        ):
            _require_plain_nonnegative_int(value, label)
        if type(compressor_equals_decoder) is not bool:
            raise CodecError("compressor_equals_decoder must be boolean")
        decoder_multiplier = 1 if compressor_equals_decoder else 2
        total = (
            self.archive_bytes
            + compressor_artifact_bytes
            + decoder_multiplier * decoder_artifact_bytes
            + command_line_bytes
            + additional_required_artifact_bytes
        )
        return {
            "archive_bytes": self.archive_bytes,
            "compressor_artifact_bytes": compressor_artifact_bytes,
            "decoder_artifact_bytes": decoder_artifact_bytes,
            "decoder_multiplier": decoder_multiplier,
            "command_line_bytes": command_line_bytes,
            "additional_required_artifact_bytes": additional_required_artifact_bytes,
            "hutter_relaxed_total_bytes": total,
        }


def _require_plain_nonnegative_int(value: object, label: str) -> None:
    if type(value) is not int or value < 0:
        raise CodecError(f"{label} must be a plain nonnegative integer")


def all_view_selectors() -> tuple[ViewSelector, ...]:
    selectors = tuple(
        ViewSelector(family, direction, traversal, projection)
        for family in DIRECTION_FAMILIES
        for direction in range(family)
        for traversal in (Traversal.NORMAL, Traversal.ANTI)
        for projection in (Projection.A, Projection.B)
    )
    if len(selectors) != DIRECTION_CANDIDATES:
        raise AssertionError("selector census drift")
    return selectors


ALL_VIEW_SELECTORS = all_view_selectors()


def _genesis_omega(block_size: int) -> bytes:
    return hashlib.sha256(
        GENESIS_DOMAIN + CONFIG_COMMITMENT + block_size.to_bytes(4, "big")
    ).digest()


def _first_primes(count: int) -> tuple[int, ...]:
    primes: list[int] = []
    candidate = 2
    while len(primes) < count:
        is_prime = True
        divisor = 2
        while divisor * divisor <= candidate:
            if candidate % divisor == 0:
                is_prime = False
                break
            divisor += 1
        if is_prime:
            primes.append(candidate)
        candidate += 1
    return tuple(primes)


PRIME_LAGS = _first_primes(sum(DIRECTION_FAMILIES))
MAX_PRIME_LAG = max(PRIME_LAGS)


def _direction_ordinal(selector: ViewSelector) -> int:
    selector.validate()
    offset = 0
    for family in DIRECTION_FAMILIES:
        if selector.family == family:
            return offset + selector.direction
        offset += family
    raise AssertionError("validated family was not found")


def _reverse_bits(byte: int) -> int:
    byte = ((byte & 0xF0) >> 4) | ((byte & 0x0F) << 4)
    byte = ((byte & 0xCC) >> 2) | ((byte & 0x33) << 2)
    return ((byte & 0xAA) >> 1) | ((byte & 0x55) << 1)


def _predict(history: bytearray, selector: ViewSelector) -> int:
    lag = PRIME_LAGS[_direction_ordinal(selector)]
    predicted = history[-lag] if len(history) >= lag else 0
    if selector.traversal is Traversal.ANTI:
        predicted = _reverse_bits(predicted)
    return predicted


def _remember(history: bytearray, byte: int) -> None:
    history.append(byte)
    if len(history) > MAX_PRIME_LAG:
        del history[: len(history) - MAX_PRIME_LAG]


def project_block(
    block: bytes, prefix: bytes | bytearray, selector: ViewSelector
) -> bytes:
    """Project a block into an exact residual using prefix-only predictions."""
    selector.validate()
    history = bytearray(prefix[-MAX_PRIME_LAG:])
    residual = bytearray()
    for byte in block:
        predicted = _predict(history, selector)
        if selector.projection is Projection.A:
            residual.append(byte ^ predicted)
        else:
            residual.append((byte - predicted) & 0xFF)
        _remember(history, byte)
    return bytes(residual)


def restore_block(
    residual: bytes, prefix: bytes | bytearray, selector: ViewSelector
) -> bytes:
    selector.validate()
    history = bytearray(prefix[-MAX_PRIME_LAG:])
    restored = bytearray()
    for value in residual:
        predicted = _predict(history, selector)
        if selector.projection is Projection.A:
            byte = value ^ predicted
        else:
            byte = (value + predicted) & 0xFF
        restored.append(byte)
        _remember(history, byte)
    return bytes(restored)


def _digest_bytes(value: bytes | str) -> bytes:
    if isinstance(value, bytes):
        return value
    try:
        decoded = bytes.fromhex(value)
    except ValueError as error:
        raise CodecError("catalog digest is not hexadecimal") from error
    if len(decoded) != 32:
        raise CodecError("catalog digest is not SHA-256 sized")
    return decoded


def _catalog_digest(first: bytes | str, second: bytes | str) -> bytes:
    first_bytes = _digest_bytes(first)
    second_bytes = _digest_bytes(second)
    framed = (
        b"ASOLARIA-GLYPH-CATALOG-PAIR-V1\x00"
        + len(first_bytes).to_bytes(4, "big")
        + first_bytes
        + len(second_bytes).to_bytes(4, "big")
        + second_bytes
    )
    return hashlib.sha256(framed).digest()


def _selector_score(
    earlier_prefix: bytes, previous_block: bytes, selector: ViewSelector
) -> tuple[int, int, int, ViewSelector]:
    sample = previous_block[:SCORE_SAMPLE_BYTES]
    residual = project_block(sample, earlier_prefix, selector)
    encoded = lzw_encode(residual, alphabet_size=256, capacity=1024)
    nonzero = sum(value != 0 for value in residual)
    transitions = sum(left != right for left, right in zip(residual, residual[1:]))
    return (len(encoded.codes), nonzero, transitions, selector)


def select_view(earlier_prefix: bytes, previous_block: bytes) -> ViewSelector:
    """Choose the next view only from an already decoded previous block."""
    if not previous_block:
        return ALL_VIEW_SELECTORS[0]
    return min(
        ALL_VIEW_SELECTORS,
        key=lambda selector: _selector_score(earlier_prefix, previous_block, selector),
    )


def _block_omega(
    prior_omega: bytes,
    *,
    index: int,
    raw_len: int,
    mode: int,
    selector: ViewSelector,
    level1_count: int,
    level2_count: int,
    body_len: int,
    decoded_sha: bytes,
    body_sha: bytes,
    catalog_digest: bytes,
) -> bytes:
    canonical = struct.pack(
        ">IIBBBBBIII",
        index,
        raw_len,
        mode,
        selector.family,
        selector.direction,
        int(selector.traversal),
        int(selector.projection),
        level1_count,
        level2_count,
        body_len,
    )
    material = (
        b"ASOLARIA-ACER-BLOCK-OMEGA-V1\x00"
        + prior_omega
        + canonical
        + decoded_sha
        + body_sha
        + catalog_digest
    )
    return hashlib.sha256(material).digest()


def _make_report(
    source: bytes,
    archive: bytes,
    block_reports: Iterable[BlockReport],
    selector_evaluations: int,
    final_omega: bytes,
) -> CodecReport:
    blocks = tuple(block_reports)
    return CodecReport(
        original_bytes=len(source),
        archive_bytes=len(archive),
        block_count=len(blocks),
        raw_blocks=sum(block.mode == "RAW_RESIDUAL" for block in blocks),
        glyph_blocks=sum(block.mode == "GLYPH_LZW2" for block in blocks),
        selector_candidates=DIRECTION_CANDIDATES,
        selector_evaluations=selector_evaluations,
        final_unified_omega=final_omega.hex(),
        source_sha256=hashlib.sha256(source).hexdigest(),
        blocks=blocks,
    )


def encode_with_report(
    source: bytes | bytearray | memoryview, *, block_size: int = DEFAULT_BLOCK_SIZE
) -> tuple[bytes, CodecReport]:
    if not isinstance(source, (bytes, bytearray, memoryview)):
        raise CodecError("source must be bytes-like")
    if type(block_size) is not int:
        raise CodecError("block size must be a plain integer")
    source = bytes(source)
    if not 1 <= block_size <= MAX_BLOCK_SIZE:
        raise CodecError("block size is outside the supported range")
    if len(source) > MAX_OUTPUT_BYTES:
        raise CodecError("source exceeds the research-cell output cap")
    block_count = (len(source) + block_size - 1) // block_size
    if block_count > MAX_BLOCK_COUNT:
        raise CodecError("source would exceed the block-count cap")

    archive = bytearray(
        # The derived genesis binds block_size into every later
        # Omega link; changing only the header can therefore never be accepted.
        HEADER.pack(
            MAGIC,
            VERSION,
            FLAGS,
            block_size,
            CONFIG_COMMITMENT,
            _genesis_omega(block_size),
        )
    )
    prior_omega = _genesis_omega(block_size)
    previous_block = b""
    previous_start = 0
    body_total = 0
    block_reports: list[BlockReport] = []
    selector_evaluations = 0

    for index, start in enumerate(range(0, len(source), block_size)):
        block = source[start : start + block_size]
        earlier_prefix = source[
            max(0, previous_start - MAX_PRIME_LAG) : previous_start
        ]
        selector = select_view(earlier_prefix, previous_block)
        if previous_block:
            selector_evaluations += DIRECTION_CANDIDATES

        residual = project_block(
            block, source[max(0, start - MAX_PRIME_LAG) : start], selector
        )
        level1 = lzw_encode(residual, alphabet_size=256, capacity=1024)
        level2 = lzw_encode(level1.codes, alphabet_size=1024, capacity=4096)
        glyph_body = pack_codes(level2.codes, width=12)
        glyph_catalog = _catalog_digest(level1.catalog_digest, level2.catalog_digest)

        if len(glyph_body) < len(residual):
            mode = MODE_GLYPH_LZW2
            body = glyph_body
            level1_count = len(level1.codes)
            level2_count = len(level2.codes)
            catalog_digest = glyph_catalog
            mode_label = "GLYPH_LZW2"
        else:
            mode = MODE_RAW_RESIDUAL
            body = residual
            level1_count = 0
            level2_count = 0
            catalog_digest = RAW_CATALOG_DIGEST
            mode_label = "RAW_RESIDUAL"

        decoded_sha = hashlib.sha256(block).digest()
        body_sha = hashlib.sha256(body).digest()
        omega = _block_omega(
            prior_omega,
            index=index,
            raw_len=len(block),
            mode=mode,
            selector=selector,
            level1_count=level1_count,
            level2_count=level2_count,
            body_len=len(body),
            decoded_sha=decoded_sha,
            body_sha=body_sha,
            catalog_digest=catalog_digest,
        )
        fixed = BLOCK_FIXED.pack(
            index,
            len(block),
            mode,
            selector.family,
            selector.direction,
            int(selector.traversal),
            int(selector.projection),
            0,
            level1_count,
            level2_count,
            len(body),
            decoded_sha,
            body_sha,
            catalog_digest,
            omega,
        )
        archive.extend(RECORD_LENGTH.pack(len(fixed) + len(body)))
        archive.extend(fixed)
        archive.extend(body)
        body_total += len(body)
        block_reports.append(
            BlockReport(
                index=index,
                raw_bytes=len(block),
                body_bytes=len(body),
                mode=mode_label,
                selector=selector,
                level1_codes=level1_count,
                level2_codes=level2_count,
                omega=omega.hex(),
            )
        )
        prior_omega = omega
        previous_block = block
        previous_start = start

    archive.extend(RECORD_LENGTH.pack(0))
    archive.extend(
        FOOTER.pack(
            FOOTER_MAGIC,
            len(block_reports),
            len(source),
            body_total,
            hashlib.sha256(source).digest(),
            prior_omega,
        )
    )
    frozen = bytes(archive)
    return frozen, _make_report(
        source, frozen, block_reports, selector_evaluations, prior_omega
    )


def encode(
    source: bytes | bytearray | memoryview, *, block_size: int = DEFAULT_BLOCK_SIZE
) -> bytes:
    return encode_with_report(source, block_size=block_size)[0]


def _read_exact(view: memoryview, start: int, length: int, label: str) -> tuple[memoryview, int]:
    end = start + length
    if length < 0 or end < start or end > len(view):
        raise CodecError(f"truncated {label}")
    return view[start:end], end


def decode_with_report(
    archive: bytes | bytearray | memoryview, *, max_output_bytes: int = MAX_OUTPUT_BYTES
) -> tuple[bytes, CodecReport]:
    if not isinstance(archive, (bytes, bytearray, memoryview)):
        raise CodecError("archive must be bytes-like")
    if len(archive) > MAX_ARCHIVE_BYTES:
        raise CodecError("archive exceeds the research-cell input cap")
    if type(max_output_bytes) is not int:
        raise CodecError("output cap must be a plain integer")
    if not 0 <= max_output_bytes <= MAX_OUTPUT_BYTES:
        raise CodecError("invalid output cap")
    frozen = bytes(archive)
    view = memoryview(frozen)
    header_bytes, position = _read_exact(view, 0, HEADER.size, "header")
    magic, version, flags, block_size, config, genesis = HEADER.unpack(header_bytes)
    if magic != MAGIC or version != VERSION or flags != FLAGS:
        raise CodecError("unsupported archive header")
    if not 1 <= block_size <= MAX_BLOCK_SIZE:
        raise CodecError("invalid block size")
    if config != CONFIG_COMMITMENT or genesis != _genesis_omega(block_size):
        raise CodecError("codec configuration commitment mismatch")

    output = bytearray()
    prior_omega = genesis
    previous_block = b""
    previous_start = 0
    body_total = 0
    block_reports: list[BlockReport] = []
    selector_evaluations = 0

    while True:
        length_bytes, position = _read_exact(
            view, position, RECORD_LENGTH.size, "record length"
        )
        (record_len,) = RECORD_LENGTH.unpack(length_bytes)
        if record_len == 0:
            break
        if previous_block and len(previous_block) != block_size:
            raise CodecError("a short block must be the final block")
        if record_len < BLOCK_FIXED.size or record_len > BLOCK_FIXED.size + MAX_BLOCK_SIZE:
            raise CodecError("record length is outside the supported range")
        record, position = _read_exact(view, position, record_len, "block record")
        fixed = record[: BLOCK_FIXED.size]
        body = bytes(record[BLOCK_FIXED.size :])
        (
            index,
            raw_len,
            mode,
            family,
            direction,
            traversal_code,
            projection_code,
            reserved,
            level1_count,
            level2_count,
            body_len,
            decoded_sha,
            body_sha,
            catalog_digest,
            omega,
        ) = BLOCK_FIXED.unpack(fixed)
        if index != len(block_reports):
            raise CodecError("non-canonical block index")
        if index >= MAX_BLOCK_COUNT:
            raise CodecError("block-count cap exceeded")
        if reserved != 0:
            raise CodecError("reserved block byte is nonzero")
        if not 1 <= raw_len <= block_size:
            raise CodecError("invalid block output length")
        if len(output) + raw_len > max_output_bytes:
            raise CodecError("decoded output would exceed the configured cap")
        if body_len != len(body) or hashlib.sha256(body).digest() != body_sha:
            raise CodecError("block body length or hash mismatch")
        try:
            selector = ViewSelector(
                family,
                direction,
                Traversal(traversal_code),
                Projection(projection_code),
            )
            selector.validate()
        except ValueError as error:
            raise CodecError("invalid block selector") from error

        earlier_prefix = bytes(
            output[max(0, previous_start - MAX_PRIME_LAG) : previous_start]
        )
        expected_selector = select_view(earlier_prefix, previous_block)
        if selector != expected_selector:
            raise CodecError("selector was not regenerated from the decoded prefix")
        if previous_block:
            selector_evaluations += DIRECTION_CANDIDATES

        if mode == MODE_RAW_RESIDUAL:
            if level1_count != 0 or level2_count != 0:
                raise CodecError("raw block carries glyph counts")
            if body_len != raw_len or catalog_digest != RAW_CATALOG_DIGEST:
                raise CodecError("raw block grammar is non-canonical")
            residual = body
            mode_label = "RAW_RESIDUAL"
        elif mode == MODE_GLYPH_LZW2:
            if level1_count == 0 or level2_count == 0:
                raise CodecError("glyph block has empty code counts")
            if level1_count > raw_len or level2_count > level1_count:
                raise CodecError("glyph code counts exceed causal bounds")
            if body_len != (level2_count * 12 + 7) // 8:
                raise CodecError("glyph body length does not match its 12-bit count")
            try:
                top = unpack_codes(body, count=level2_count, width=12)
                second = lzw_decode(
                    top,
                    alphabet_size=1024,
                    capacity=4096,
                    max_output_symbols=level1_count,
                )
                if len(second.symbols) != level1_count:
                    raise CodecError("level-2 output count mismatch")
                first = lzw_decode(
                    second.symbols,
                    alphabet_size=256,
                    capacity=1024,
                    max_output_symbols=raw_len,
                )
            except (TypeError, ValueError) as error:
                if isinstance(error, CodecError):
                    raise
                raise CodecError("invalid glyph-coded block") from error
            if len(first.symbols) != raw_len or any(value > 255 for value in first.symbols):
                raise CodecError("level-1 output count or alphabet mismatch")
            rebuilt_digest = _catalog_digest(
                first.catalog_digest, second.catalog_digest
            )
            if rebuilt_digest != catalog_digest:
                raise CodecError("rebuilt catalog digest mismatch")
            residual = bytes(first.symbols)
            mode_label = "GLYPH_LZW2"
        else:
            raise CodecError("unknown block mode")

        block = restore_block(residual, output, selector)
        if len(block) != raw_len or hashlib.sha256(block).digest() != decoded_sha:
            raise CodecError("decoded block length or hash mismatch")
        expected_omega = _block_omega(
            prior_omega,
            index=index,
            raw_len=raw_len,
            mode=mode,
            selector=selector,
            level1_count=level1_count,
            level2_count=level2_count,
            body_len=body_len,
            decoded_sha=decoded_sha,
            body_sha=body_sha,
            catalog_digest=catalog_digest,
        )
        if omega != expected_omega:
            raise CodecError("block Omega chain mismatch")

        output.extend(block)
        body_total += body_len
        block_reports.append(
            BlockReport(
                index=index,
                raw_bytes=raw_len,
                body_bytes=body_len,
                mode=mode_label,
                selector=selector,
                level1_codes=level1_count,
                level2_codes=level2_count,
                omega=omega.hex(),
            )
        )
        prior_omega = omega
        previous_block = block
        previous_start = len(output) - len(block)

    footer_bytes, position = _read_exact(view, position, FOOTER.size, "footer")
    if position != len(view):
        raise CodecError("trailing bytes after footer")
    footer_magic, block_count, original_len, charged_body_total, source_sha, final_omega = FOOTER.unpack(
        footer_bytes
    )
    if footer_magic != FOOTER_MAGIC:
        raise CodecError("invalid footer magic")
    if block_count != len(block_reports) or original_len != len(output):
        raise CodecError("footer count or output length mismatch")
    if charged_body_total != body_total:
        raise CodecError("footer body-byte census mismatch")
    if hashlib.sha256(output).digest() != source_sha:
        raise CodecError("final source hash mismatch")
    if final_omega != prior_omega:
        raise CodecError("final Unified Omega mismatch")

    restored = bytes(output)
    return restored, _make_report(
        restored, frozen, block_reports, selector_evaluations, prior_omega
    )


def decode(
    archive: bytes | bytearray | memoryview, *, max_output_bytes: int = MAX_OUTPUT_BYTES
) -> bytes:
    return decode_with_report(archive, max_output_bytes=max_output_bytes)[0]


def completed_block_prefix(archive: bytes, block_count: int) -> bytes:
    """Return header plus exactly ``block_count`` complete records for tests."""
    if type(block_count) is not int:
        raise CodecError("block count must be a plain integer")
    if block_count < 0:
        raise CodecError("block count cannot be negative")
    view = memoryview(archive)
    _, position = _read_exact(view, 0, HEADER.size, "header")
    for _ in range(block_count):
        length_bytes, after_length = _read_exact(
            view, position, RECORD_LENGTH.size, "record length"
        )
        (record_len,) = RECORD_LENGTH.unpack(length_bytes)
        if record_len == 0:
            raise CodecError("requested prefix exceeds archive blocks")
        _, position = _read_exact(view, after_length, record_len, "block record")
    return bytes(view[:position])
