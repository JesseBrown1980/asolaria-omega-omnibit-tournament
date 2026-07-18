"""Verify imported public references and both HBP SHA-256 sidecars."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS_PATH = ROOT / "provenance" / "reference-pins.json"
SIDECARS = (
    (
        ROOT / "provenance" / "SOURCE-LEDGER.hbp",
        ROOT / "provenance" / "SOURCE-LEDGER.hbp.sha256",
    ),
    (
        ROOT / "contracts" / "ARCHITECTURE.hbp",
        ROOT / "contracts" / "ARCHITECTURE.hbp.sha256",
    ),
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)
    print(f"PINFAIL|message={message}|json=0")


def verify_pins(failures: list[str]) -> int:
    document = json.loads(PINS_PATH.read_text(encoding="utf-8"))
    pins = document.get("pins")
    expected_files = document.get("expected_files")
    if not isinstance(pins, list):
        fail("pins_not_list", failures)
        return 0
    if expected_files != len(pins):
        fail(f"expected_files_mismatch:{expected_files}:{len(pins)}", failures)

    root_resolved = ROOT.resolve()
    seen: set[str] = set()
    verified = 0
    for index, pin in enumerate(pins, start=1):
        if not isinstance(pin, dict):
            fail(f"pin_not_object:{index}", failures)
            continue
        relative = pin.get("path")
        expected_bytes = pin.get("bytes")
        expected_sha = pin.get("sha256")
        if not isinstance(relative, str) or not relative:
            fail(f"invalid_path:{index}", failures)
            continue
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts or "\\" in relative:
            fail(f"unsafe_path:{relative}", failures)
            continue
        if relative in seen:
            fail(f"duplicate_path:{relative}", failures)
            continue
        seen.add(relative)
        if not isinstance(expected_bytes, int) or expected_bytes < 0:
            fail(f"invalid_byte_count:{relative}", failures)
            continue
        if not isinstance(expected_sha, str) or not SHA256_RE.fullmatch(expected_sha):
            fail(f"invalid_sha256:{relative}", failures)
            continue

        candidate = (ROOT / relative_path).resolve()
        try:
            candidate.relative_to(root_resolved)
        except ValueError:
            fail(f"path_escapes_repository:{relative}", failures)
            continue
        if not candidate.is_file():
            fail(f"missing_file:{relative}", failures)
            continue

        data = candidate.read_bytes()
        actual_sha = sha256(data)
        if len(data) != expected_bytes:
            fail(f"byte_mismatch:{relative}:{expected_bytes}:{len(data)}", failures)
            continue
        if actual_sha != expected_sha:
            fail(f"sha_mismatch:{relative}:{expected_sha}:{actual_sha}", failures)
            continue
        verified += 1
        print(
            f"PINPASS|path={relative}|bytes={len(data)}|sha256={actual_sha}|json=0"
        )
    return verified


def verify_sidecar(target: Path, sidecar_path: Path, failures: list[str]) -> None:
    relative = target.relative_to(ROOT).as_posix()
    sidecar = sidecar_path.read_text(encoding="ascii").strip()
    fields = sidecar.split()
    if len(fields) != 2:
        fail(f"sidecar_format:{relative}", failures)
        return
    expected_sha = fields[0].lower()
    named_file = fields[1].lstrip("*")
    if not SHA256_RE.fullmatch(expected_sha) or named_file != target.name:
        fail(f"sidecar_content:{relative}", failures)
        return
    actual_sha = sha256(target.read_bytes())
    if actual_sha != expected_sha:
        fail(f"sidecar_sha_mismatch:{relative}:{expected_sha}:{actual_sha}", failures)
        return
    print(
        f"SIDECARPASS|path={relative}|sha256={actual_sha}|json=0"
    )


def main() -> int:
    failures: list[str] = []
    verified = verify_pins(failures)
    for target, sidecar in SIDECARS:
        verify_sidecar(target, sidecar, failures)
    ok = not failures
    print(
        f"REFERENCEPINS|files={verified}|failures={len(failures)}|"
        f"ok={int(ok)}|json=0"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
