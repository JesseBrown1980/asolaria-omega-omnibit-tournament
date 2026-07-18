from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from asolaria_tournament.privacy import violations


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    findings = violations(ROOT)
    for finding in findings:
        print(f"PRIVACY_FAIL|{finding}")
    ok = result.wasSuccessful() and not findings
    print(
        "VERIFY|tests_run={}|tests_ok={}|privacy_findings={}|ok={}|json=0".format(
            result.testsRun,
            int(result.wasSuccessful()),
            len(findings),
            int(ok),
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
