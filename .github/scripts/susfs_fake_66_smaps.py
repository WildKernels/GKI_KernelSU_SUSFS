#!/usr/bin/env python3
"""Brace the show_smaps_rollup "Case 4" block on 6.6 sublevels <= 30.

Those trees have

    if (vma->vm_end > last_vma_end)
        smap_gather_stats(vma, &mss, last_vma_end);

while the SUSFS patch's show_smaps_rollup hunk expects the braced form with the
`last_vma_end = vma->vm_end;` line inside. Replaces the inline one-liner that
used to do this (its regex was unbalanced and raised every run, so the reshape
silently never happened and hunk #6 failed).

Idempotent. Usage: susfs_fake_66_smaps.py <fs/proc/task_mmu.c> [apply|revert]
"""
import pathlib
import re
import sys

BRACED = re.compile(
    r'(?P<i>\t+)if \(vma->vm_end > last_vma_end\) \{\n'
    r'(?P=i)\tsmap_gather_stats\(vma, &mss, last_vma_end\);\n'
    r'(?P=i)\tlast_vma_end = vma->vm_end;\n'
    r'(?P=i)\}\n'
)
BARE = re.compile(
    r'(?P<i>\t+)if \(vma->vm_end > last_vma_end\)\n'
    r'(?P=i)\tsmap_gather_stats\(vma, &mss, last_vma_end\);\n'
)


def main():
    if len(sys.argv) < 2:
        raise SystemExit('usage: susfs_fake_66_smaps.py <task_mmu.c> [apply|revert]')
    path = pathlib.Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else 'apply'
    src = path.read_text()

    if mode == 'apply':
        if BRACED.search(src):
            print('show_smaps_rollup already braced - nothing to do')
            return 0
        m = BARE.search(src)
        if not m:
            raise SystemExit('ERROR: Case 4 pattern not found - 6.6 source shape changed')
        ind = m.group('i')
        repl = (f'{ind}if (vma->vm_end > last_vma_end) {{\n'
                f'{ind}\tsmap_gather_stats(vma, &mss, last_vma_end);\n'
                f'{ind}\tlast_vma_end = vma->vm_end;\n'
                f'{ind}}}\n')
        path.write_text(src[:m.start()] + repl + src[m.end():])
        print('braced show_smaps_rollup Case 4 block (6.6 <= 30)')
        return 0

    if mode == 'revert':
        m = BRACED.search(src)
        if not m:
            print('not braced - nothing to revert')
            return 0
        ind = m.group('i')
        repl = (f'{ind}if (vma->vm_end > last_vma_end)\n'
                f'{ind}\tsmap_gather_stats(vma, &mss, last_vma_end);\n')
        path.write_text(src[:m.start()] + repl + src[m.end():])
        print('reverted show_smaps_rollup Case 4 block')
        return 0

    raise SystemExit(f'unknown mode: {mode}')


if __name__ == '__main__':
    sys.exit(main())
