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
KCONFIG_ENTRY = re.compile(r"^[ \t]*(?:menu)?config[ \t]+([A-Za-z0-9_]+)")

NOT_SET = re.compile(r"^(?:# CONFIG_[A-Za-z0-9_]+ is not set|CONFIG_[A-Za-z0-9_]+=n)$")


# Root implementations live either symlinked into the tree (drivers/kernelsu)
# or beside it as their own checkout (kernel/BakaSU, kernel/KernelSU, ...).
KSU_CHECKOUTS = (
    "KernelSU",
    "KernelSU-Next",
    "BakaSU",
    "SukiSU-Ultra",
    "KowSU",
    "FinaSU",
)


def scan_roots() -> list[str]:
    roots = ["."]
    for name in KSU_CHECKOUTS:
        for candidate in (f"../{name}", f"./{name}"):
            if os.path.isdir(candidate):
                roots.append(candidate)
                break
    return roots


def _walk_all(root: str, visited: set[str]):
    """os.walk over one or more roots (colon-free list in root), link-safe."""
    for base in root.split(os.pathsep):
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base, followlinks=True):
            real = os.path.realpath(dirpath)
            if real in visited:
                dirnames[:] = []
                continue
            visited.add(real)
            dirnames[:] = [
                d for d in dirnames if d not in {"out", ".git", "bazel-out", "bazel-bin"}
            ]
            yield dirpath, dirnames, filenames


def declared_symbols(root: str = ".") -> set[str] | None:
    """Every symbol the tree declares in a Kconfig file, or None if unreadable.

    Kleaf's fragment check rejects a symbol the tree does not declare
    (``ERROR: CONFIG_X: actual '', expected 'CONFIG_X=y' ... Are they declared
    in Kconfig?``) and the error names the fragment, not the patch or the step
    that contributed it. Every Kconfig* file is scanned once, whatever depth.
    """
    names: set[str] = set()
    seen_any = False
    visited: set[str] = set()
    # followlinks: the root implementation (KernelSU / BakaSU / ...) is symlinked
    # into the tree, so its Kconfig lives outside this directory. Without this the
    # scan misses CONFIG_KSU, every CONFIG_KSU_SUSFS_* and CONFIG_BBG, and the
    # prune silently strips them. visited guards against link cycles.
    for dirpath, _dirnames, filenames in _walk_all(root, visited):
        for name in filenames:
            if not name.startswith("Kconfig"):
                continue
            seen_any = True
            try:
                with open(os.path.join(dirpath, name), encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        # Entries inside a choice are indented with a tab, e.g.
                        # "\tconfig DEFAULT_BBR" in net/ipv4/Kconfig, so the
                        # keyword cannot be anchored to column 0.
                        match = KCONFIG_ENTRY.match(line)
                        if match:
                            names.add("CONFIG_" + match.group(1))
            except OSError:
                continue
    return names if seen_any else None


def filter_undeclared(symbols: dict[str, str], declared: set[str], label: str) -> dict[str, str]:
    """Drop entries the tree cannot honour, so Kleaf never sees them."""
    kept: dict[str, str] = {}
    for key, line in symbols.items():
        if key in declared:
            kept[key] = line
            continue
        if NOT_SET.match(line):
            print(f"note: {label}: {key} is not declared here and it asks for 'off' - dropped (absence is off)")
        else:
            print(
                f"WARNING: {label}: {key} is not declared in any Kconfig here - dropped "
                f"({line}); the tree's version does not have this symbol"
            )
    return kept



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
    parser.add_argument("source", nargs="?", help="fragment to append, or - for stdin")
    parser.add_argument("--dest", default="common/wild_defconfig.fragment")
    parser.add_argument("--label", default=None, help="name shown in the log")
    parser.add_argument(
        "--prune",
        action="store_true",
        help="drop entries whose symbol the tree does not declare, then exit",
    )
    args = parser.parse_args()

    if args.prune:
        # Run this once every patch has landed: a symbol a patch adds later is
        # not declared yet when the entry is appended, so the check cannot live
        # in the append path (it would drop CONFIG_DEFAULT_BBR and friends).
        existing = read_symbols(args.dest)
        declared = declared_symbols(os.pathsep.join(scan_roots()))
        if declared is None:
            print("WARNING: no Kconfig files found here - cannot check declarations")
            return
        kept = filter_undeclared(existing, declared, "prune")
        # Tail entries can predate the normalisation above (or come from a file
        # that was written by hand), so apply the same '=n' rewrite here.
        for key, line in list(kept.items()):
            if line.endswith("=n"):
                kept[key] = f"# {key} is not set"
        with open(args.dest, "w", encoding="utf-8") as fh:
            fh.write("\n".join(kept.values()) + "\n")
        print(
            f"prune -> {args.dest}: {len(existing) - len(kept)} undeclared dropped, "
            f"{len(kept)} symbol(s) kept"
        )
        return

    if not args.source:
        sys.exit("ERROR: need a source fragment (or use --prune)")

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
            # Kleaf's own check (build/kernel/kleaf/impl/config_utils.bzl) greps
            # .config for the symbol and then blanks the value only for the
            # '# CONFIG_X is not set' spelling, so a literal 'CONFIG_X=n' can
            # never match: .config holds the comment form for a bool that is off
            # and the check compares 'CONFIG_X=n' against ''. Write the form the
            # checker understands.
            if item.endswith("=n"):
                item = f"# {key} is not set"
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
        f"{skipped} non-config line(s) skipped, "
        f"{len(symbols)} symbol(s) total (was {before})"
    )


if __name__ == "__main__":
    main()
