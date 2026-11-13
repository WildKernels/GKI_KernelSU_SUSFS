#!/usr/bin/env python3
"""Check that every config in a fragment actually landed in the built .config.

A fragment is a request, not a promise: olddefconfig drops symbols the tree does not
declare, and silently restores values whose dependencies are off. The build's own
check_defconfig only compares the defconfig on the build.sh path, so this is the
independent verification - it looks at the fragments we wrote and the .config the
kernel was actually configured with.

Lines marked `# nocheck` are skipped, matching Kleaf's own rule for fragment checks.

Usage: verify_fragment.py <fragment> [<fragment> ...] --config <path>
"""

import argparse
import re
import sys

SYMBOL = re.compile(r"^(?:# )?(CONFIG_[A-Za-z0-9_]+)(?:=(.*)| is not set)$")


def parse_config(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            item = line.strip()
            match = SYMBOL.match(item)
            if match:
                values[match.group(1)] = match.group(2) if match.group(2) is not None else "n"
    return values


def parse_fragment(path: str) -> list[tuple[str, str, str]]:
    """Returns (symbol, expected value, raw line) for every checkable entry."""
    entries: list[tuple[str, str, str]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            item = line.strip()
            if "nocheck" in item:
                continue
            match = SYMBOL.match(item)
            if not match:
                continue
            entries.append((match.group(1), match.group(2) if match.group(2) is not None else "n", item))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("fragments", nargs="+")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    actual = parse_config(args.config)
    if not actual:
        sys.exit(f"ERROR: {args.config}: no CONFIG_ entries")

    missing: list[str] = []
    wrong: list[str] = []
    checked = 0
    for fragment in args.fragments:
        for symbol, expected, raw in parse_fragment(fragment):
            checked += 1
            if symbol not in actual:
                # =n is satisfied by absence: a symbol the tree never declares cannot
                # appear in .config, and "not there" is the off state.
                if expected != "n":
                    missing.append(f"{symbol} ({raw})")
            elif actual[symbol] != expected:
                wrong.append(f"{symbol}: wanted {expected}, .config has {actual[symbol]}")

    # Every entry, so the log shows the comparison rather than only its verdict.
    for fragment in args.fragments:
        for symbol, expected, _raw in parse_fragment(fragment):
            got = actual.get(symbol)
            if got is None:
                # A request for =n is satisfied by the symbol being absent: an
                # undeclared symbol cannot appear in .config at all, and that is the
                # off state. Only a request for anything else is a miss.
                if expected == "n":
                    print(f"  ok       {symbol}=n (absent)")
                    continue
                print(f"  MISSING  {symbol}: wanted {expected}, not in .config")
            elif got != expected:
                print(f"  WRONG    {symbol}: wanted {expected}, .config has {got}")
            else:
                print(f"  ok       {symbol}={expected}")


    if wrong or missing:
        print(f"FRAGMENT CHECK FAILED: {len(wrong)} wrong, {len(missing)} missing of {checked} entr(ies)")
        sys.exit(1)

    print(f"FRAGMENT CHECK OK: all {checked} entries present with the requested value")


if __name__ == "__main__":
    main()
