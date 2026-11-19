#!/usr/bin/env python3
"""Wire pids.max / pids.current into a GKI tree without touching the ABI.

DroidSpaces asks for CONFIG_CGROUP_PIDS so a container can be given a process
limit. Enabling it is what breaks: registering the pids subsystem increments
CGROUP_SUBSYS_COUNT, which resizes fixed arrays inside struct cgroup and struct
css_set, so prebuilt vendor modules read the wrong offsets (measured: 3241 of
8865 symbol CRCs moved, and even with the CRCs forced back to stock the device
did not boot).

This installs a controller-free implementation instead:

  kernel/cgroup/pidslimit.c   new file: state in an xarray keyed by cgroup,
                              pids.max / pids.current cftypes, fork check
  kernel/cgroup/Makefile      build it
  kernel/cgroup/cgroup.c      add the two files to cgroup_base_files[], drop the
                              state when a cgroup is destroyed
  kernel/fork.c               refuse the fork when an ancestor is at its limit

None of that changes a struct layout, so the ABI stays byte-identical to stock
and no genksyms shadow is involved.

Usage: ds_pids_limit.py <kernel/common>
Idempotent: re-running on an already-patched tree is a no-op.
"""
import shutil
import sys
from pathlib import Path

MARKER = "ds_pids_limit_check"
CFTYPES_HOOK = "DroidSpaces pids limits"


def die(msg: str):
    sys.stderr.write(f"error: {msg}\n")
    sys.exit(1)


def read(p: Path) -> str:
    if not p.is_file():
        die(f"{p}: not found")
    return p.read_text()


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
        anchor = "\t{\n\t\t.name = \"cpu.stat\","
        if anchor not in t:
            die("cgroup.c: cgroup_base_files anchor not found")
        inject = ("\t/* DroidSpaces pids limits - no subsystem, no ABI change */\n"
                  "\t{\n\t\t.name = \"pids.max\",\n"
                  "\t\t.seq_show = ds_pids_max_show,\n"
                  "\t\t.write = ds_pids_max_write,\n"
                  "\t},\n"
                  "\t{\n\t\t.name = \"pids.current\",\n"
                  "\t\t.seq_show = ds_pids_current_show,\n"
                  "\t},\n")
        t = t.replace(anchor, inject + anchor, 1)
        changed = True

    if "int ds_pids_max_show(struct seq_file *seq, void *v);" not in t:
        # drop the standalone file array from pidslimit.c and declare the two
        # handlers here instead
        decl_anchor = "static struct cftype cgroup_base_files[];\n"
        if decl_anchor not in t:
            die("cgroup.c: forward declaration anchor not found")
        decl = ("int ds_pids_max_show(struct seq_file *seq, void *v);\n"
                "ssize_t ds_pids_max_write(struct kernfs_open_file *of, char *buf,\n"
                "\t\t\t   size_t nbytes, loff_t off);\n"
                "int ds_pids_current_show(struct seq_file *seq, void *v);\n"
                "void ds_pids_limit_free(struct cgroup *cgrp);\n")
        t = t.replace(decl_anchor, decl + decl_anchor, 1)
        changed = True

    if "ds_pids_limit_free(cgrp)" not in t:
        # The file carries a forward declaration of the same name earlier on, and
        # the definition has lock-annotation attributes between its signature and
        # its brace, so take the last occurrence and find the brace after it.
        sig = "static int cgroup_destroy_locked(struct cgroup *cgrp)\n"
        if sig not in t:
            die("cgroup.c: cgroup_destroy_locked not found")
        idx = t.rindex(sig)
        brace = t.index("\n{\n", idx)
        # after the locals: a statement before declarations is not kernel style
        decl_end = t.index("\tint ssid;\n", brace) + len("\tint ssid;\n")
        t = t[:decl_end] + "\n\tds_pids_limit_free(cgrp);\n" + t[decl_end:]
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
    if anchor not in t:
        die("fork.c: cgroup_can_fork block not found")

    inject = anchor + (
        "\n\t/* DroidSpaces pids.max: refuse the fork before the child is visible. */\n"
        "\tretval = ds_pids_limit_check(current);\n"
        "\tif (retval)\n"
        "\t\tgoto bad_fork_cancel_cgroup;\n")

    decl_anchor = "unsigned long _ksu_get_task_flags"  # not used; keep simple
    t = t.replace(anchor, inject, 1)

    if "int ds_pids_limit_check(struct task_struct *task);" not in t:
        inc = "#include <linux/cgroup.h>\n"
        if inc not in t:
            die("fork.c: linux/cgroup.h include not found")
        t = t.replace(inc, inc + "int ds_pids_limit_check(struct task_struct *task);\n", 1)

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
        patch_fork_c(root),
    ])
    print("ds pids limit: wired" if changed else "ds pids limit: already wired")


if __name__ == "__main__":
    main()
