#!/usr/bin/env python3
"""Print '<tag> <path>' for a release whose tree ships a stale ABI oracle.

Reads .github/abi-oracles.json; prints nothing when the release is not listed,
so the caller can fall through to the tree's own ABI file.

Usage: abi_oracle_pick.py <family> <YYYY-MM>
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "..", "abi-oracles.json")


def main() -> int:
    if len(sys.argv) != 3:
        return 0
    family, date = sys.argv[1], sys.argv[2]
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return 0
    entry = data.get(f"{family}-{date}")
    if not isinstance(entry, dict):
        return 0
    tag, path = entry.get("tag"), entry.get("path")
    if tag and path:
        print(tag, path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
