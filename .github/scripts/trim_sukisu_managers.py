#!/usr/bin/env python3
"""Trim SukiSU-Ultra's manager table to its own signing key.

SukiSU-Ultra hardcodes seven trusted manager certificates in
kernel/manager/apk_sign.c:

    static struct apk_sign_key { unsigned size; const char *sha256; }
    apk_sign_keys[] = {
        { 0x35c, "947ae944…" },  // SukiSU
        { 0x396, "f415f4ed…" },  // RKSU
        { 0x033b, "c371061b…" }, // KSU
        { 0x381, "52d52d8c…" },  // WKSU
        { 0x375, "484fcba6…" },  // KowSU
        { 0x3e6, "79e59011…" },  // KSUN
        { 0x380, "7e0c6d72…" },  // MKSU
    };

`is_manager_apk()` returns true on the first row that matches, so all seven are
trusted equally, and the signature-fallback crowner
(kernel/extension/dynamic_sig_fallback.c) reuses `is_manager_apk()` - meaning a
one-row table also narrows that fallback to the single cert.

Usage:  trim_sukisu_managers.py <path-to-SukiSU-Ultra-checkout>

Fails loudly (exit 1) if the table cannot be found exactly once, if the SukiSU
row is missing, or if the result does not contain exactly one row. There is no
"best effort" mode: a silently mis-trimmed table would ship a kernel that either
trusts too much or trusts nothing.
"""

import re
import sys
from typing import NoReturn

SUKISU_CERT_SIZE = "0x35c"
SUKISU_HASH = "947ae944f3de4ed4c21a7e4f7953ecf351bfa2b36239da37a34111ad29993eef"
EXPECTED_ROWS = 7  # as shipped upstream; a different count means the layout moved

# { 0x35c, "947ae944…" }, // SukiSU      ->  indent | braces | comma | comment
ROW_RE = re.compile(
    r'^(?P<indent>\s*)'
    r'(?P<braces>\{\s*(?:0x[0-9a-fA-F]+|\d+)\s*,\s*"[0-9a-fA-F]{64}"\s*\})'
    r'\s*,?\s*'
    r'(?P<comment>//\s*(?P<name>\S+))?\s*$'
)
TABLE_START_RE = re.compile(r"apk_sign_keys\[\]\s*=\s*\{\s*$")


def fail(msg: str) -> NoReturn:
    sys.exit(f"ERROR: {msg}")


def table_bounds(lines: list[str], what: str) -> tuple[int, int]:
    starts = [i for i, ln in enumerate(lines) if TABLE_START_RE.search(ln)]
    if len(starts) != 1:
        fail(f"{what}: expected exactly one apk_sign_keys[] table, found {len(starts)}")
    start = starts[0]
    for i in range(start + 1, len(lines)):
        if lines[i].strip().startswith("}"):
            return start, i
    fail(f"{what}: could not find the closing brace of apk_sign_keys[]")


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: trim_sukisu_managers.py <path-to-SukiSU-Ultra-checkout>")

    path = f"{sys.argv[1].rstrip('/')}/kernel/manager/apk_sign.c"
    try:
        lines = open(path, encoding="utf-8").read().split("\n")
    except OSError as exc:
        fail(f"cannot read {path}: {exc}")

    start, end = table_bounds(lines, "pre-write")
    rows = [i for i in range(start + 1, end) if ROW_RE.match(lines[i])]
    if len(rows) != EXPECTED_ROWS:
        fail(
            f"expected {EXPECTED_ROWS} certificate rows in {path}, found {len(rows)} "
            "- SukiSU changed the table layout"
        )

    keep = [i for i in rows if SUKISU_HASH in lines[i]]
    if len(keep) != 1:
        fail(f"expected exactly one SukiSU row ({SUKISU_HASH[:8]}...), found {len(keep)}")

    m = ROW_RE.match(lines[keep[0]])
    if m is None:  # pragma: no cover - rows[] was built with the same regex
        fail("internal error: SukiSU row did not match its own pattern")
    # comma before the comment, never inside it
    kept_row = f"{m.group('indent')}{m.group('braces')}," + (
        f" {m.group('comment')}" if m.group("comment") else ""
    )

    out: list[str] = []
    dropped = 0
    for i, ln in enumerate(lines):
        if i == keep[0]:
            out.append(kept_row)
        elif i in rows:
            dropped += 1
        else:
            out.append(ln)
    text = "\n".join(out)
    open(path, "w", encoding="utf-8").write(text)

    # Re-read and verify before declaring success.
    check = open(path, encoding="utf-8").read().split("\n")
    cstart, cend = table_bounds(check, "post-write")
    remaining = [i for i in range(cstart + 1, cend) if ROW_RE.match(check[i])]
    if len(remaining) != 1:
        fail(f"post-write check: expected 1 row, found {len(remaining)}")
    if SUKISU_HASH not in check[remaining[0]]:
        fail("post-write check: the surviving row is not the SukiSU key")
    if "is_manager_apk" not in text:
        fail("post-write check: is_manager_apk() disappeared")

    print(
        f"SukiSU manager table trimmed: {EXPECTED_ROWS} rows -> 1 (dropped {dropped}); "
        f"kept size {SUKISU_CERT_SIZE} {check[remaining[0]].strip()}"
    )


if __name__ == "__main__":
    main()
