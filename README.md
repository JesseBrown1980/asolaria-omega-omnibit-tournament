# Asolaria Omega Omnibit Tournament

This repository is the clean integration lane for the recursive Omnibit codec,
three-seat formula tournament, and movable-flashlight adapter.

It deliberately separates four things that older work sometimes collapsed:

1. the original 3,200-byte Quant8 tail;
2. recursive representation floors `64 -> 256 -> 1024 -> 4096`;
3. executable glyph/catalog functions and directional Omega commitments; and
4. the complete, charged substrate required for exact reconstruction.

The target is a standalone, causal, lossless Wikipedia codec. The current
baseline is not a Hutter Prize result and makes no physical-quantum claim.

This is a **public SGRAM/GitRAM surface**: code, contracts, source pins,
derived commitments, and reviewed receipts remain publicly streamable. Raw
seat filesystems, corpora, matrices, credentials, and private key material are
excluded; their absence is a privacy boundary, not a private-repository mode.

## Tournament topology

- Seats: Acer, Liris, Relic.
- Each seat keeps its filesystem, corpus, training matrix, and hardware state
  private and non-replicated.
- Git carries only reviewed code, derived commitments, allowlisted receipts,
  public fixtures, and explicit Omega bindings.
- Each seat branch evaluates the operator-specified `NORMAL` and `ANTI`
  traversal views. Three seats times two views gives six public tournament
  vantages without copying a seat-local matrix.
- The flashlight's `A/B` light/dark projection fields remain a separate axis;
  they are not silently renamed NORMAL/ANTI or DBBH/DBWH.

The three tournament branches are:

- `tournament/acer`
- `tournament/liris`
- `tournament/relic`

## Preserved axes

- second-cascade topology: 93,312 nodes per pass;
- symbolic logical-address ceiling: `10^(100,000,000)`;
- executed/harvested population: hundreds of millions, a separate axis;
- reference rungs: 2, 4, 8, 16, 32, 64, 256, 1024, 4096;
- Omega bindings: 27 shared keys plus one Unified Omega key
  (`OPERATOR_SPECIFIED`; exact implementation binding unresolved and counted);
- glyph levels: operator recalls 48 or more; exact enumeration is unresolved;
- view families: 3, 6, 12, 24, pi-like, and N;
- operator candidate piece arities: 5, 12, 14, 48, 96, and further values;
- eight DBBH/DBWH direction ports with signed `-1/+1` traversal are a target
  contract, not yet an implemented proof.

## Baseline

The Python baseline creates privacy-safe tournament manifests and
domain-separated commitments. It never reads a corpus or local matrix.
The exact July 17 light/dark flashlight source and its two pinned helpers are
imported under `tools/movable-flashlight/`. A public lazy-import adaptation
keeps its geometry contract importable without optional plotting packages;
both upstream and adapted hashes are pinned. That instrument computes
10-frame pixel windows; its positive/negative values mean lightening and
darkening, not NORMAL/ANTI reflection fields.

```powershell
python -m pip install -e ".[flashlight]"
python .\scripts\verify.py
python -m asolaria_tournament --config .\config\base.json
```

Set `PYTHONPATH=src` if the package has not been installed.

Reviewed Rust components are imported under `reference/` with their original
layout and source hashes. Integration promotion requires:

1. exact standalone replay;
2. causal suffix-poison tests;
3. every seed/model/catalog/residual byte charged;
4. no network, filesystem, or seat-private side channel;
5. a held-out source hash match.

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[SOURCE-LEDGER.hbp](provenance/SOURCE-LEDGER.hbp).
