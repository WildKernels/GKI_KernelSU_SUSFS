#!/usr/bin/env python3
"""Adapt the 6.18 SUSFS patch's clone_mnt() hunk to the tree's actual shape.

The 6.18 bundle's fs/namespace.c hunk #8 inserts the SUS_MOUNT bookkeeping at
the top of clone_mnt(), anchored on:

    {
        struct mount *mnt;
        int err;

        mnt = alloc_vfsmnt(old->mnt_devname);

6.18.63 added a line in that prologue:

        mnt->mnt_t_flags = old->mnt_t_flags & T_UNBINDABLE;

which no longer matches the patch's pre-image, so the whole hunk failed
("Hunk #8 FAILED at 1437") and the leg died before compiling. Hard-coding the
new context would break every sublevel that still has the old shape, so this
rewrites the hunk's pre-image to whatever the tree actually contains, and
leaves the patch untouched when the line is absent.

Usage: susfs_618_namespace_mnt_t_flags.py <kernel/common> <patch-file>
"""
import re
import sys
from pathlib import Path
from typing import NoReturn

ANCHOR = "static struct mount *clone_mnt("
MNT_T_FLAGS = "mnt->mnt_t_flags = old->mnt_t_flags & T_UNBINDABLE;"


def die(msg: str) -> NoReturn:
    sys.stderr.write(f"error: {msg}\n")
    sys.exit(1)


def clone_mnt_body(source: str) -> str:
    start = source.find(ANCHOR)
    if start < 0:
        die("fs/namespace.c: clone_mnt() not found")
    # Body runs to the matching close brace of the function.
    brace = source.find("{", start)
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i]
    die("fs/namespace.c: clone_mnt() body did not terminate")


def main() -> None:
    if len(sys.argv) != 3:
        die("usage: susfs_618_namespace_mnt_t_flags.py <kernel/common> <patch-file>")
    tree, patch_path = Path(sys.argv[1]), Path(sys.argv[2])
    ns = tree / "fs/namespace.c"
    if not ns.is_file():
        die(f"{ns}: not found")

    body = clone_mnt_body(ns.read_text(errors="surrogateescape"))
    if MNT_T_FLAGS not in body:
        print("fs/namespace.c: clone_mnt() has no mnt_t_flags line, patch left as-is")
        return

    text = patch_path.read_text()
    sections = re.split(r"(?m)^(?=diff --git )", text)
    changed = False
    for si, sec in enumerate(sections):
        if not sec.startswith("diff --git a/fs/namespace.c"):
            continue
        hunks = re.split(r"(?m)^(?=@@ )", sec)
        for hi, hunk in enumerate(hunks):
            if not hunk.startswith("@@ "):
                continue
            if "clone_mnt" not in hunk.splitlines()[0]:
                continue
            body_lines = hunk.splitlines()[1:]
            if any(MNT_T_FLAGS in ln for ln in body_lines):
                print("patch already carries the mnt_t_flags context line")
                return
            out, inserted = [], False
            for ln in body_lines:
                out.append(ln)
                if not inserted and "~MNT_INTERNAL_FLAGS;" in ln:
                    out.append(" \t" + MNT_T_FLAGS)
                    inserted = True
            if not inserted:
                die("patch: could not find the MNT_INTERNAL_FLAGS context line")
            m = re.match(r"@@ -(\d+),(\d+) \+(\d+),(\d+) @@(.*)$", hunk.splitlines()[0])
            if m is None:
                die("patch: unexpected hunk header shape")
            old_start, old_len, new_start, new_len = (int(g) for g in m.groups()[:4])
            header = "@@ -%d,%d +%d,%d @@%s" % (
                old_start, old_len + 1, new_start, new_len + 1, m.group(5))
            hunks[hi] = "\n".join([header] + out) + "\n"
            sections[si] = "".join(hunks)
            changed = True
            print(f"adapted clone_mnt hunk: pre-image {old_len} -> {old_len + 1} lines")
    if not changed:
        die("patch: no clone_mnt hunk for fs/namespace.c")

    patch_path.write_text("".join(sections))


if __name__ == "__main__":
    main()
