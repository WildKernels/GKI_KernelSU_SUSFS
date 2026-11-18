#!/usr/bin/env python3
"""Keep DroidSpaces' scheduler/cgroup options out of the exported ABI.

Both options are off in stock GKI and both move genksyms' view of types that
exported symbols reach, so both are shadowed the same way: the compiler gets the
real layout, `__GENKSYMS__` gets the stock one.

1. CONFIG_CFS_BANDWIDTH (cpu.max)
   kernel/sched/sched.h adds members to struct cfs_bandwidth and struct cfs_rq.
   struct rq embeds struct cfs_rq, so the CRCs of every exported symbol naming
   'struct rq *' move (__traceiter_android_rvh_*, __task_rq_lock,
   __migrate_task, __balance_callbacks).

2. CONFIG_CGROUP_PIDS (pids.max)
   include/linux/cgroup_subsys.h gains one SUBSYS(pids) entry, which increments
   CGROUP_SUBSYS_COUNT. That constant sizes fixed arrays inside struct cgroup and
   struct css_set (include/linux/cgroup-defs.h:218/258/447/464), so both structs
   grow and the change propagates through every exported symbol that reaches
   them - measured on android14-6.1-2026-06: 3241 of 8865 symbols drifted from
   stock, against 0 for the same leg with the option off.

Neither struct is part of the GKI module headers, so no vendor module can be
offset-sensitive to them; only kernel-internal layout differs.

Usage: droidspaces_kabi_shadow.py <kernel/common>
Idempotent; a tree without a given gated block is left untouched for it.
"""
import sys
from pathlib import Path

S = "kernel/sched/sched.h"
C = "include/linux/cgroup_subsys.h"

PLAIN_BW = "#ifdef CONFIG_CFS_BANDWIDTH"
GUARDED_BW = "#if defined(CONFIG_CFS_BANDWIDTH) && !defined(__GENKSYMS__)"
PLAIN_PIDS = "#if IS_ENABLED(CONFIG_CGROUP_PIDS)"
GUARDED_PIDS = "#if IS_ENABLED(CONFIG_CGROUP_PIDS) && !defined(__GENKSYMS__)"
BW_STRUCTS = ("struct cfs_bandwidth {", "struct cfs_rq {")


def die(msg: str):
    sys.stderr.write(f"error: {msg}\n")
    sys.exit(1)


def shadow_struct(lines, struct_line: str) -> int:
    """Guard the first '#ifdef CONFIG_CFS_BANDWIDTH' inside a struct body."""
    start = next((i for i, l in enumerate(lines) if l.startswith(struct_line)), -1)
    if start < 0:
        return 0
    end: int = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("};")), -1)
    if end < 0:
        die(f"{struct_line}: unterminated struct")
    for i in range(start + 1, end):
        if lines[i].startswith(GUARDED_BW):
            return 0
        if lines[i].startswith(PLAIN_BW):
            lines[i] = lines[i].replace(PLAIN_BW, GUARDED_BW, 1)
            return 1
    return 0


def shadow_subsys(lines) -> int:
    """Guard the SUBSYS(pids) entry so genksyms keeps the stock subsystem count."""
    for i, line in enumerate(lines):
        if line.startswith(GUARDED_PIDS):
            return 0
        if line.startswith(PLAIN_PIDS):
            nxt = "\n".join(lines[i + 1:i + 3])
            if "SUBSYS(pids)" not in nxt:
                return 0
            lines[i] = line.replace(PLAIN_PIDS, GUARDED_PIDS, 1)
            return 1
    return 0


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: droidspaces_kabi_shadow.py <kernel/common>")
    root = Path(sys.argv[1])

    total = 0
    sched = root / S
    if sched.is_file():
        lines = sched.read_text().splitlines(keepends=True)
        n = sum(shadow_struct(lines, t) for t in BW_STRUCTS)
        if n:
            sched.write_text("".join(lines))
        total += n
    else:
        die(f"{sched}: not found")

    subsys = root / C
    if subsys.is_file():
        lines = subsys.read_text().splitlines(keepends=True)
        n = shadow_subsys(lines)
        if n:
            subsys.write_text("".join(lines))
        total += n

    print(f"droidspaces kabi shadow: {total} site(s) guarded"
          if total else "droidspaces kabi shadow: nothing to do (already guarded or not gated)")


if __name__ == "__main__":
    main()
