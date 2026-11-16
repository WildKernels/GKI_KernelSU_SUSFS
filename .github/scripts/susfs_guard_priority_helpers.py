#!/usr/bin/env python3
"""Keep the SUSFS credential helpers compiling whether or not the priority-uid
filter is enabled.

fs/susfs.c defines two static helpers:

  static struct cred *susfs_switch_to_ksu_domain(void)
  static void susfs_restore_creds(struct cred *orig_cred)

When they were introduced, only the priority-uid-filter switch called them, so
a tree without CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER - BakaSU's Kconfig has no
such symbol at all, so olddefconfig drops the entry - compiled them as dead
code and GKI's -Werror killed the build:

  fs/susfs.c:183:21: error: unused function 'susfs_switch_to_ksu_domain'
  fs/susfs.c:217:13: error: unused function 'susfs_restore_creds'

The old fix wrapped the definitions in the same config guard. That is now wrong:
the sus_path uid filter path calls susfs_restore_creds as well (the
susfs_sus_path_app_strings worker's error exits), so with the guard in place and
the priority symbol off, the definition disappears while those calls remain:

  fs/susfs.c:779:2: error: call to undeclared function 'susfs_restore_creds'

__maybe_unused solves both directions: the helpers stay visible to every caller,
and a build where nothing calls them no longer trips -Wunused-function. Any
guard this script added earlier is removed, so re-running on an already-patched
tree upgrades it.

Idempotent, anchor-checked.

Usage: susfs_guard_priority_helpers.py <path-to-fs/susfs.c>
"""

import os
import sys
from typing import NoReturn

GUARD = "#ifdef CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER\n"
ENDIF = "#endif // #ifdef CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER /* credential helpers */\n"

SWITCH_SIG = "static struct cred *susfs_switch_to_ksu_domain(void) {"
SWITCH_NEW = "static struct cred * __maybe_unused susfs_switch_to_ksu_domain(void) {"
RESTORE_SIG = "static void susfs_restore_creds(struct cred *orig_cred) {"
RESTORE_NEW = "static void __maybe_unused susfs_restore_creds(struct cred *orig_cred) {"
DOC_START = " * Switches the selinux domain of the current process to the KernelSU one"


def die(msg: str) -> NoReturn:
    sys.exit(f"ERROR: {msg}")


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: susfs_guard_priority_helpers.py <path-to-fs/susfs.c>")
    path = sys.argv[1]
    if not os.path.exists(path):
        die(f"{path}: not found")
    src = open(path, encoding="utf-8").read()
    original = src
    notes = []

    # Upgrade path: undo the guard this script used to insert. It has to be
    # removed surgically - upstream has its own, legitimate
    # "#ifdef CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER" around the switch block
    # (~line 1785), and removing every occurrence would delete real code.
    if ENDIF in src:
        src = src.replace(ENDIF, "", 1)
        doc_at = src.find(DOC_START)
        if doc_at > 0:
            guard_at = src.rfind(GUARD, 0, doc_at)
            between = src[guard_at + len(GUARD):doc_at] if guard_at >= 0 else None
            if between is not None and between.strip() in ("/*", ""):
                src = src[:guard_at] + src[guard_at + len(GUARD):]
                notes.append("removed our guard around the credential helpers")
            else:
                notes.append("removed our guard's #endif; head not adjacent, left alone")
        else:
            notes.append("removed our guard's #endif")

    if SWITCH_NEW in src and RESTORE_NEW in src:
        if src != original:
            open(path, "w", encoding="utf-8").write(src)
        print("  susfs.c: credential helpers already __maybe_unused" +
              ("; " + "; ".join(notes) if notes else ""))
        return

    if SWITCH_SIG in src:
        src = src.replace(SWITCH_SIG, SWITCH_NEW, 1)
        notes.append("susfs_switch_to_ksu_domain -> __maybe_unused")
    if RESTORE_SIG in src:
        src = src.replace(RESTORE_SIG, RESTORE_NEW, 1)
        notes.append("susfs_restore_creds -> __maybe_unused")

    if src == original:
        print("  susfs.c: credential helpers not present (nothing to do)")
        return

    open(path, "w", encoding="utf-8").write(src)

    check = open(path, encoding="utf-8").read()
    if ENDIF in check:
        die("the config guard is still present after rewrite")
    for sig in (SWITCH_NEW, RESTORE_NEW):
        if sig not in check:
            die(f"{sig} missing after rewrite")
    print("  susfs.c: " + "; ".join(notes))


if __name__ == "__main__":
    main()
