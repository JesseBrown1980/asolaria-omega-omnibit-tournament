from __future__ import annotations

import argparse
import json
from pathlib import Path

from .tournament import build_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--seat", choices=("acer", "liris", "relic"), default="acer")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    print(json.dumps(build_manifest(config, args.seat), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
