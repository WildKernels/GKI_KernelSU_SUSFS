#!/usr/bin/env python3
"""Explain ABI drift by comparing each differing symbol against the ABI oracles
of the release before and the release after the tree being built.

Motivation: a 5.10.185 leg fails on `is_ashmem_file` while ashmem.c is identical
to the next release's. A single oracle can be stale or can be generated with a
different toolchain; the neighbouring releases show which value the codebase
actually converged on, which is the difference between "our build diverged" and
"this tree's ABI file was never regenerated".

The ABI files are immutable per tag, so this is reproducible:
  android/abi_gki_aarch64.xml   (5.10 / 5.15 era, crc as an elf-symbol attribute)
  gki/aarch64/abi.stg           (6.1+ era, crc: 0x... + name: "...")

Called by the ABI gate only when drift was found; it prints and returns 0 so it
never changes the gate's verdict.

Usage:
  abi_neighbour_diff.py --family android12-5.10 --date 2023-09 \
      --drift /tmp/drift.tsv [--max-symbols 10]
"""

import argparse
import base64
import os
import re
import subprocess
import sys
import urllib.request

REPO = "https://android.googlesource.com/kernel/common"
GS = REPO + "/+/{ref}/{path}?format=TEXT"
PATHS = ("android/abi_gki_aarch64.xml", "gki/aarch64/abi.stg")


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, shell=True).stdout


def family_tags(family):
    """{branch: highest r} for the monthly releases of one family, date order."""
    out = sh(f"git ls-remote --tags {REPO} 'refs/tags/{family}-*'")
    best = {}
    for line in out.splitlines():
        m = re.search(r"refs/tags/(.+)_r(\d+)$", line.strip())
        if not m:
            continue
        branch, r = m.group(1), int(m.group(2))
        rest = branch[len(family) + 1:] if branch.startswith(family + "-") else ""
        if not re.fullmatch(r"\d{4}-\d{2}", rest):
            continue
        best[branch] = max(best.get(branch, 0), r)
    return dict(sorted(best.items()))


def abi_crcs(tag):
    for path in PATHS:
        try:
            raw = urllib.request.urlopen(GS.format(ref=f"refs/tags/{tag}", path=path), timeout=120).read()
            text = base64.b64decode(raw).decode("utf-8", "replace")
        except Exception:
            continue
        if len(text) < 1000:
            continue
        out = {}
        for name, crc in re.findall(r"name='([^']+)'[^>]*crc='(0x[0-9a-fA-F]+)'", text):
            out[name] = crc
        for crc, name in re.findall(r"crc:\s*(0x[0-9a-fA-F]+)\s*\n\s*name:\s*\"([^\"]+)\"", text):
            out[name] = crc
        for name, crc in re.findall(r"name:\s*\"([^\"]+)\"\s*\n\s*crc:\s*(0x[0-9a-fA-F]+)", text):
            out[name] = crc
        if out:
            return path, out
    return None, {}


def norm(crc):
    try:
        return "0x%08x" % int(crc, 16)
    except Exception:
        return crc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", required=True)
    ap.add_argument("--date", required=True, help="YYYY-MM of the release being built")
    ap.add_argument("--drift", required=True, help="symbol<TAB>ours<TAB>stock file")
    ap.add_argument("--max-symbols", type=int, default=10)
    args = ap.parse_args()

    if not re.fullmatch(r"\d{4}-\d{2}", args.date):
        print(f"ABI neighbours: build date '{args.date}' is not a monthly release - skipping")
        return 0
    if not os.path.exists(args.drift):
        print("ABI neighbours: no drift file to explain")
        return 0

    rows = []
    with open(args.drift, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                rows.append((parts[0], norm(parts[1]), norm(parts[2])))
    if not rows:
        return 0
    if len(rows) > args.max_symbols:
        print(f"ABI neighbours: showing the first {args.max_symbols} of {len(rows)} differing symbols")
        rows = rows[:args.max_symbols]

    tags = family_tags(args.family)
    want = f"{args.family}-{args.date}"
    if want not in tags:
        print(f"ABI neighbours: no upstream tags for {want} - skipping")
        return 0
    names = list(tags)
    idx = names.index(want)
    window = names[max(0, idx - 1): idx + 2]
    labels = {}
    for i, branch in enumerate(window):
        role = "current" if branch == want else ("previous" if names.index(branch) < idx else "next")
        labels[branch] = role

    print()
    print(f"ABI neighbours for {want} (stock oracle per release, immutable tags):")
    crcs = {}
    for branch in window:
        tag = f"{branch}_r{tags[branch]}"
        path, table = abi_crcs(tag)
        crcs[branch] = table
        print(f"  {labels[branch]:<8} {branch:<28} {tag.split('_r')[-1]:>3}  {(path or '-'):<30} {len(table)} symbols")

    print()
    print(f"{'symbol':<40} {'ours':<12} {'this tree':<12} {'previous':<12} {'next':<12} verdict")
    for sym, ours, stock in rows:
        prev = next_b = "-"
        for branch in window:
            role = labels[branch]
            val = crcs[branch].get(sym)
            val = norm(val) if val else "-"
            if role == "previous":
                prev = val
            elif role == "next":
                next_b = val
        verdict = []
        if prev == ours:
            verdict.append("ours == previous release")
        if next_b == ours:
            verdict.append("ours == next release")
        if not verdict:
            verdict.append("ours matches neither neighbour")
        print(f"{sym:<40} {ours:<12} {stock:<12} {prev:<12} {next_b:<12} {'; '.join(verdict)}")

    print()
    print("Reading: 'ours == next release' with an unchanged source file means this")
    print("tree's ABI file was never regenerated - a stale oracle, not our drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
