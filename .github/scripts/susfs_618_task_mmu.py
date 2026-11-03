#!/usr/bin/env python3
"""Fix up fs/proc/task_mmu.c after the ported SUSFS patch, for android17-6.18.

Two things the 6.12 patch cannot express as static context:

1. The SUS_MAP skip in show_smaps_rollup(). Google ships TWO shapes of this
   function on the 6.18 branches, so a context hunk offsets ~48 lines on one and
   rejects outright on the next:
     A (2026-04, 2026-09):  do { smap_gather_stats(...); last_vma_end = ...; }
                            for_each_vma(vmi, vma);
     B (2026-06, lts):      while (vma) { ... if (vma->vm_start < last_vma_end)
                            { smap_gather_stats_range(...) } else {
                            smap_gather_stats(...) } last_vma_end = ...; }
   Anchor on the loop shape and the last_vma_end assignment, not on line numbers.

2. The OPEN_REDIRECT branch in show_map_vma() calls two page-size-migration
   helpers (__VM_NO_COMPAT, __fold_filemap_fixup_entry) that only exist on trees
   carrying Google's page-size work. Where they are absent the code cannot
   compile; the calls are dead there anyway (VMA_PAD_START falls back to
   vm_end, so nothing is ever padded and nothing needs folding).

Idempotent, anchor-checked, fails loudly on drift.

Usage: susfs_618_task_mmu.py <kernel/common>
"""

import os
import re
import sys
from typing import NoReturn

GUARD = """#ifdef CONFIG_KSU_SUSFS_SUS_MAP
\t\tif (vma->vm_file && SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file)))
\t\t\tgoto bypass_orig_flow;
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP
"""

LABEL = """#ifdef CONFIG_KSU_SUSFS_SUS_MAP
bypass_orig_flow:
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP
"""


def die(msg: str) -> NoReturn:
    sys.exit(f"ERROR: {msg}")


def tree_has_pgsize_migration(root: str) -> bool:
    """True when __VM_NO_COMPAT / __fold_filemap_fixup_entry actually exist.

    Do NOT test for page_size_compat.h: every 6.18 branch ships that header, but
    the two symbols the SUSFS OPEN_REDIRECT block uses are absent (checked mm.h,
    page_size_compat.h, pgsize_migration.h and fs/proc/internal.h on
    android17-6.18, -2026-09, -2026-06 and -2026-04). Grepping headers is cheap;
    grepping include/ is not.
    """
    for rel in (
        "include/linux/mm.h",
        "include/linux/page_size_compat.h",
        "include/linux/pgsize_migration.h",
        "fs/proc/internal.h",
    ):
        p = os.path.join(root, rel)
        if os.path.exists(p):
            with open(p, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            if "__VM_NO_COMPAT" in text or "__fold_filemap_fixup_entry" in text:
                return True
    return False


def fix_smaps_rollup(src: str) -> tuple[str, str]:
    fn = src.find("static int show_smaps_rollup(")
    if fn < 0:
        die("task_mmu.c: show_smaps_rollup() not found")
    nxt = src.find("\nstatic ", fn + 10)
    end = nxt if nxt > 0 else len(src)
    region = src[fn:end]

    if "bypass_orig_flow" in region:
        return src, "SUS_MAP skip already present"

    do_loop = re.search(r"(?m)^\tdo \{\n", region)
    while_loop = re.search(r"(?m)^\twhile \(vma\) \{\n", region)
    cmp_line = re.search(r"(?m)^\t\tif \(vma->vm_start < last_vma_end\) \{\n", region)
    last_end = re.search(r"(?m)^\t\tlast_vma_end = vma->vm_end;\n", region)

    if not last_end:
        die("task_mmu.c: `last_vma_end = vma->vm_end;` not found in show_smaps_rollup()")

    if do_loop:
        insert_at = fn + do_loop.end()
        shape = "A (do/for_each_vma)"
    elif cmp_line:
        insert_at = fn + cmp_line.start()
        shape = "B (while/vma_next)"
    elif while_loop:
        insert_at = fn + while_loop.end()
        shape = "B (while/vma_next, no cmp line)"
    else:
        die("task_mmu.c: neither loop shape found in show_smaps_rollup()")

    label_at = fn + last_end.start()
    src = src[:label_at] + LABEL + src[label_at:]
    src = src[:insert_at] + GUARD + src[insert_at:]
    return src, f"SUS_MAP skip inserted - shape {shape}"


def drop_pgsize_only_lines(src: str) -> tuple[str, str]:
    """Remove the __VM_NO_COMPAT / __fold_filemap_fixup_entry pair when unsupported."""
    if "__VM_NO_COMPAT" not in src and "__fold_filemap_fixup_entry" not in src:
        return src, "no page-size-migration calls in show_map_vma()"
    lines = src.split("\n")
    out, i, removed = [], 0, 0
    while i < len(lines):
        ln = lines[i]
        stripped = ln.strip()
        if stripped.startswith("if (flags & __VM_NO_COMPAT)"):
            indent = len(ln) - len(ln.lstrip("\t"))
            j = i + 1
            while j < len(lines) and not (
                lines[j].strip() == "}" and len(lines[j]) - len(lines[j].lstrip("\t")) == indent
            ):
                j += 1
            k = j + 1
            if k < len(lines) and "__fold_filemap_fixup_entry" in lines[k]:
                k += 1
            removed += 1
            i = k
            continue
        if "__fold_filemap_fixup_entry" in stripped:
            removed += 1
            i += 1
            continue
        out.append(ln)
        i += 1
    if not removed:
        return src, "page-size-migration calls not in the expected shape (left alone)"
    return "\n".join(out), f"dropped {removed} page-size-migration-only construct(s)"


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: susfs_618_task_mmu.py <kernel/common>")
    root = sys.argv[1].rstrip("/")
    path = f"{root}/fs/proc/task_mmu.c"
    src = open(path, encoding="utf-8").read()

    src, msg1 = fix_smaps_rollup(src)
    print(f"  task_mmu.c: {msg1}")

    if tree_has_pgsize_migration(root):
        print("  task_mmu.c: tree carries page-size-migration helpers, leaving show_map_vma() as-is")
    else:
        src, msg2 = drop_pgsize_only_lines(src)
        print(f"  task_mmu.c: {msg2}")

    open(path, "w", encoding="utf-8").write(src)

    check = open(path, encoding="utf-8").read()
    fn = check.find("static int show_smaps_rollup(")
    nxt = check.find("\nstatic ", fn + 10)
    region = check[fn : nxt if nxt > 0 else len(check)]
    if "goto bypass_orig_flow;" not in region or "bypass_orig_flow:" not in region:
        die("task_mmu.c: SUS_MAP skip missing after write")
    if not tree_has_pgsize_migration(root) and "__fold_filemap_fixup_entry" in check:
        die("task_mmu.c: __fold_filemap_fixup_entry still referenced")
    print("  task_mmu.c: verified")


if __name__ == "__main__":
    main()
