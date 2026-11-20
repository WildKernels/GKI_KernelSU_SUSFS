#!/usr/bin/env python3
"""Wire the pids controller into a GKI tree without touching the ABI.

DroidSpaces asks for CONFIG_CGROUP_PIDS so a container can be given a process
limit. Enabling it is what breaks: registering the pids subsystem increments
CGROUP_SUBSYS_COUNT, which resizes fixed arrays inside struct cgroup and struct
css_set, so prebuilt vendor modules read the wrong offsets (measured: 3241 of
8865 symbol CRCs moved, and even with the CRCs forced back to stock the device
did not boot).

This installs a controller-free implementation with the controller's behaviour:

  kernel/cgroup/pidslimit.c   counters charged up the hierarchy, can_fork charge
                              /check/rollback, cancel_fork and exit uncharge,
                              migration check and charge transfer, the four
                              pids.* files, pollable pids.events
  kernel/cgroup/Makefile      build it
  kernel/cgroup/cgroup.c      the files in cgroup_base_files[], state allocated
                              at cgroup_create and freed at destroy, hooks in
                              cancel_fork / exit / migrate, and the controller
                              advertised in cgroup.controllers
  kernel/fork.c               ds_pids_can_fork() after cgroup_can_fork()

None of that changes a struct layout, so the ABI stays byte-identical to stock
and no genksyms shadow is involved.

Usage: ds_pids_limit.py <kernel/common>
Idempotent: re-running on an already-patched tree is a no-op.
"""
import shutil
import sys
from pathlib import Path

MARKER = "ds_pids_can_fork"
CFTYPES_HOOK = "DroidSpaces pids limits"


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


def patch_cgroup_makefile(root: Path) -> bool:
    p = root / "kernel/cgroup/Makefile"
    t = read(p)
    if "pidslimit.o" in t:
        return False
    line = "obj-y := cgroup.o rstat.o namespace.o cgroup-v1.o freezer.o\n"
    if line not in t:
        die("kernel/cgroup/Makefile: unexpected obj-y line")
    # after the ':=' line: a preceding '+=' would be overwritten by it
    p.write_text(t.replace(line, line + "obj-y += pidslimit.o\n", 1))
    return True


def patch_cgroup_c(root: Path) -> bool:
    p = root / "kernel/cgroup/cgroup.c"
    t = read(p)
    changed = False

    if CFTYPES_HOOK not in t:
        anchor = '\t{\n\t\t.name = "cpu.stat",'
        inject = ("\t/* DroidSpaces pids limits - no subsystem, no ABI change */\n"
                  '\t{\n\t\t.name = "pids.max",\n'
                  "\t\t.seq_show = ds_pids_max_show,\n"
                  "\t\t.write = ds_pids_max_write,\n"
                  "\t},\n"
                  '\t{\n\t\t.name = "pids.current",\n'
                  "\t\t.seq_show = ds_pids_current_show,\n"
                  "\t},\n"
                  '\t{\n\t\t.name = "pids.peak",\n'
                  "\t\t.seq_show = ds_pids_peak_show,\n"
                  "\t},\n"
                  '\t{\n\t\t.name = "pids.events",\n'
                  "\t\t.seq_show = ds_pids_events_show,\n"
                  "\t},\n")
        t = sub(t, anchor, inject + anchor, "cgroup.c base files")
        changed = True

    if "int ds_pids_alloc(struct cgroup *cgrp);" not in t:
        decl_anchor = "static struct cftype cgroup_base_files[];\n"
        decl = ("int ds_pids_alloc(struct cgroup *cgrp);\n"
                "void ds_pids_free(struct cgroup *cgrp);\n"
                "int ds_pids_can_fork(struct task_struct *task);\n"
                "void ds_pids_cancel_fork(struct task_struct *task);\n"
                "void ds_pids_exit(struct task_struct *task);\n"
                "void ds_pids_migrate(struct task_struct *task, struct cgroup *dst);\n"
                "int ds_pids_migrate_check(struct cgroup_taskset *tset);\n"
                "int ds_pids_max_show(struct seq_file *seq, void *v);\n"
                "ssize_t ds_pids_max_write(struct kernfs_open_file *of, char *buf,\n"
                "\t\t\t   size_t nbytes, loff_t off);\n"
                "int ds_pids_current_show(struct seq_file *seq, void *v);\n"
                "int ds_pids_peak_show(struct seq_file *seq, void *v);\n"
                "int ds_pids_events_show(struct seq_file *seq, void *v);\n")
        t = sub(t, decl_anchor, decl + decl_anchor, "cgroup.c declarations")
        changed = True

    if "ds_pids_alloc(cgrp)" not in t:
        anchor = "\tcgroup_propagate_control(cgrp);\n\n\treturn cgrp;\n"
        new = ("\tcgroup_propagate_control(cgrp);\n\n"
               "\t/* DroidSpaces pids: state up front, the charge paths are atomic */\n"
               "\tif (ds_pids_alloc(cgrp)) {\n"
               "\t\tret = -ENOMEM;\n"
               "\t\tgoto out_psi_free;\n"
               "\t}\n\n"
               "\treturn cgrp;\n")
        t = sub(t, anchor, new, "cgroup.c cgroup_create")
        changed = True

    if "ds_pids_free(cgrp)" not in t:
        sig = "static int cgroup_destroy_locked(struct cgroup *cgrp)\n"
        if sig not in t:
            die("cgroup.c: cgroup_destroy_locked not found")
        idx = t.rindex(sig)
        brace = t.index("\n{\n", idx)
        decl_end = t.index("\tint ssid;\n", brace) + len("\tint ssid;\n")
        t = t[:decl_end] + "\n\tds_pids_free(cgrp);\n" + t[decl_end:]
        changed = True

    if "ds_pids_cancel_fork(child)" not in t:
        anchor = ("void cgroup_cancel_fork(struct task_struct *child,\n"
                  "\t\t\tstruct kernel_clone_args *kargs)\n{\n"
                  "\tstruct cgroup_subsys *ss;\n\tint i;\n\n")
        t = sub(t, anchor,
                anchor + "\t/* DroidSpaces pids: the fork failed, give the charge back */\n"
                         "\tds_pids_cancel_fork(child);\n\n",
                "cgroup.c cancel_fork")
        changed = True

    if "ds_pids_exit(tsk)" not in t:
        anchor = "\tcss_set_move_task(tsk, cset, NULL, false);\n"
        t = sub(t, anchor,
                anchor + "\t/* DroidSpaces pids: the task is leaving the hierarchy */\n"
                         "\tds_pids_exit(tsk);\n",
                "cgroup.c cgroup_exit")
        changed = True

    if "ds_pids_migrate_check(tset)" not in t:
        anchor = ("\t/*\n"
                  "\t * Now that we're guaranteed success, proceed to move all tasks to\n")
        new = ("\t/* DroidSpaces pids: destination limits, before the commit point */\n"
               "\tret = ds_pids_migrate_check(tset);\n"
               "\tif (ret) {\n"
               "\t\tfailed_ssid = CGROUP_SUBSYS_COUNT;\n"
               "\t\tgoto out_cancel_attach;\n"
               "\t}\n\n") + anchor
        t = sub(t, anchor, new, "cgroup.c migrate check")
        changed = True

    if "ds_pids_migrate(task, to_cset->dfl_cgrp)" not in t:
        anchor = "\t\t\tcss_set_move_task(task, from_cset, to_cset, true);\n"
        t = sub(t, anchor,
                anchor + "\t\t\tds_pids_migrate(task, to_cset->dfl_cgrp);\n",
                "cgroup.c migrate move")
        changed = True

    if changed:
        p.write_text(t)
    return changed


def patch_controller_view(root: Path) -> bool:
    """Advertise pids in cgroup.controllers and accept +pids in subtree_control.

    DroidSpaces does not probe for the file: check.c gates on
    ds_cgroup_has_controller("pids"), discover.c re-checks it per cgroup, and
    lifecycle.c only writes "+pids" when the root list names it. Without the
    advertisement the limit is skipped even though pids.max exists and works.

    Both edits are interface-only - no struct, no symbol, no CRC changes.
    """
    p = root / "kernel/cgroup/cgroup.c"
    t = read(p)
    changed = False

    show_old = "\tif (printed)\n\t\tseq_putc(seq, '\\n');\n}\n"
    if 'seq_puts(seq, "pids")' not in t:
        show_new = ("\t/* DroidSpaces: pids limits are provided without a subsystem, so\n"
                    "\t * advertise the controller here rather than registering one. */\n"
                    "\tif (printed)\n"
                    "\t\tseq_putc(seq, ' ');\n"
                    '\tseq_puts(seq, "pids");\n'
                    "\tseq_putc(seq, '\\n');\n"
                    "}\n")
        t = sub(t, show_old, show_new, "cgroup.c controller list")
        changed = True

    write_old = "\t\tif (ssid == CGROUP_SUBSYS_COUNT)\n\t\t\treturn -EINVAL;\n"
    if 'strcmp(tok + 1, "pids")' not in t:
        write_new = ("\t\tif (ssid == CGROUP_SUBSYS_COUNT) {\n"
                     "\t\t\t/* pids has no subsystem: accept the token, nothing to enable */\n"
                     '\t\t\tif (!strcmp(tok + 1, "pids"))\n'
                     "\t\t\t\tcontinue;\n"
                     "\t\t\treturn -EINVAL;\n"
                     "\t\t}\n")
        t = sub(t, write_old, write_new, "cgroup.c subtree_control")
        changed = True

    if changed:
        p.write_text(t)
    return changed


def patch_fork_c(root: Path) -> bool:
    p = root / "kernel/fork.c"
    t = read(p)
    if MARKER in t:
        return False

    anchor = ("\tretval = cgroup_can_fork(p, args);\n"
              "\tif (retval)\n"
              "\t\tgoto bad_fork_cleanup_dmabuf;\n")
    inject = anchor + (
        "\n\t/* DroidSpaces pids.max: charge, check, roll back on refusal. */\n"
        "\tretval = ds_pids_can_fork(current);\n"
        "\tif (retval)\n"
        "\t\tgoto bad_fork_cancel_cgroup;\n")
    t = sub(t, anchor, inject, "fork.c can_fork")

    inc = "#include <linux/cgroup.h>\n"
    t = sub(t, inc, inc + "int ds_pids_can_fork(struct task_struct *task);\n",
            "fork.c declaration")

    p.write_text(t)
    return True


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: ds_pids_limit.py <kernel/common>")
    root = Path(sys.argv[1])
    src = Path(__file__).resolve().parent.parent / "patches/ds-limits/pidslimit.c"
    if not src.is_file():
        die(f"{src}: not found")

    dst = root / "kernel/cgroup/pidslimit.c"
    if not dst.is_file() or dst.read_bytes() != src.read_bytes():
        shutil.copyfile(src, dst)
        print("pidslimit.c installed")

    changed = any([
        patch_cgroup_makefile(root),
        patch_cgroup_c(root),
        patch_controller_view(root),
        patch_fork_c(root),
    ])
    print("ds pids limit: wired" if changed else "ds pids limit: already wired")


if __name__ == "__main__":
    main()
