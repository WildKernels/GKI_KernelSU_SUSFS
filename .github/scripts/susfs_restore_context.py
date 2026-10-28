#!/usr/bin/env python3
"""Re-insert `#include <trace/hooks/*>` context lines a SUSFS hunk expects.

Google keeps dropping `#include <trace/hooks/blk.h>`, `<trace/hooks/fs.h>` and
`<trace/hooks/mm.h>` from GKI sources while the susfs4ksu patch still lists them
as hunk context, so `patch` fails hunk #1 of fs/namespace.c / fs/proc/task_mmu.c
on those sublevels. The includes are context only - SUSFS uses no blk/fs/mm
trace hook symbols - so restoring the line (and an empty header when the tree no
longer ships it) makes the hunk apply.

Deliberately narrow: only `<trace/hooks/...>` includes are considered, and lines
are inserted after the last include that the same hunk lists and the file
already has. Anything else is left alone - rewriting unrelated includes breaks
the very context we are trying to restore.

Idempotent. Usage: susfs_restore_context.py <patch> [tree]
"""
import pathlib
import re
import sys

INCLUDE_RE = re.compile(r'^#include\s+(?P<inc><trace/hooks/[^>]+>)')
ANY_INCLUDE = re.compile(r'^#include\s+(?P<inc>[<"][^>"]+[>"])')


def first_hunk_context_includes(hunk_lines):
    """Ordered #include lines the first hunk expects to find in the source."""
    out = []
    for line in hunk_lines:
        if line[:1] != ' ':
            continue
        m = ANY_INCLUDE.match(line[1:].strip())
        if m:
            out.append(m.group('inc'))
    return out


def parse_patch(text):
    """{path: [include, ...]} for the first hunk of every patched file."""
    files = {}
    cur = None
    hunk = []
    in_first = False

    def flush():
        nonlocal hunk, in_first
        if cur is not None and in_first:
            incs = first_hunk_context_includes(hunk)
            if incs:
                files[cur] = incs
        hunk = []
        in_first = False

    for line in text.splitlines():
        if line.startswith('diff --git '):
            flush()
            m = re.match(r'diff --git a/(\S+) b/', line)
            cur = m.group(1) if m else None
            continue
        if line.startswith('@@'):
            if in_first:
                flush()
                cur = None
                continue
            in_first = True
            continue
        if in_first:
            hunk.append(line)
    flush()
    return files


def ensure_stub(tree, inc):
    """Create an empty placeholder for a context-only trace hook header."""
    rel = inc.strip('<>')
    header = tree / 'include' / rel
    if header.exists():
        return None
    header.parent.mkdir(parents=True, exist_ok=True)
    guard = '_SUSFS_CONTEXT_STUB_' + re.sub(r'\W', '_', rel).upper()
    header.write_text(
        f'/* Stub created by GKI_KernelSU_SUSFS.\n'
        f' * The SUSFS patch lists #include <{rel}> as hunk context only; this\n'
        f' * GKI sublevel no longer ships the header. No symbols are used. */\n'
        f'#ifndef {guard}\n#define {guard}\n#endif\n')
    return header


def main():
    if len(sys.argv) < 2:
        raise SystemExit('usage: susfs_restore_context.py <patch> [tree]')
    patch_path = pathlib.Path(sys.argv[1])
    tree = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else '.')
    plan = parse_patch(patch_path.read_text(errors='replace'))

    added, stubbed = [], []
    for rel, includes in plan.items():
        if not any(INCLUDE_RE.match('#include ' + i) for i in includes):
            continue
        target = tree / rel
        if not target.exists():
            continue
        lines = target.read_text(errors='replace').splitlines(keepends=True)
        present = [l.strip() for l in lines]

        # Walk the hunk's include sequence in order and keep a cursor in the
        # file: a missing trace/hooks include is inserted exactly where the
        # hunk expects it (right after its predecessor), not after whatever
        # include happens to come last in the file.
        changed = False
        cursor = 0
        for inc in includes:
            want = f'#include {inc}'
            try:
                idx = present.index(want, cursor)
            except ValueError:
                idx = None
            if idx is not None:
                cursor = idx + 1
                continue
            if not INCLUDE_RE.match('#include ' + inc):
                continue  # only the trace/hooks context class is restored
            lines.insert(cursor, want + '\n')
            present.insert(cursor, want)
            added.append(f'{rel}: {want}')
            stub = ensure_stub(tree, inc)
            if stub:
                stubbed.append(str(stub.relative_to(tree)))
            cursor += 1
            changed = True
        if changed:
            target.write_text(''.join(lines))

    for a in added:
        print(f'context restored  {a}')
    for s in stubbed:
        print(f'stub header made  {s}')
    if not added and not stubbed:
        print('context already complete - nothing to restore')
    return 0


if __name__ == '__main__':
    sys.exit(main())
