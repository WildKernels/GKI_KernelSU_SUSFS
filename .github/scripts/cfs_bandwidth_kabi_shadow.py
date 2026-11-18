#!/usr/bin/env python3
"""Keep CONFIG_CFS_BANDWIDTH out of the exported ABI while the kernel still gets it.

CONFIG_CFS_BANDWIDTH is off in every stock GKI defconfig (init/Kconfig defaults
it to n), and turning it on adds members to two scheduler structs:

  kernel/sched/sched.h  struct cfs_bandwidth  gated fields (lock, quota, runtime, ...)
  kernel/sched/sched.h  struct cfs_rq         9 members (~64 bytes)

struct rq embeds struct cfs_rq, so genksyms expands the type through every
exported symbol that names 'struct rq *' - __traceiter_android_rvh_*,
__task_rq_lock, __migrate_task, __balance_callbacks - and their CRCs move.

The fix is the same ABI-shadowing the BBRv3 ports use: genksyms and the compiler
are separate passes over the same headers, so gate the new members on
!defined(__GENKSYMS__). The compiler sees the real struct; genksyms sees exactly
the stock one, because stock builds with the option off and therefore never
compiles those members at all.

Safe for vendor modules specifically because kernel/sched/sched.h is not part of
the GKI module headers - nothing outside the scheduler can be offset-sensitive to
either struct. Modules do not embed cfs_rq or cfs_bandwidth.

Usage: cfs_bandwidth_kabi_shadow.py <kernel/common>
Idempotent; a tree whose structs carry no gated block is left untouched.
"""
import sys
from pathlib import Path

GUARDED = "#if defined(CONFIG_CFS_BANDWIDTH) && !defined(__GENKSYMS__)"
PLAIN = "#ifdef CONFIG_CFS_BANDWIDTH"
TARGETS = ("struct cfs_bandwidth {", "struct cfs_rq {")


def die(msg: str):
    sys.stderr.write(f"error: {msg}\n")
    sys.exit(1)


def shadow(lines, struct_line: str) -> int:
    """Guard the first '#ifdef CONFIG_CFS_BANDWIDTH' inside a struct body."""
    start = next((i for i, l in enumerate(lines) if l.startswith(struct_line)), None)
    if start is None:
        return 0
    end: int = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("};")), -1)
    if end < 0:
        die(f"{struct_line}: unterminated struct")
    for i in range(start + 1, end):
        if lines[i].startswith(PLAIN):
            if lines[i].strip() == GUARDED:
                return 0
            lines[i] = lines[i].replace(PLAIN, GUARDED, 1)
            return 1
        if lines[i].strip() == GUARDED:
            return 0
    return 0


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: cfs_bandwidth_kabi_shadow.py <kernel/common>")
    sched_h = Path(sys.argv[1]) / "kernel/sched/sched.h"
    if not sched_h.is_file():
        die(f"{sched_h}: not found")
    lines = sched_h.read_text().splitlines(keepends=True)

    changed = sum(shadow(lines, t) for t in TARGETS)
    if changed:
        sched_h.write_text("".join(lines))
        print(f"cfs_bandwidth kabi shadow: {changed} struct(s) guarded")
    else:
        print("cfs_bandwidth kabi shadow: already guarded or no gated block, nothing to do")


if __name__ == "__main__":
    main()
