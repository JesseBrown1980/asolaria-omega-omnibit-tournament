# Relic tournament lane

The Relic lane implements a bounded executable baseline over the shared
tournament contract. It does not read the Relic filesystem, a corpus, a model,
or a private matrix. Inputs must be public fixtures or already approved derived
commitments.

## Engine shape

Each reflection field compiles the same declared topology:

- recursive floors: 64, 256, 1024, 4096;
- direction families per floor: 8 RNQ, 12 TRI, and 20 PI_LENS;
- 40 logical cube descriptors per floor;
- 160 cube descriptors per field;
- 320 descriptors across fields A and B;
- 27 public Omega binding commitments and one unified root.

A cube is a deterministic routing descriptor. It is not a glyph level and it is
not an independent truth copy. The engine commits the full route, then fuses
the route into one reversible stream transform per field. This avoids applying
320 full payload passes and keeps runtime linear in payload size.

## Dual-field law

Fields A and B have different route roots and produce different encoded byte
streams. Either field must restore the source exactly. Reunification decodes
both fields independently and fails closed unless the restored bytes match.

The A/B to NORMAL/ANTI interpretation remains unresolved. The code does not
silently assign that meaning.

## Causality and accounting

The stream mask depends on the public route and Omega commitments, not on
future source bytes. Changing a suffix therefore cannot rewrite an encoded
prefix. Chunk boundaries do not change output.

The receipt counts the two field payloads and public manifest. Decoder bytes
remain explicitly UNCOUNTED in this baseline, so Hutter eligibility is false.
No compression, whole-Wikipedia replay, physical-quantum effect, or prize
result is claimed.

## Evidence transition

The branch begins at IMPLEMENTED_PENDING_CI. It may move to MEASURED only after
the shared workflow reproduces:

- four floors and 40 directions per floor;
- exactly 27 plus one Omega commitments;
- distinct A/B payloads;
- exact decode and byte-identical reunification;
- chunk-boundary invariance;
- causal prefix behavior;
- fail-closed tamper detection;
- a path-free, payload-free HBP receipt;
- the repository privacy gate.
