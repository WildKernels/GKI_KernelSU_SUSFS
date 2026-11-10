#!/usr/bin/env python3
"""Append a config fragment to the shared wild fragment, one entry per symbol.

Every step that wants to contribute kernel options appends to the same file
(common/wild_defconfig.fragment by default), which the build then applies as a defconfig
fragment. Doing it through this script instead of `cat >>` means:

  * only real config lines land - comments and blank lines are dropped, and anything
    that is not a CONFIG_ line is reported rather than silently copied
  * the file never holds the same symbol twice: appending a symbol that is already
    there replaces the earlier value, and the change is printed
  * the appending step is named in the output, so a fragment's contents can be traced
    back to the steps that put them there

Usage:
    append_fragment.py <source-fragment> [--dest common/wild_defconfig.fragment] [--label NAME]
"""

import argparse
import os
import re
import sys

SYMBOL = re.compile(r"^(?:# )?(CONFIG_[A-Za-z0-9_]+)(?:=.*| is not set)$")


def read_symbols(path: str) -> dict[str, str]:
    """Existing fragment as symbol -> line, preserving first-appearance order."""
    symbols: dict[str, str] = {}
    if not os.path.exists(path):
        return symbols
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            item = line.strip()
            match = SYMBOL.match(item)
            if match:
                symbols[match.group(1)] = item
    return symbols


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="fragment to append, or - for stdin")
    parser.add_argument("--dest", default="common/wild_defconfig.fragment")
    parser.add_argument("--label", default=None, help="name shown in the log")
    args = parser.parse_args()

    label = args.label or ("stdin" if args.source == "-" else os.path.basename(args.source))
    if args.source == "-":
        lines = sys.stdin.read().splitlines()
    elif not os.path.exists(args.source):
        sys.exit(f"ERROR: {args.source} not found")
    else:
        with open(args.source, encoding="utf-8") as fh:
            lines = fh.read().splitlines()

    symbols = read_symbols(args.dest)
    before = len(symbols)
    added = overridden = skipped = 0

    if True:
        for line in lines:
            item = line.strip()
            if not item or item.startswith("#") and "is not set" not in item:
                continue
            match = SYMBOL.match(item)
            if not match:
                skipped += 1
                continue
            key = match.group(1)
            if key in symbols:
                if symbols[key] != item:
                    print(f"note: {label} overrides {key}: {symbols[key]} -> {item}")
                    overridden += 1
                symbols[key] = item
            else:
                symbols[key] = item
                added += 1

    with open(args.dest, "w", encoding="utf-8") as fh:
        fh.write("\n".join(symbols.values()) + "\n")

    print(
        f"{label} -> {args.dest}: +{added} new, {overridden} overridden, "
        f"{skipped} non-config line(s) skipped, {len(symbols)} symbol(s) total"
        f" (was {before})"
    )


if __name__ == "__main__":
    main()
