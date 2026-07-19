"""Typed glyph primitives and a bounded, deterministic integer LZW codec.

This module is deliberately a codec primitive, not a claim that an Omega
binding or catalog digest contains uncounted decoder state.  A caller can use
the same engine for the 256 -> 1024 and 1024 -> 4096 catalog rungs by changing
``alphabet_size`` and ``capacity``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

TUPLE_DIM = 60
MAX_STREAM_SYMBOLS = 1_000_000
MAX_PACKED_CODES = 1_000_000
MAX_ALPHABET_SIZE = 65_536
MAX_CATALOG_CAPACITY = 65_536
MAX_CODE_WIDTH = 32
MIN_TUPLE_VALUE = -(1 << 63)
MAX_TUPLE_VALUE = (1 << 63) - 1


class GlyphRole(str, Enum):
    """Semantic type of a glyph in the public language layer."""

    NOUN = "NOUN"
    WORD = "WORD"


class Verb(str, Enum):
    """Bounded operations understood by the glyph catalog layer."""

    EMIT = "EMIT"
    CONCAT = "CONCAT"
    CATALOG_INSERT = "CATALOG_INSERT"


@dataclass(frozen=True)
class Tuple60:
    """An exact 60-axis integer tuple; no axis is silently added or dropped."""

    axes: tuple[int, ...]

    def __post_init__(self) -> None:
        axes = tuple(self.axes)
        if len(axes) != TUPLE_DIM:
            raise ValueError(f"Tuple60 requires exactly {TUPLE_DIM} axes")
        for value in axes:
            _require_plain_int(value, "tuple axis")
            if not MIN_TUPLE_VALUE <= value <= MAX_TUPLE_VALUE:
                raise ValueError("tuple axis must fit a signed 64-bit integer")
        object.__setattr__(self, "axes", axes)

    @classmethod
    def from_iterable(cls, axes: Iterable[int]) -> "Tuple60":
        return cls(tuple(axes))

    def __len__(self) -> int:
        return TUPLE_DIM


@dataclass(frozen=True)
class FrozenCatalog:
    """Immutable final LZW dictionary shared by an encode/decode receipt."""

    alphabet_size: int
    capacity: int
    entries: tuple[tuple[int, ...], ...]
    digest: str

    @property
    def frozen(self) -> bool:
        return len(self.entries) == self.capacity


@dataclass(frozen=True)
class LzwResult:
    """A complete bounded LZW result and its final catalog commitment."""

    codes: tuple[int, ...]
    symbols: tuple[int, ...]
    catalog: FrozenCatalog

    @property
    def catalog_digest(self) -> str:
        return self.catalog.digest

    @property
    def catalog_size(self) -> int:
        return len(self.catalog.entries)

    @property
    def catalog_frozen(self) -> bool:
        return self.catalog.frozen


def lzw_encode(
    symbols: Iterable[int], alphabet_size: int, capacity: int
) -> LzwResult:
    """Encode integer symbols with deterministic LZW dictionary growth.

    ``capacity`` is the total dictionary size, including the singleton base
    alphabet.  Once it is reached, the dictionary is frozen for the remainder
    of the stream; it is never reset implicitly.
    """

    _validate_catalog_bounds(alphabet_size, capacity)
    source = _bounded_int_tuple(symbols, "symbol", MAX_STREAM_SYMBOLS)
    for symbol in source:
        if not 0 <= symbol < alphabet_size:
            raise ValueError("symbol is outside the base alphabet")

    entries = [(symbol,) for symbol in range(alphabet_size)]
    lookup = {entry: code for code, entry in enumerate(entries)}
    codes: list[int] = []

    if source:
        phrase = (source[0],)
        for symbol in source[1:]:
            candidate = phrase + (symbol,)
            if candidate in lookup:
                phrase = candidate
                continue

            codes.append(lookup[phrase])
            if len(entries) < capacity:
                lookup[candidate] = len(entries)
                entries.append(candidate)
            phrase = (symbol,)

        codes.append(lookup[phrase])

    catalog = _freeze_catalog(alphabet_size, capacity, entries)
    return LzwResult(codes=tuple(codes), symbols=source, catalog=catalog)


def lzw_decode(
    codes: Iterable[int],
    alphabet_size: int,
    capacity: int,
    max_output_symbols: int = MAX_STREAM_SYMBOLS,
) -> LzwResult:
    """Decode a deterministic LZW stream with strict malformed-code checks.

    The standard KwKwK case is accepted only when the code equals the next
    dictionary index and the dictionary still has capacity.  Codes that skip
    an index, reference a frozen-out entry, or begin outside the base alphabet
    are rejected.
    """

    _validate_catalog_bounds(alphabet_size, capacity)
    _require_plain_int(max_output_symbols, "max_output_symbols")
    if not 0 <= max_output_symbols <= MAX_STREAM_SYMBOLS:
        raise ValueError(
            f"max_output_symbols must be in [0, {MAX_STREAM_SYMBOLS}]"
        )

    encoded = _bounded_int_tuple(codes, "code", MAX_PACKED_CODES)
    for code in encoded:
        if not 0 <= code < capacity:
            raise ValueError("code is outside the declared catalog capacity")

    entries = [(symbol,) for symbol in range(alphabet_size)]
    output: list[int] = []
    if not encoded:
        return LzwResult(
            codes=encoded,
            symbols=(),
            catalog=_freeze_catalog(alphabet_size, capacity, entries),
        )

    first_code = encoded[0]
    if first_code >= alphabet_size:
        raise ValueError("first LZW code must name a base-alphabet symbol")

    previous = entries[first_code]
    _extend_bounded(output, previous, max_output_symbols)

    for code in encoded[1:]:
        next_code = len(entries)
        if code < next_code:
            current = entries[code]
        elif code == next_code and next_code < capacity:
            # Standard LZW KwKwK: the encoder just emitted the phrase whose
            # definition is previous + first(previous).
            current = previous + (previous[0],)
        else:
            raise ValueError("invalid LZW code sequence")

        _extend_bounded(output, current, max_output_symbols)
        if len(entries) < capacity:
            entries.append(previous + (current[0],))
        previous = current

    catalog = _freeze_catalog(alphabet_size, capacity, entries)
    return LzwResult(codes=encoded, symbols=tuple(output), catalog=catalog)


def pack_codes(codes: Iterable[int], width: int) -> bytes:
    """Pack fixed-width unsigned codes MSB-first, padding the tail with zeroes."""

    _validate_width(width)
    values = _bounded_int_tuple(codes, "code", MAX_PACKED_CODES)
    limit = 1 << width
    for code in values:
        if not 0 <= code < limit:
            raise ValueError("code does not fit the declared width")

    output = bytearray((len(values) * width + 7) // 8)
    bit_offset = 0
    for code in values:
        for shift in range(width - 1, -1, -1):
            if code & (1 << shift):
                byte_index, bit_index = divmod(bit_offset, 8)
                output[byte_index] |= 1 << (7 - bit_index)
            bit_offset += 1
    return bytes(output)


def unpack_codes(payload: bytes, count: int, width: int) -> tuple[int, ...]:
    """Unpack fixed-width codes and reject length or nonzero-padding drift."""

    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    _require_plain_int(count, "count")
    if not 0 <= count <= MAX_PACKED_CODES:
        raise ValueError(f"count must be in [0, {MAX_PACKED_CODES}]")
    _validate_width(width)

    total_bits = count * width
    expected_bytes = (total_bits + 7) // 8
    if len(payload) != expected_bytes:
        raise ValueError("payload length does not match count and width")

    padding_bits = expected_bytes * 8 - total_bits
    if padding_bits and payload[-1] & ((1 << padding_bits) - 1):
        raise ValueError("fixed-width payload has nonzero padding bits")

    output: list[int] = []
    bit_offset = 0
    for _ in range(count):
        code = 0
        for _ in range(width):
            byte_index, bit_index = divmod(bit_offset, 8)
            code = (code << 1) | ((payload[byte_index] >> (7 - bit_index)) & 1)
            bit_offset += 1
        output.append(code)
    return tuple(output)


def _validate_catalog_bounds(alphabet_size: int, capacity: int) -> None:
    _require_plain_int(alphabet_size, "alphabet_size")
    _require_plain_int(capacity, "capacity")
    if not 1 <= alphabet_size <= MAX_ALPHABET_SIZE:
        raise ValueError(f"alphabet_size must be in [1, {MAX_ALPHABET_SIZE}]")
    if not alphabet_size <= capacity <= MAX_CATALOG_CAPACITY:
        raise ValueError(
            "capacity must be at least alphabet_size and no greater than "
            f"{MAX_CATALOG_CAPACITY}"
        )


def _validate_width(width: int) -> None:
    _require_plain_int(width, "width")
    if not 1 <= width <= MAX_CODE_WIDTH:
        raise ValueError(f"width must be in [1, {MAX_CODE_WIDTH}]")


def _require_plain_int(value: object, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")


def _bounded_int_tuple(
    values: Iterable[int], label: str, limit: int
) -> tuple[int, ...]:
    output: list[int] = []
    for index, value in enumerate(values):
        if index >= limit:
            raise ValueError(f"{label} stream exceeds hard cap of {limit}")
        _require_plain_int(value, label)
        output.append(value)
    return tuple(output)


def _extend_bounded(output: list[int], phrase: tuple[int, ...], limit: int) -> None:
    if len(phrase) > limit - len(output):
        raise ValueError("decoded output exceeds max_output_symbols")
    output.extend(phrase)


def _freeze_catalog(
    alphabet_size: int,
    capacity: int,
    entries: Iterable[tuple[int, ...]],
) -> FrozenCatalog:
    frozen_entries = tuple(tuple(entry) for entry in entries)
    digest = _catalog_digest(alphabet_size, capacity, frozen_entries)
    return FrozenCatalog(
        alphabet_size=alphabet_size,
        capacity=capacity,
        entries=frozen_entries,
        digest=digest,
    )


def _catalog_digest(
    alphabet_size: int,
    capacity: int,
    entries: tuple[tuple[int, ...], ...],
) -> str:
    digest = hashlib.sha256()
    digest.update(b"ASOLARIA-LZW-CATALOG-V1\x00")
    digest.update(alphabet_size.to_bytes(4, "big"))
    digest.update(capacity.to_bytes(4, "big"))
    digest.update(len(entries).to_bytes(4, "big"))
    for code, phrase in enumerate(entries):
        digest.update(code.to_bytes(4, "big"))
        digest.update(len(phrase).to_bytes(8, "big"))
        for symbol in phrase:
            digest.update(symbol.to_bytes(4, "big"))
    return digest.hexdigest()


__all__ = [
    "FrozenCatalog",
    "GlyphRole",
    "LzwResult",
    "MAX_CATALOG_CAPACITY",
    "MAX_CODE_WIDTH",
    "MAX_PACKED_CODES",
    "MAX_STREAM_SYMBOLS",
    "TUPLE_DIM",
    "Tuple60",
    "Verb",
    "lzw_decode",
    "lzw_encode",
    "pack_codes",
    "unpack_codes",
]
