#!/usr/bin/env python3
"""Export __vfs_setxattr_noperm so the NTSync backport can link as a module.

The 5.10 / 5.15 trees resolve CONFIG_NTSYNC to =m and fs/xattr.c exports
nothing, so modpost rejects the reference:

    ERROR: modpost: "__vfs_setxattr_noperm" [drivers/misc/ntsync.ko] undefined!

6.x has the same unexported symbol but builds ntsync in-tree, where the
reference resolves at vmlinux link time, so this script is only wired for
5.10 / 5.15: adding an export to a 6.x tree would move its KMI surface for no
reason. Run is idempotent and fails loudly when the definition it must
annotate is absent, so a tree change cannot silently drop the export.

Usage: ntsync_xattr_export.py <kernel-tree-root>
"""

import sys
from pathlib import Path

SYMBOL = "__vfs_setxattr_noperm"
EXPORT = "EXPORT_SYMBOL_GPL(%s);\n" % SYMBOL


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: ntsync_xattr_export.py <kernel-tree-root>", file=sys.stderr)
        return 2

    tree = Path(sys.argv[1])
    xattr = tree / "fs" / "xattr.c"
    if not xattr.is_file():
        print("ERROR: %s not found - is this a kernel tree?" % xattr, file=sys.stderr)
        return 1

    text = xattr.read_text()

    if "EXPORT_SYMBOL" in text and SYMBOL in text:
        for line in text.splitlines():
            if line.startswith("EXPORT_SYMBOL") and SYMBOL in line:
                print("ntsync: %s is already exported (%s)" % (SYMBOL, line.strip()))
                return 0

    lines = text.splitlines(keepends=True)

    def_line = None
    for i, line in enumerate(lines):
        if line.startswith("int %s(" % SYMBOL):
            def_line = i
            break
    if def_line is None:
        print(
            "ERROR: definition of %s not found in %s - the export cannot be "
            "placed, aborting rather than building a kernel that fails modpost"
            % (SYMBOL, xattr),
            file=sys.stderr,
        )
        return 1

    # The closing brace of a top-level function is the first '}' at column 0.
    close = None
    for i in range(def_line + 1, len(lines)):
        if lines[i].startswith("}"):
            close = i
            break
    if close is None:
        print(
            "ERROR: no column-0 closing brace after %s at %s:%d"
            % (SYMBOL, xattr, def_line + 1),
            file=sys.stderr,
        )
        return 1

    lines.insert(close + 1, EXPORT)
    xattr.write_text("".join(lines))
    print(
        "ntsync: exported %s after its definition at %s:%d"
        % (SYMBOL, xattr, close + 1)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
