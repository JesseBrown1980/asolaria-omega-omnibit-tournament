"""Verify receipt privacy and byte-index integrity without seat-local access."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPTS = ROOT / "provenance" / "receipts"
sys.path.insert(0, str(ROOT / "src"))

from asolaria_tournament.privacy import forbidden_text_matches

MAX_RECEIPT_BYTES = 500_000
ABSOLUTE_WINDOWS_PATH = re.compile(r"(?i)\b[A-Z]:\\")
MOUNTED_WINDOWS_PATH = re.compile(r"(?i)/" + r"mnt/[a-z]/")
PHYSICAL_DEVICE = re.compile(r"(?i)Physical" + r"Drive\d+")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def receipt_kind(path: Path) -> str | None:
    name = path.name.lower()
    if name.endswith((".hbp.sha256", ".hbi.sha256")):
        return "sidecar"
    if name.endswith(".hbp"):
        return "hbp"
    if name.endswith(".hbi"):
        return "hbi"
    return None


def parse_sha256_sidecar(text: str, target_name: str) -> str:
    items = text.strip().split()
    if len(items) != 2:
        raise ValueError("sidecar must contain exactly hash and filename")
    expected_sha = items[0].lower()
    named_file = items[1].lstrip("*")
    if not SHA256_RE.fullmatch(expected_sha):
        raise ValueError("sidecar hash is not lowercase SHA-256")
    if named_file != target_name:
        raise ValueError("sidecar filename does not match target")
    return expected_sha


def verify_sha256_sidecar(sidecar_path: Path, failures: list[str]) -> None:
    relative = sidecar_path.relative_to(ROOT).as_posix()
    target = sidecar_path.with_suffix("")
    if not target.is_file():
        failures.append(f"{relative}: missing sidecar target")
        return
    try:
        expected_sha = parse_sha256_sidecar(
            sidecar_path.read_text(encoding="ascii"), target.name
        )
    except (UnicodeDecodeError, ValueError) as error:
        failures.append(f"{relative}: invalid sidecar: {error}")
        return
    actual_sha = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual_sha != expected_sha:
        failures.append(
            f"{relative}: sidecar hash mismatch {expected_sha} != {actual_sha}"
        )


def fields(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in line.split("|")[1:]:
        if "=" in item:
            key, value = item.split("=", 1)
            result[key] = value
    return result


def verify_hbi(hbi_path: Path, failures: list[str]) -> int:
    hbp_path = hbi_path.with_suffix(".hbp")
    relative = hbi_path.relative_to(ROOT).as_posix()
    if not hbp_path.is_file():
        failures.append(f"{relative}: missing paired HBP")
        return 0
    source = hbp_path.read_bytes()
    rows = 0
    cursor = 0
    for line in hbi_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("HBIROW|"):
            continue
        item = fields(line)
        rows += 1
        try:
            row = int(item["row"])
            offset = int(item.get("off", item.get("offset", "")))
            length = int(item["len"])
            expected_sha = item["sha256"]
        except (KeyError, ValueError):
            failures.append(f"{relative}: malformed row {rows}")
            continue
        if row != rows:
            failures.append(f"{relative}: row sequence {row} != {rows}")
        if offset != cursor:
            failures.append(f"{relative}: offset {offset} != {cursor}")
        chunk = source[offset : offset + length]
        actual_sha = hashlib.sha256(chunk).hexdigest()
        if len(chunk) != length:
            failures.append(f"{relative}: short row {row}")
        if actual_sha != expected_sha:
            failures.append(f"{relative}: hash mismatch row {row}")
        expected_hex = item.get("hex")
        if expected_hex is not None and chunk.hex() != expected_hex.lower():
            failures.append(f"{relative}: hex mismatch row {row}")
        cursor = offset + length
    if rows == 0:
        failures.append(f"{relative}: no HBI rows")
    if cursor != len(source):
        failures.append(f"{relative}: indexed {cursor} of {len(source)} bytes")
    return rows


def main() -> int:
    failures: list[str] = []
    receipt_files = sorted(path for path in RECEIPTS.rglob("*") if path.is_file())
    hbi_pairs = 0
    hbi_rows = 0
    sidecars = 0
    for path in receipt_files:
        relative = path.relative_to(ROOT).as_posix()
        kind = receipt_kind(path)
        if kind is None:
            failures.append(f"{relative}: unexpected receipt suffix")
            continue
        data = path.read_bytes()
        if not data:
            failures.append(f"{relative}: empty receipt")
            continue
        if len(data) > MAX_RECEIPT_BYTES:
            failures.append(f"{relative}: exceeds receipt byte limit")
            continue
        if b"\x00" in data:
            failures.append(f"{relative}: contains NUL byte")
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            failures.append(f"{relative}: is not UTF-8")
            continue
        matches = forbidden_text_matches(text)
        matches.extend(
            label
            for label, pattern in (
                ("absolute_windows_path", ABSOLUTE_WINDOWS_PATH),
                ("mounted_windows_path", MOUNTED_WINDOWS_PATH),
                ("physical_device", PHYSICAL_DEVICE),
            )
            if pattern.search(text)
        )
        for match in matches:
            failures.append(f"{relative}: privacy match {match}")
        if kind == "hbi":
            hbi_pairs += 1
            hbi_rows += verify_hbi(path, failures)
        elif kind == "sidecar":
            sidecars += 1
            verify_sha256_sidecar(path, failures)

    for failure in failures:
        print(f"RECEIPTFAIL|message={failure}|json=0")
    ok = not failures
    print(
        f"RECEIPTPRIVACY|files={len(receipt_files)}|sidecars={sidecars}|"
        f"hbi_pairs={hbi_pairs}|hbi_rows={hbi_rows}|findings={len(failures)}|"
        f"ok={int(ok)}|json=0"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
