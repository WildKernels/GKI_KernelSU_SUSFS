#!/usr/bin/env python3
"""Report whether a USB-Arsenal patch is already present in the kernel tree.

A newer kernel can ship a fix that an older patch set still carries. 6.1 with the
5.15 set is exactly that: 0005 ("f_hid: move list and spinlock inits") is already
in android14-6.1's f_hid.c, but with different surrounding context, so `git apply`
refuses it and `git apply --reverse --check` refuses too - it is neither appliable
nor cleanly reversible.

Applying it with fuzz would duplicate the inits, which is worse than skipping it.
So compare what the patch *adds* against the files it targets: if at least 90% of
the added lines already exist, treat the patch as satisfied.

Exit status: 0 = already present (skip), 1 = not present (try to apply).
"""

import os
import re
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: usb_arsenal_already_present.py <patch>", file=sys.stderr)
        return 2

    patch = sys.argv[1]
    cur, adds = None, {}
    with open(patch, errors="replace") as fh:
        for line in fh:
            m = re.match(r"^\+\+\+ b/(\S+)", line)
            if m:
                cur = m.group(1)
                adds.setdefault(cur, [])
                continue
            if cur and line.startswith("+") and not line.startswith("+++"):
                text = line[1:].strip()
                if text:
                    adds[cur].append(text)

    total = sum(len(v) for v in adds.values())
    if not total:
        return 1

    present = 0
    for path, lines in adds.items():
        if not os.path.exists(path):
            continue
        with open(path, errors="replace") as fh:
            body = fh.read()
        present += sum(1 for l in lines if l in body)

    return 0 if present / total >= 0.9 else 1


if __name__ == "__main__":
    sys.exit(main())
