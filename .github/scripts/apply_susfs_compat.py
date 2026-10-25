#!/usr/bin/env python3
"""Apply the upstream SUSFS patch across pre-refactor and current GKI 6.12."""

import re
import subprocess
import sys
from pathlib import Path


def adapt_patch(patch, exec_source, mmu_source):
    sections = re.split(r"(?=^diff --git )", patch, flags=re.M)
    old_rollup = (
        "\tvma_start = vma->vm_start;\n\tdo {\n"
        "\t\tsmap_gather_stats(vma, &mss, 0);"
    ) in mmu_source

    for index, section in enumerate(sections):
        if section.startswith("diff --git a/fs/exec.c "):
            if "#include <linux/dma-buf.h>" not in exec_source:
                hunks = re.split(r"(?=^@@ )", section, flags=re.M)
                if (
                    len(hunks) < 2
                    or hunks[1].count(" #include <linux/dma-buf.h>\n") != 1
                ):
                    raise ValueError("unexpected fs/exec.c SUSFS include hunk")
                hunks[1] = hunks[1].replace(" #include <linux/dma-buf.h>\n", "", 1)
                match = re.match(r"@@ -(\d+),(\d+) \+(\d+),(\d+) @@", hunks[1])
                if not match:
                    raise ValueError("unexpected fs/exec.c hunk header")
                old_line, old_count, new_line, new_count = map(int, match.groups())
                hunks[1] = re.sub(
                    r"^@@ [^\n]+@@",
                    f"@@ -{old_line},{old_count - 1} +{new_line},{new_count - 1} @@",
                    hunks[1],
                    count=1,
                )
                sections[index] = "".join(hunks)

        elif section.startswith("diff --git a/fs/proc/task_mmu.c "):
            if "if (!vma_pages(vma))" in mmu_source:
                if section.count(" \tif (!vma_data_pages(vma))\n") != 1:
                    raise ValueError("unexpected show_smap SUSFS hunk")
                section = section.replace(
                    " \tif (!vma_data_pages(vma))\n", " \tif (!vma_pages(vma))\n", 1
                )

            if old_rollup:
                hunks = re.split(r"(?=^@@ )", section, flags=re.M)
                discarded = [
                    h
                    for h in hunks[1:]
                    if "show_smaps_rollup" in h.split("\n", 1)[0]
                    and ("goto bypass_orig_flow;\n" in h or "\n+bypass_orig_flow:\n" in h)
                ]
                if len(discarded) != 2:
                    raise ValueError("unexpected show_smaps_rollup SUSFS hunks")
                section = "".join(h for h in hunks if h not in discarded)
            sections[index] = section

    return "".join(sections), old_rollup


def guard_old_rollup(mmu_source):
    start = mmu_source.index("static int show_smaps_rollup(")
    end = mmu_source.index("\nstatic const struct seq_operations proc_pid_smaps_op", start)
    rollup = mmu_source[start:end]
    call = re.compile(
        r"(?m)^(\t+)smap_gather_stats\(vma, &mss, (0|last_vma_end)\);$"
    )
    if len(call.findall(rollup)) != 3:
        raise ValueError("unexpected pre-refactor smaps_rollup gather calls")

    def guarded(match):
        indent, offset = match.groups()
        return (
            "#ifdef CONFIG_KSU_SUSFS_SUS_MAP\n"
            f"{indent}if (!vma->vm_file || "
            "!(SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file))))\n"
            "#endif\n"
            f"{indent}\tsmap_gather_stats(vma, &mss, {offset});"
        )

    rollup = call.sub(guarded, rollup)
    return mmu_source[:start] + rollup + mmu_source[end:]


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: apply_susfs_compat.py <kernel/common> <upstream.patch>")

    tree, patch_file = Path(sys.argv[1]), Path(sys.argv[2])
    exec_source = (tree / "fs/exec.c").read_text()
    mmu_file = tree / "fs/proc/task_mmu.c"
    adapted, old_rollup = adapt_patch(
        patch_file.read_text(), exec_source, mmu_file.read_text()
    )
    subprocess.run(
        ["patch", "--batch", "--forward", "-p1"],
        cwd=tree,
        input=adapted,
        text=True,
        check=True,
    )
    if old_rollup:
        mmu_file.write_text(guard_old_rollup(mmu_file.read_text()))


if __name__ == "__main__":
    main()
