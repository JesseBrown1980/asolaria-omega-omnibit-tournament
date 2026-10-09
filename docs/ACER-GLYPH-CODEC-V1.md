# Acer glyph recalculation codec v1

This is a `DESIGN` contract for one Python `RESEARCH_CODEC_CELL`. It does not
report compression, a Hutter result, physical quantum execution, or a completed
Rust submission. Its job is to turn the operator's recalculation idea into a
testable, byte-accounted software codec. Rust 1.81.0 is the frozen publication
target; later Rust versions are not authorized for this lane.

## The two catalog stages

The first implementation uses an **online rebuilt catalog**. Each block starts
from fixed singleton base alphabets of 256 symbols for level 1 and 1,024
symbols for level 2. V1 does not implement an empty or custom charged base
catalog. Every update is a deterministic function of bytes in that block.
V1 declares `NOUN`/`WORD` and
`EMIT`/`CONCAT`/`CATALOG_INSERT` types as language scaffolding, but its active
archive contains numeric LZW phrase codes, not semantic glyph opcodes.
`Tuple60` currently proves only the 60-axis shape; learned noun/verb semantics,
emitters, and tuple-command bindings remain held. None of these steps consults
Wikipedia, a seat-local matrix, GitHub, SGRAM, or a live service during decode.

A **later trained mint** is a separate research stage. Training may study
Wikipedia and may mint a stronger glyph grammar, but every table, model,
dictionary, seed, and executable function needed by standalone decoding must be
included in the charged artifact. The target corpus is not free decoder side
information. The trained-mint stage remains held until its serialization and
byte accounting are implemented.

The measured 3,200-byte Quant8 route-tail packet and the operator's separate
"3,200 tuples" catalog hint are not the same quantity. This contract preserves
the packet as 3,200 bytes and records the catalog hint as unresolved; neither is
called a complete reconstruction payload.

## Typed direction cells

The design assigns one causal prime lag to each member of the 6-, 12-, and
24-sector families. Their union has 42 selectors. Crossing that union with two
software residual projections (`A`, `B`) and two traversals (`NORMAL`, `ANTI`)
produces 168 typed cells:

```text
(6 + 12 + 24) * 2 projections * 2 traversals = 168
```

The nested Cartesian proposal is deliberately different:

```text
6 * 12 * 24 * 2 projections * 2 traversals = 6,912
```

Those 6,912 cells are held and are not materialized by v1. Both counts are
independent of the second-cascade body topology:

```text
6 * 6 * 6 * 6 * 6 * 12 = 93,312 nodes per pass
```

No one of these three axes may overwrite another in a receipt.

## Exact software projection semantics

For input byte `x[i]`, the selected prime lag reads only the decoded prefix and
produces the NORMAL predictor byte `p[i]`. Before enough prefix exists, the
predictor uses a fixed zero byte. ANTI uses `bit_reverse_8(p[i])`; it never reads
future input.

The residual fields are:

```text
A residual = x[i] XOR predictor[i]
B residual = (x[i] - predictor[i]) mod 256
```

The inverse operations are exact when the selector and residual are present:

```text
A replay = residual XOR predictor
B replay = (residual + predictor) mod 256
```

These `A` and `B` names describe new deterministic codec projections. They are
not the July 17 movable-flashlight pixel fields, whose A/B values describe image
intensity measurements. An adapter must never merge the two meanings.

## Strict forward-only framed archive

The format is consumed in one direction. The current Python research bundle
checks a 1,500,000,000-byte hard input cap and then reads the archive into
memory; it is not yet a streaming file-I/O implementation. At each record it has only
the decoded prefix, the deterministic catalog rebuilt from that prefix, and
explicit state already read from the archive. A modeled record carries its
selector and residual. A RAW record carries the exact projected residual. RAW
fallback makes the format total even when a glyph-coded residual would not be
shorter.

The selector is prefix-only, explicit, and charged. Garbage collection may
discard only transient state that can be deterministically rebuilt from the
decoded prefix; it may not discard an unresolved distinction. An Omega value
is an unkeyed self-consistency commitment to charged artifacts, not the payload
hidden behind them. Without a separately trusted signed root, it does not
authenticate an archive against an adversary who can rewrite the archive and
recompute all hashes.

The current local receipt's `archive + one decoder` number is a research
metric only. It is not a Hutter score. Under the published rules, a
self-extracting submission charges the compressor plus self-extracting archive.
The separate-compressor relaxation charges:

```text
compressor + 2 * decoder + archive
```

When compressor and decoder are the same artifact, the decoder multiplier may
fall from two to one; the compressor term remains. Required command-line
options are also charged. Before any benchmark claim, the submission form,
runtime/source-build treatment, compressor, decoder, archive, command line,
and every additional required artifact must be resolved and measured.

The complete byte census therefore includes, at minimum:

- the compressor executable or accepted source ZIP/build instructions;
- the current Python decoder bundle and its unresolved runtime/source-build
  treatment;
- the future standalone decoder executable built with Rust 1.81.0;
- archive header, record tags, selectors, residuals, and raw literals;
- catalog or trained-mint state, tables, models, and seeds;
- Omega manifests and every other artifact required for offline replay.

Compression evidence remains `PENDING_CHARGED_BENCHMARK`, and the Hutter
formula remains `HELD_INCOMPLETE_ARTIFACT_CENSUS`, until exact replay and the
complete rule-compliant byte charge are measured together.

## Frozen invariants

- `TARGET_EXACT_REPLAY_WITH_CHARGED_SELECTOR_RESIDUAL`
- `ACCEPTED_DOMAIN_COLLISION_FREE`
- `INTERNAL_PROJECTIONS_MAY_BE_MANY_TO_ONE`
- `RESIDUAL_COMPLETES_DISCARDED_DISTINCTIONS`
- `CATALOG_REBUILT_FROM_DECODED_PREFIX`
- `CAUSAL_STATE_PREFIX_ONLY`
- `SELECTOR_EXPLICIT_AND_CHARGED`
- `OMEGA_SELF_CONSISTENCY_COMMITMENT_NOT_PAYLOAD`
- `ALL_REQUIRED_STATE_COUNTED`
- `GC_SAFE_TRANSIENT_STATE_ONLY`

The accepted target archive states must be collision-free end to end. Internal
views may be many-to-one only because the charged selector/residual or RAW
literal restores every distinction required for exact target replay.

## Quantum terminology boundary

This cell implements ordinary deterministic software. The work referenced as
arXiv:2602.10695 may motivate an architecture analogy, but it is not evidence
that this codec performs a physical quantum operation, clones arbitrary unknown
quantum states, or bypasses the no-cloning theorem. Any later physical claim
requires separate independent evidence and a new contract.
