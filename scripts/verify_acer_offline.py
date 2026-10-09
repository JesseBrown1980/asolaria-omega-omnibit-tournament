"""Build and run an isolated-import Acer research decoder bundle.

The subprocess uses Python isolated mode, but the operating system does not
deny network syscalls.  The receipt records that distinction explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from asolaria_tournament.acer_glyph_codec import encode_with_report


DECODER_MAIN = '''from __future__ import annotations
import argparse
from pathlib import Path
from asolaria_tournament.acer_glyph_codec import MAX_ARCHIVE_BYTES, decode

parser = argparse.ArgumentParser()
parser.add_argument("archive", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
archive_bytes = args.archive.stat().st_size
if archive_bytes > MAX_ARCHIVE_BYTES:
    raise SystemExit("archive exceeds the research-cell input cap")
args.output.write_bytes(decode(args.archive.read_bytes()))
'''


def fixture() -> bytes:
    rng = random.Random(0xA50A_2026)
    pseudo_random = bytes(rng.randrange(256) for _ in range(2048))
    language = (
        b"noun verb word tuple catalog recalculates from decoded prefix " * 48
    )
    return language + bytes(range(256)) * 2 + pseudo_random


def build_decoder_bundle(target: Path) -> None:
    entries = {
        "__main__.py": DECODER_MAIN.encode("utf-8"),
        "asolaria_tournament/__init__.py": b"",
        "asolaria_tournament/glyph_program.py": (
            SRC / "asolaria_tournament" / "glyph_program.py"
        ).read_bytes(),
        "asolaria_tournament/acer_glyph_codec.py": (
            SRC / "asolaria_tournament" / "acer_glyph_codec.py"
        ).read_bytes(),
    }
    # Stored entries plus explicit DOS creator metadata make the byte stream
    # independent of host zlib versions and Windows/POSIX creator defaults.
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as bundle:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 0
            info.external_attr = 0
            bundle.writestr(info, entries[name])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--block-size", type=int, default=512)
    args = parser.parse_args()

    source = fixture()
    archive, report = encode_with_report(source, block_size=args.block_size)
    # Keep the temporary cell under the checked-out public tree so managed
    # workspace sandboxes do not silently redirect it to a forbidden user temp.
    with tempfile.TemporaryDirectory(
        prefix=".acer-glyph-offline-", dir=ROOT
    ) as directory:
        cell = Path(directory)
        bundle = cell / "decoder.pyz"
        repeated_bundle = cell / "decoder-repeat.pyz"
        archive_path = cell / "archive.aogc"
        output_path = cell / "restored.bin"
        build_decoder_bundle(bundle)
        build_decoder_bundle(repeated_bundle)
        if bundle.read_bytes() != repeated_bundle.read_bytes():
            print("ACEROFFLINEERROR|reason=DECODER_BUNDLE_NONDETERMINISTIC|json=0")
            return 1
        archive_path.write_bytes(archive)

        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() not in {"PYTHONPATH", "PYTHONHOME"}
        }
        completed = subprocess.run(
            [sys.executable, "-I", str(bundle), str(archive_path), str(output_path)],
            cwd=cell,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=120,
        )
        if completed.returncode != 0:
            sys.stderr.write(completed.stderr.decode("utf-8", errors="replace"))
            return completed.returncode or 1
        restored = output_path.read_bytes()
        if restored != source:
            print("ACEROFFLINEERROR|reason=RESTORED_BYTES_MISMATCH|json=0")
            return 1

        decoder_bytes = bundle.stat().st_size
        compressor_source_bytes = sum(
            path.stat().st_size
            for path in (
                ROOT / "scripts" / "verify_acer_offline.py",
                SRC / "asolaria_tournament" / "glyph_program.py",
                SRC / "asolaria_tournament" / "acer_glyph_codec.py",
            )
        )
        charge = report.charge(
            decoder_artifact_bytes=decoder_bytes,
            external_data_oracle_bytes=0,
        )
        receipt = {
            "schema": "ASOLARIA-ACER-OFFLINE-VERIFY-V1",
            "class": "MEASURED_RESEARCH_CELL",
            "source_bytes": len(source),
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "archive_bytes": len(archive),
            "archive_sha256": hashlib.sha256(archive).hexdigest(),
            "decoder_bundle_bytes": decoder_bytes,
            "decoder_bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
            "decoder_bundle_deterministic": True,
            "compressor_source_bytes_unscored": compressor_source_bytes,
            "external_data_oracle_bytes": 0,
            "research_archive_plus_one_decoder_bytes": charge[
                "research_archive_plus_one_decoder_bytes"
            ],
            "hutter_formula_status": "HELD_INCOMPLETE_ARTIFACT_CENSUS",
            "hutter_relaxed_formula": (
                "compressor+2*decoder+archive+command_line+required_artifacts;"
                "decoder_multiplier=1_if_compressor_equals_decoder"
            ),
            "hutter_default_decoder_multiplier": 2,
            "hutter_same_artifact_decoder_multiplier": 1,
            "command_line_bytes": "UNMEASURED",
            "submission_form": "UNRESOLVED_EXECUTABLE_OR_SOURCE_ZIP",
            "python_runtime_or_source_build_treatment": "UNRESOLVED",
            "raw_blocks": report.raw_blocks,
            "glyph_blocks": report.glyph_blocks,
            "block_count": report.block_count,
            "selector_candidates": report.selector_candidates,
            "final_unified_omega": report.final_unified_omega,
            "python_isolated_mode": True,
            "os_network_deny": False,
            "verification_mode": "PYTHON_ISOLATED_IMPORT_REPLAY",
            "hutter_eligible": False,
            "hutter_blockers": [
                "PYTHON_RUNTIME_NOT_COUNTED",
                "COMPRESSOR_ARTIFACT_NOT_SCORED",
                "COMMAND_LINE_BYTES_UNMEASURED",
                "SUBMISSION_FORM_UNRESOLVED",
                "NETWORK_NOT_OS_DENIED",
                "RESOURCE_LIMIT_NOT_ENWIK9_MEASURED",
            ],
            "exact_restore": True,
        }
        print(json.dumps(receipt, sort_keys=True))
        print(
            "ACEROFFLINEVERIFY|source_bytes={source_bytes}|archive_bytes={archive_bytes}|"
            "decoder_bundle_bytes={decoder_bundle_bytes}|research_archive_plus_one_decoder_bytes={charged}|"
            "external_data_oracle_bytes=0|blocks={blocks}|raw_blocks={raw}|glyph_blocks={glyph}|"
            "exact_restore=PASS|verification_mode=PYTHON_ISOLATED_IMPORT_REPLAY|"
            "os_network_deny=0|hutter_formula_status=HELD|hutter_eligible=0|json=0".format(
                source_bytes=len(source),
                archive_bytes=len(archive),
                decoder_bundle_bytes=decoder_bytes,
                charged=charge["research_archive_plus_one_decoder_bytes"],
                blocks=report.block_count,
                raw=report.raw_blocks,
                glyph=report.glyph_blocks,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
