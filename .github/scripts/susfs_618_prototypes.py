#!/usr/bin/env python3
"""Declare every non-static function in fs/susfs.c, in place.

6.18 moved -Wmissing-prototypes into the always-on warning set (6.12 only applies
it with W=1, which we never pass), so the vendored 6.12 SUSFS source — which
declares only 19 of its ~40 globals — now fails the build with ~40 of:

  fs/susfs.c:1034:6: error: no previous prototype for function
                    'susfs_spoof_cmdline_or_bootconfig'

Approach: place each prototype directly above its own definition. That keeps it
inside the same preprocessor branch, which matters because some functions are
defined twice with different signatures:

  #if LINUX_VERSION_CODE < KERNEL_VERSION(6,12,0)
  bool susfs_is_inode_sus_path(struct mnt_idmap* idmap, struct inode *inode)
  #else
  bool susfs_is_inode_sus_path(struct inode *inode)
  #endif

A single top-of-file prototype cannot satisfy both (that attempt produced
"conflicting types for 'susfs_is_inode_sus_path'"). Attributes on the definition
line (__attribute__((hot))) are left off the prototype.

If, after inserting, any definition still has no prototype in the lines above it
(an unusual shape this scanner cannot parse), the script falls back to silencing
the warning for this file only, so the build never regresses to a hard failure
for a cosmetic reason. Either way it is idempotent and it reports which path it
took.

Usage: susfs_618_prototypes.py <kernel/common>
"""

import os
import re
import sys
from typing import NoReturn

PROTO_MARKER = "/* 6.18: prototype (added by GKI_KernelSU_SUSFS; -Wmissing-prototypes is on by default) */"
PRAGMA_MARKER = "/* 6.18: silence -Wmissing-prototypes for this vendored file (GKI_KernelSU_SUSFS) */"
SKIP = {"if", "for", "while", "switch", "return", "sizeof", "typeof", "container_of"}
DEF_RE = re.compile(r"^([A-Za-z_][\w \t\*]*?)\b([A-Za-z_]\w*)\s*\(")

PRAGMA_BLOCK = f"""{PRAGMA_MARKER}
/*
 * Fallback: an unusual definition shape defeated prototype insertion, so the
 * warning is silenced for this vendored file only. -Wmissing-prototypes stays
 * on everywhere else.
 */
#if defined(__clang__)
#pragma clang diagnostic ignored "-Wmissing-prototypes"
#elif defined(__GNUC__) && __GNUC__ >= 8
#pragma GCC diagnostic ignored "-Wmissing-prototypes"
#endif
"""


def die(msg: str) -> NoReturn:
    sys.exit(f"ERROR: {msg}")


def signature_of(lines: list[str], i: int) -> str | None:
    ln = lines[i]
    if ln.rstrip().endswith(";"):
        return None  # already a prototype, not a definition
    # Strip leading annotations so `__attribute__((hot)) bool f(...)` and
    # `__weak int f(...)` are recognised as definitions (the attribute's own
    # parentheses otherwise swallow the function name).
    clean = re.sub(r"^(?:(?:__attribute__\s*\(\([^)]*\)\)|__[a-z]+)\s+)+", "", ln)
    m = DEF_RE.match(clean)
    if not m or m.group(2) in SKIP:
        return None
    sig, depth, j = clean, clean.count("(") - clean.count(")"), i
    while depth > 0 and j + 1 < len(lines):
        j += 1
        sig += "\n" + lines[j]
        depth += lines[j].count("(") - lines[j].count(")")
    sig = sig.split("{")[0].rstrip()
    if ")" not in sig:
        return None
    sig = sig[: sig.rindex(")") + 1].strip()
    if sig.count("(") != sig.count(")") or not sig.endswith(")"):
        return None
    return sig


def strip_attributes(sig: str) -> str:
    return re.sub(r"__attribute__\s*\(\([^)]*\)\)\s*", "", sig).strip()


def missing_definitions(text: str) -> list[str]:
    lines = text.split("\n")
    missing = []
    for i, ln in enumerate(lines):
        if ln[:1] in (" ", "\t", "#", "/", "*", "}", ""):
            continue
        if ln.startswith("static") or ln.startswith("inline"):
            continue
        sig = signature_of(lines, i)
        if not sig:
            continue
        m2 = re.search(r"\b([A-Za-z_]\w*)\s*\(", sig)
        if not m2:
            continue
        name = m2.group(1)
        window = "\n".join(lines[max(0, i - 3) : i])
        if not re.search(rf"\b{re.escape(name)}\s*\([^;]*\)\s*;", window):
            missing.append(name)
    return missing


def add_pragmas(path: str) -> None:
    lines = open(path, encoding="utf-8").read().split("\n")
    idx = [i for i, ln in enumerate(lines) if ln.startswith("#include")]
    if not idx:
        die("fs/susfs.c: no #include lines found")
    at = idx[-1] + 1
    lines[at:at] = [""] + PRAGMA_BLOCK.split("\n")
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    print("  fs/susfs.c: FALLBACK - silenced -Wmissing-prototypes for this file")


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: susfs_618_prototypes.py <kernel/common>")
    path = os.path.join(sys.argv[1].rstrip("/"), "fs/susfs.c")
    if not os.path.exists(path):
        die(f"{path}: not found")

    src = open(path, encoding="utf-8").read()
    if PROTO_MARKER in src:
        print("  fs/susfs.c: prototypes already inserted")
        return
    if PRAGMA_MARKER in src:
        print("  fs/susfs.c: already silenced (fallback path from an earlier run)")
        return

    lines = src.split("\n")
    out: list[str] = []
    inserted = 0
    for i, ln in enumerate(lines):
        if ln[:1] not in (" ", "\t", "#", "/", "*", "}", ""):
            if not ln.startswith("static") and not ln.startswith("inline"):
                sig = signature_of(lines, i)
                if sig:
                    m2 = re.search(r"\b([A-Za-z_]\w*)\s*\(", sig)
                    if not m2:
                        continue
                    name = m2.group(1)
                    prev = next((p for p in reversed(out) if p.strip()), "")
                    already = prev.rstrip().endswith(";") and re.search(
                        rf"\b{re.escape(name)}\s*\(", prev
                    )
                    if not already:
                        out.append(PROTO_MARKER)
                        out.append(strip_attributes(sig) + ";")
                        inserted += 1
        out.append(ln)

    open(path, "w", encoding="utf-8").write("\n".join(out))
    print(f"  fs/susfs.c: {inserted} prototype(s) placed above their definitions")

    still = missing_definitions(open(path, encoding="utf-8").read())
    if still:
        print(f"  fs/susfs.c: {len(set(still))} left after insertion "
              f"({', '.join(sorted(set(still))[:4])}) - falling back")
        add_pragmas(path)
    else:
        print("  fs/susfs.c: verified - every non-static definition is declared")


if __name__ == "__main__":
    main()
