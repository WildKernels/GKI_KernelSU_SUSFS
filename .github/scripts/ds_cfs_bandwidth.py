#!/usr/bin/env python3
"""Run the real CFS bandwidth code with its state in side tables.

CONFIG_CFS_BANDWIDTH adds ten fields to struct cfs_rq (embedded in struct rq) and
fills struct cfs_bandwidth (embedded in task_group). Both types are in the GKI ABI
graph - root_task_group is exported - so enabling it moves thousands of CRCs, and
even with the CRCs shadowed back to stock the device does not boot: vendor modules
read rq fields at offsets baked in when they were compiled (runs 44286900753 and
44466030716 passed the gate and neither booted).

This keeps every struct stock and runs the upstream bandwidth code anyway:

  kernel/sched/ds_bandwidth.h/.c  the two state structs, side tables keyed by
                                  cfs_rq / task_group pointer, a static key so
                                  the fast path is unchanged until a quota is set
  kernel/sched/sched.h            the gated struct members removed, the bandwidth
                                  type renamed to ds_cfs_bandwidth, code enabled
                                  under DS_CFS_BANDWIDTH
  kernel/sched/fair.c, core.c,    guards enabled, field accesses rewritten to the
  debug.c                         side-table accessors, alloc/free hooks added

The scheduler's own cpu.max, cpu.max.burst, cpu.stat and the slice sysctl are then
the real ones, so the freeze-based cpuquota port is not installed alongside it.

Usage: ds_cfs_bandwidth.py <kernel/common>
Idempotent.
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "patches/ds-limits"
MARKER = "DS_CFS_BANDWIDTH"

CFS_RQ_FIELDS = [
    "runtime_enabled", "runtime_remaining", "throttled_pelt_idle",
    "throttled_clock", "throttled_clock_pelt", "throttled_clock_pelt_time",
    "throttled", "throttle_count", "throttled_list",
]
# longest first so throttled_clock_pelt_time is not eaten by throttled_clock
FIELD_RE = re.compile(
    r"\b([A-Za-z_]\w*(?:->\w+)*)->(" +
    "|".join(sorted(CFS_RQ_FIELDS, key=len, reverse=True)) + r")\b")


def die(msg: str):
    sys.stderr.write(f"error: {msg}\n")
    sys.exit(1)


def read(p: Path) -> str:
    if not p.is_file():
        die(f"{p}: not found")
    return p.read_text()


def sub(t: str, old: str, new: str, what: str) -> str:
    if old not in t:
        die(f"{what}: anchor not found")
    return t.replace(old, new, 1)


def enable_guards(t: str) -> str:
    t = t.replace("#ifdef CONFIG_CFS_BANDWIDTH",
                  "#if defined(CONFIG_CFS_BANDWIDTH) || defined(DS_CFS_BANDWIDTH)")
    t = t.replace("#ifndef CONFIG_CFS_BANDWIDTH",
                  "#if !defined(CONFIG_CFS_BANDWIDTH) && !defined(DS_CFS_BANDWIDTH)")
    return t


def rewrite_fields(t: str) -> str:
    return FIELD_RE.sub(lambda m: f"ds_cfs_rq_bw({m.group(1)})->{m.group(2)}", t)


BW_MEMBER_RE = re.compile(r"\b([A-Za-z_]\w*(?:->\w+)*)->cfs_bandwidth\.(\w+)")
BW_ROOT_RE = re.compile(r"\broot_task_group\.cfs_bandwidth\.(\w+)")


def rewrite_bw_members(t: str) -> str:
    """tg->cfs_bandwidth.quota -> ds_tg_bw(tg)->quota (the member stays empty)."""
    t = BW_MEMBER_RE.sub(lambda m: f"ds_tg_bw({m.group(1)})->{m.group(2)}", t)
    return BW_ROOT_RE.sub(lambda m: f"ds_tg_bw(&root_task_group)->{m.group(1)}", t)


def patch_sched_h(root: Path) -> bool:
    p = root / "kernel/sched/sched.h"
    t = read(p)
    if MARKER in t:
        return False

    # 1. turn the code on
    guard = "#ifndef _KERNEL_SCHED_SCHED_H\n#define _KERNEL_SCHED_SCHED_H\n"
    if guard not in t:
        die("sched.h: include guard not found")
    t = t.replace(guard, guard + "\n/* DroidSpaces: bandwidth code on, structs stay stock */\n"
                                 "#define DS_CFS_BANDWIDTH 1\n", 1)

    # 2. task_group keeps an empty cfs_bandwidth; the real state is a side table
    start = t.index("struct cfs_bandwidth {\n#ifdef CONFIG_CFS_BANDWIDTH")
    end = t.index("\n};\n", start) + len("\n};\n")
    t = t[:start] + ("/* DroidSpaces: state lives in ds_cfs_bandwidth, keyed by task_group */\n"
                     "struct cfs_bandwidth { };\n") + t[end:]

    # 3. cfs_rq keeps its stock layout
    start = t.index("#ifdef CONFIG_CFS_BANDWIDTH\n\tint\t\t\truntime_enabled;")
    end = t.index("#endif /* CONFIG_CFS_BANDWIDTH */\n", start) + len("#endif /* CONFIG_CFS_BANDWIDTH */\n")
    t = t[:start] + t[end:]

    # 4. the bandwidth type used by the code is the side-table one
    t = t.replace("struct cfs_bandwidth *", "struct ds_cfs_bandwidth *")

    # 5. accessors, after cfs_rq and task_group are defined
    anchor = "#endif\t/* CONFIG_CGROUP_SCHED */\n"
    t = sub(t, anchor, anchor + '\n#include "ds_bandwidth.h"\n', "sched.h include point")

    p.write_text(t)
    return True


def patch_fair_c(root: Path) -> bool:
    p = root / "kernel/sched/fair.c"
    t = read(p)
    if "ds_cfs_rq_bw(" in t:
        return False

    t = enable_guards(t)
    t = t.replace("struct cfs_bandwidth", "struct ds_cfs_bandwidth")
    t = t.replace("&tg->cfs_bandwidth", "ds_tg_bw(tg)")
    t = rewrite_bw_members(t)
    t = rewrite_fields(t)

    # state allocated with the cfs_rq, freed with it
    t = sub(t, "\t\tinit_tg_cfs_entry(tg, cfs_rq, se, i, parent->se[i]);\n",
            "\t\tinit_tg_cfs_entry(tg, cfs_rq, se, i, parent->se[i]);\n"
            "\t\tds_bw_cfs_rq_alloc(cfs_rq);\n", "fair.c alloc hook")
    t = sub(t, "\tfor_each_possible_cpu(i) {\n\t\tif (tg->cfs_rq)\n\t\t\tkfree(tg->cfs_rq[i]);\n",
            "\tfor_each_possible_cpu(i) {\n\t\tif (tg->cfs_rq)\n\t\t\tds_bw_cfs_rq_free(tg->cfs_rq[i]);\n"
            "\t\tif (tg->cfs_rq)\n\t\t\tkfree(tg->cfs_rq[i]);\n", "fair.c free hook")
    t = sub(t, "\tkfree(tg->cfs_rq);\n\tkfree(tg->se);\n}",
            "\tkfree(tg->cfs_rq);\n\tkfree(tg->se);\n\tds_bw_tg_free(tg);\n}",
            "fair.c tg free hook")

    p.write_text(t)
    return True


def patch_core_c(root: Path) -> bool:
    p = root / "kernel/sched/core.c"
    t = read(p)
    if "ds_bw_activate()" in t:
        return False

    t = enable_guards(t)
    t = t.replace("struct cfs_bandwidth", "struct ds_cfs_bandwidth")
    t = t.replace("&tg->cfs_bandwidth", "ds_tg_bw(tg)")
    t = t.replace("&root_task_group.cfs_bandwidth", "ds_tg_bw(&root_task_group)")
    t = rewrite_bw_members(t)
    t = rewrite_fields(t)

    # the fast path stays stock until a quota is actually configured
    anchor = "static int tg_set_cfs_bandwidth(struct task_group *tg, u64 period, u64 quota,\n"
    if anchor not in t:
        die("core.c: tg_set_cfs_bandwidth not found")
    idx = t.index(anchor)
    brace = t.index("\n{\n", idx)
    # after the declaration block: a statement before declarations is not C
    body = t.index("\n\n", brace + 3)
    t = t[:body] + "\n\tds_bw_activate();\n" + t[body:]

    p.write_text(t)
    return True


def patch_debug_c(root: Path) -> bool:
    p = root / "kernel/sched/debug.c"
    t = read(p)
    if "ds_cfs_rq_bw(" in t:
        return False
    t = enable_guards(t)
    t = rewrite_fields(t)
    p.write_text(t)
    return True


def patch_makefile(root: Path) -> bool:
    p = root / "kernel/sched/Makefile"
    t = read(p)
    if "ds_bandwidth.o" in t:
        return False
    anchor = "obj-y += fair.o\n"
    if anchor not in t:
        die("kernel/sched/Makefile: fair.o line not found")
    p.write_text(t.replace(anchor, anchor + "obj-y += ds_bandwidth.o\n", 1))
    return True


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: ds_cfs_bandwidth.py <kernel/common>")
    root = Path(sys.argv[1])
    sched = root / "kernel/sched"
    if not sched.is_dir():
        die(f"{sched}: not a kernel tree")

    for name in ("ds_bandwidth.h", "ds_bandwidth.c"):
        src = HERE / name
        if not src.is_file():
            die(f"{src}: not found")
        dst = sched / name
        if not dst.is_file() or dst.read_bytes() != src.read_bytes():
            shutil.copyfile(src, dst)
            print(f"{name} installed")

    changed = any([patch_sched_h(root), patch_fair_c(root), patch_core_c(root),
                   patch_debug_c(root), patch_makefile(root)])
    print("ds cfs bandwidth: wired" if changed else "ds cfs bandwidth: already wired")


if __name__ == "__main__":
    main()
