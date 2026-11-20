#!/usr/bin/env python3
"""Install cpu.max for DroidSpaces without CONFIG_CFS_BANDWIDTH.

CFS_BANDWIDTH grows struct cfs_rq inside struct rq; vendor modules subscribed to
the android vendor-hook tracepoints read rq at compile-time offsets, so the
device stops booting even when the CRCs are shadowed back to stock (runs
44286900753 and 44466030716 both passed the ABI gate and neither booted).

This installs an out-of-scheduler quota instead: per-cgroup state in a list, a
delayed work that samples summed se.sum_exec_runtime at the interval set by
sched_cfs_bandwidth_slice_us, freeze/thaw of the cgroup's tasks when the period's
allowance is spent, and a burst bucket refilled from unused quota. No struct
changes anywhere.

  kernel/cgroup/cpuquota.c   the enforcer, cpu.max / cpu.max.burst handlers,
                             cpu.stat extras, sysctl
  kernel/cgroup/Makefile     build it
  kernel/cgroup/cgroup.c     cpu.max and cpu.max.burst in cgroup_base_files[],
                             state freed at destroy, and cpu_stat_show() extended
                             with the throttle/burst counters. No second cpu.stat:
                             cgroup_base_files[] already has one in 6.1.

Skipped when the tree really does enable CFS_BANDWIDTH - then the scheduler's own
cpu.max exists and adding a second one would collide.

Usage: ds_cpu_limit.py <kernel/common>
Idempotent.
"""
import shutil
import sys
from pathlib import Path

MARKER = "ds_cpu_max_show"
SRC = Path(__file__).resolve().parent.parent / "patches/ds-limits/cpuquota.c"


def die(msg: str):
    sys.stderr.write(f"error: {msg}\n")
    sys.exit(1)


def read(p: Path) -> str:
    if not p.is_file():
        die(f"{p}: not found")
    return p.read_text()


def real_bandwidth_enabled(root: Path) -> bool:
    frag = root / "wild_defconfig.fragment"
    if frag.is_file() and "CONFIG_CFS_BANDWIDTH=y" in read(frag):
        return True
    # the side-table port runs the scheduler's own bandwidth code
    sched_h = root / "kernel/sched/sched.h"
    return sched_h.is_file() and "DS_CFS_BANDWIDTH" in read(sched_h)


def patch_makefile(root: Path) -> bool:
    p = root / "kernel/cgroup/Makefile"
    t = read(p)
    if "cpuquota.o" in t:
        return False
    anchor = "obj-y += pidslimit.o\n"
    if anchor in t:
        t = t.replace(anchor, anchor + "obj-y += cpuquota.o\n", 1)
    else:
        t = t.rstrip("\n") + "\nobj-y += cpuquota.o\n"
    p.write_text(t)
    return True


def patch_cgroup_c(root: Path) -> bool:
    p = root / "kernel/cgroup/cgroup.c"
    t = read(p)
    changed = False

    if MARKER not in t:
        anchor = '\t{\n\t\t.name = "pids.max",\n'
        if anchor not in t:
            die("cgroup.c: pids.max base file not found - run ds_pids_limit.py first")
        inject = ('\t/* DroidSpaces cpu.max - enforced outside the scheduler */\n'
                  '\t{\n\t\t.name = "cpu.max",\n'
                  '\t\t.seq_show = ds_cpu_max_show,\n'
                  '\t\t.write = ds_cpu_max_write,\n'
                  '\t},\n'
                  '\t{\n\t\t.name = "cpu.max.burst",\n'
                  '\t\t.seq_show = ds_cpu_burst_show,\n'
                  '\t\t.write = ds_cpu_burst_write,\n'
                  '\t},\n')
        t = t.replace(anchor, inject + anchor, 1)
        changed = True

    if "int ds_cpu_max_show(struct seq_file *seq, void *v);" not in t:
        decl_anchor = "int ds_pids_max_show(struct seq_file *seq, void *v);\n"
        if decl_anchor not in t:
            die("cgroup.c: pids declarations not found")
        decl = ("int ds_cpu_max_show(struct seq_file *seq, void *v);\n"
                "ssize_t ds_cpu_max_write(struct kernfs_open_file *of, char *buf,\n"
                "\t\t\t   size_t nbytes, loff_t off);\n"
                "int ds_cpu_burst_show(struct seq_file *seq, void *v);\n"
                "ssize_t ds_cpu_burst_write(struct kernfs_open_file *of, char *buf,\n"
                "\t\t\t     size_t nbytes, loff_t off);\n"
                "void ds_cpu_stat_extra(struct seq_file *seq, struct cgroup *cgrp);\n"
                "void ds_cpuquota_free(struct cgroup *cgrp);\n")
        t = t.replace(decl_anchor, decl + decl_anchor, 1)
        changed = True

    if "ds_cpuquota_free(cgrp)" not in t:
        anchor = "\tds_pids_free(cgrp);\n"
        if anchor not in t:
            die("cgroup.c: pids cleanup hook not found")
        t = t.replace(anchor, anchor + "\tds_cpuquota_free(cgrp);\n", 1)
        changed = True

    if "ds_cpu_stat_extra(seq, cgrp)" not in t:
        anchor = ("\tcgroup_base_stat_cputime_show(seq);\n"
                  "#ifdef CONFIG_CGROUP_SCHED\n")
        if anchor not in t:
            die("cgroup.c: cpu_stat_show body not found")
        t = t.replace(anchor,
                      "\tcgroup_base_stat_cputime_show(seq);\n"
                      "\t/* DroidSpaces: throttle and burst counters for cpu.stat */\n"
                      "\tds_cpu_stat_extra(seq, cgrp);\n"
                      "#ifdef CONFIG_CGROUP_SCHED\n", 1)
        changed = True

    if changed:
        p.write_text(t)
    return changed


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: ds_cpu_limit.py <kernel/common>")
    root = Path(sys.argv[1])

    if real_bandwidth_enabled(root):
        print("ds cpu limit: CFS_BANDWIDTH is enabled, scheduler owns cpu.max - skipped")
        return
    if not SRC.is_file():
        die(f"{SRC}: source not found")

    dst = root / "kernel/cgroup/cpuquota.c"
    if not dst.is_file() or dst.read_bytes() != SRC.read_bytes():
        shutil.copyfile(SRC, dst)
        print("cpuquota.c installed")

    changed = any([patch_makefile(root), patch_cgroup_c(root)])
    print("ds cpu limit: wired" if changed else "ds cpu limit: already wired")


if __name__ == "__main__":
    main()
