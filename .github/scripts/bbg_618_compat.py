#!/usr/bin/env python3
"""Make Baseband-guard build on android17-6.18 (kernel 6.18).

Upstream BBG calls blkdev_get_no_open() without declaring it, which worked
while the prototype lived in include/linux/blkdev.h. Two upstream changes broke
that for 6.18:

  6.15  signature gained `bool autoload`
        (torvalds 5f33b5226c9d, the commit BBG itself cites)
  6.18  prototype moved out of include/linux/blkdev.h into block/blk.h, which is
        private to the block layer -> "call to undeclared function"

The function still exists (block/bdev.c, unchanged semantics; put stays
blkdev_put_no_open). Neither is EXPORT_SYMBOL'd, which is fine because BBG is
built into vmlinux.

This adds the missing declarations and routes stats/helper.c's unguarded
single-argument call through version-aware wrappers.

Usage: bbg_618_compat.py <path-to-security/baseband-guard>

Idempotent; exits 1 if the anchors it expects are missing or already ambiguous,
so an upstream refactor fails the build instead of silently skipping the shim.
"""

import re
import sys
from typing import NoReturn

MARKER = "/* BBG 6.18 compat: blkdev_get_no_open declaration/arity (added by GKI_KernelSU_SUSFS) */"

DECLS = """
{marker}
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 15, 0)
extern struct block_device *blkdev_get_no_open(dev_t dev, bool autoload);
#else
extern struct block_device *blkdev_get_no_open(dev_t dev);
#endif
extern void blkdev_put_no_open(struct block_device *bdev);

static inline struct block_device *bbg_bdev_get_no_open(dev_t dev)
{{
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 15, 0)
    return blkdev_get_no_open(dev, true);   /* true = legacy autoload behaviour */
#else
    return blkdev_get_no_open(dev);
#endif
}}
"""

CALL_OLD = "\tbdev = blkdev_get_no_open(dev);"
CALL_NEW = "\tbdev = bbg_bdev_get_no_open(dev);"


def fail(msg: str) -> NoReturn:
    sys.exit(f"ERROR: {msg}")


def patch_decls(path: str) -> None:
    """Insert the declarations after the LAST #include.

    Anchoring on a named include is wrong: blkdev_helper.c starts with
    <linux/version.h> before <linux/blkdev.h>, so declaring dev_t/bool there
    fails with "unknown type name 'dev_t'". The last include guarantees
    blkdev.h and types.h are already in scope.
    """
    src = open(path, encoding="utf-8").read()
    if MARKER in src:
        print(f"  {path}: already patched, skipping")
        return
    lines = src.split("\n")
    # Anchor on <linux/blkdev.h>, which is the first include in both files and
    # brings dev_t/bool into scope. Anchoring on "the last #include" was wrong:
    # blkdev_helper.c has another #include past the functions that call the
    # wrapper (line 123), which left the declaration below its uses.
    idx = [i for i, ln in enumerate(lines) if ln.startswith("#include <linux/blkdev.h>")]
    if not idx:
        idx = [i for i, ln in enumerate(lines[:40]) if ln.startswith("#include")]
    if not idx:
        fail(f"{path}: no usable #include line found")
    at = idx[0] + 1
    block = DECLS.format(marker=MARKER).rstrip("\n").split("\n")
    lines[at:at] = [""] + block
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    print(f"  {path}: declarations added after the last #include (line {at})")


def patch_call(path: str) -> None:
    src = open(path, encoding="utf-8").read()
    if CALL_NEW in src:
        print(f"  {path}: call already routed through the wrapper")
        return
    n = src.count(CALL_OLD)
    if n != 1:
        fail(f"{path}: expected exactly one unguarded blkdev_get_no_open(dev) call, found {n}")
    open(path, "w", encoding="utf-8").write(src.replace(CALL_OLD, CALL_NEW, 1))
    print(f"  {path}: single-arg call routed through bbg_bdev_get_no_open()")


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: bbg_618_compat.py <path-to-security/baseband-guard>")
    root = sys.argv[1].rstrip("/")
    compat = f"{root}/kernel_compat.h"
    helper = f"{root}/blkdev_helper.c"

    print(f"[+] BBG 6.18 compat: {root}")
    patch_decls(compat)
    patch_decls(helper)
    patch_call(helper)

    # verify
    for p in (compat, helper):
        text = open(p, encoding="utf-8").read()
        if MARKER not in text:
            fail(f"{p}: marker missing after write")
    if CALL_NEW not in open(helper, encoding="utf-8").read():
        fail(f"{helper}: wrapper call missing after write")
    if re.search(r"^\tbdev = blkdev_get_no_open\(dev\);$", open(helper, encoding="utf-8").read(), re.M):
        fail(f"{helper}: unguarded call still present")
    print("[+] BBG 6.18 compat applied and verified")


if __name__ == "__main__":
    main()
