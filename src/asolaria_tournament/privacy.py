"""Repository and receipt privacy gates."""

from __future__ import annotations

import re
from pathlib import Path

FORBIDDEN_TEXT = (
    re.compile(r"(?i)\b[A-Z]:\\" + r"Users\\"),
    re.compile(r"(?i)/" + r"home/[^/\s]+/"),
    re.compile(r"(?i)file:" + r"//"),
    re.compile(r"(?i)(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,})"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)

FORBIDDEN_SUFFIXES = {
    ".gguf",
    ".safetensors",
    ".onnx",
    ".pt",
    ".pth",
    ".key",
    ".pem",
    ".pfx",
    ".p12",
}

SKIP_DIRS = {".git", ".pytest_cache", ".venv", "__pycache__", "target"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def forbidden_text_matches(text: str) -> list[str]:
    return [pattern.pattern for pattern in FORBIDDEN_TEXT if pattern.search(text)]


def violations(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts) or not path.is_file():
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append(f"{relative}: forbidden suffix")
            continue
        if path.stat().st_size > 2_000_000:
            findings.append(f"{relative}: exceeds public artifact limit")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"{relative}: unexpected binary file")
            continue
        for pattern in forbidden_text_matches(text):
            findings.append(f"{relative}: matches {pattern}")
    return findings
