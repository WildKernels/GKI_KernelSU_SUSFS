#!/usr/bin/env python3
"""Fix fanotify_fdinfo() arity in fs/notify/fdinfo.c after the SUSFS patch.

The 5.10/5.15/6.1 SUSFS patches widen show_fdinfo() to a 3-argument callback
when SUS_MOUNT or SUS_KSTAT is on:

    #if defined(CONFIG_KSU_SUSFS_SUS_MOUNT) || defined(CONFIG_KSU_SUSFS_SUS_KSTAT)
    static void show_fdinfo(struct seq_file *m, struct file *f,
                            void (*show)(struct seq_file *m,
                                         struct fsnotify_mark *mark,
                                         struct file *file))
    ...
            show(m, mark, f);

They adapt the inotify callbacks to that shape but not the fanotify one, so
fanotify_fdinfo() stays 2-argument. That is invisible while CONFIG_FANOTIFY=n,
because the whole block compiles out. With fanotify enabled it is a hard error:

    fs/notify/fdinfo.c:221:20: error: incompatible function pointer types passing
      'void (struct seq_file *, struct fsnotify_mark *)' to parameter of type
      'void (*)(struct seq_file *, struct fsnotify_mark *, struct file *)'

Add the missing `struct file *file` parameter to fanotify_fdinfo() whenever
show_fdinfo() is in the widened form. The parameter is unused by design (the
inotify side is what needs `file` for sus_mount path resolution), and the kernel
does not build with -Wunused-parameter.

Idempotent, anchored, fails loudly if the file is in neither expected shape.

Usage: susfs_fdinfo_fanotify_arity.py <kernel/common>
"""

import os
import re
import sys
from typing import NoReturn

WIDE_SHOW = re.compile(
    r"static void show_fdinfo\(struct seq_file \*m, struct file \*f,\s*\n"
    r"\s*void \(\*show\)\(struct seq_file \*m,\s*\n"
    r"\s*struct fsnotify_mark \*mark,\s*\n"
    r"\s*struct file \*file\)\)"
)
FAN_2ARG = re.compile(
    r"static void fanotify_fdinfo\(struct seq_file \*m, struct fsnotify_mark \*mark\)"
)
FAN_3ARG = re.compile(
    r"static void fanotify_fdinfo\(struct seq_file \*m, struct fsnotify_mark \*mark,"
    r"\s*\n?\s*struct file \*file\)"
)


def die(msg: str) -> NoReturn:
    sys.exit(f"ERROR: {msg}")


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: susfs_fdinfo_fanotify_arity.py <kernel/common>")
    path = os.path.join(sys.argv[1].rstrip("/"), "fs/notify/fdinfo.c")
    if not os.path.exists(path):
        print("  fdinfo.c: not present (nothing to do)")
        return

    src = open(path, encoding="utf-8").read()

    if not WIDE_SHOW.search(src):
        print("  fdinfo.c: show_fdinfo() is not widened - nothing to do")
        return
    if FAN_3ARG.search(src):
        print("  fdinfo.c: fanotify_fdinfo() already takes file")
        return
    if not FAN_2ARG.search(src):
        # fanotify may be compiled out of this tree entirely.
        print("  fdinfo.c: no 2-argument fanotify_fdinfo() found - nothing to do")
        return

    src = FAN_2ARG.sub(
        "static void fanotify_fdinfo(struct seq_file *m, struct fsnotify_mark *mark,\n"
        "\t\t\t     struct file *file)",
        src,
        count=1,
    )
    open(path, "w", encoding="utf-8").write(src)

    check = open(path, encoding="utf-8").read()
    if not FAN_3ARG.search(check):
        die("fdinfo.c: fanotify_fdinfo() still 2-argument after rewrite")
    print("  fdinfo.c: fanotify_fdinfo() widened to match show_fdinfo()")


if __name__ == "__main__":
    main()
