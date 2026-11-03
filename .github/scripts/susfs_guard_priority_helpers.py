#!/usr/bin/env python3
"""Guard the SUSFS priority-uid-filter credential helpers (upstream oversight).

susfs.c defines two static helpers used only by the priority-uid-filter code:

  static struct cred *susfs_switch_to_ksu_domain(void)
  static void susfs_restore_creds(struct cred *orig_cred)

Every call site lives inside `#ifdef CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER`
(block spans roughly 1376-1805 in the 6.12 tip), but the definitions themselves
were added outside that guard. When the symbol is not defined - which is the case
for BakaSU's kernel tree on the older branches, whose Kconfig predates the
feature - the users compile out and the definitions become dead code, and GKI
turns that into an error:

  fs/susfs.c:183:21: error: unused function 'susfs_switch_to_ksu_domain'
  fs/susfs.c:217:13: error: unused function 'susfs_restore_creds'

Wrap the definitions in the same switch that guards their only callers. This is
correct in both directions: with the symbol on, nothing changes; with it off, the
helpers disappear along with their call sites.

Idempotent, anchor-checked.

Usage: susfs_guard_priority_helpers.py <path-to-fs/susfs.c>
"""

import os
import sys
from typing import NoReturn

GUARD = "#ifdef CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER\n"
ENDIF = "#endif // #ifdef CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER /* credential helpers */\n"

SWITCH_SIG = "static struct cred *susfs_switch_to_ksu_domain(void) {"
RESTORE_SIG = "static void susfs_restore_creds(struct cred *orig_cred) {"
DOC_START = " * Switches the selinux domain of the current process to the KernelSU one"


def die(msg: str) -> NoReturn:
    sys.exit(f"ERROR: {msg}")


def brace_end(text: str, sig: str) -> int:
    start = text.find(sig)
    if start < 0:
        die(f"signature not found: {sig}")
    brace = text.find("{", start)
    depth, i = 0, brace
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    die(f"unbalanced braces for {sig}")


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: susfs_guard_priority_helpers.py <path-to-fs/susfs.c>")
    path = sys.argv[1]
    if not os.path.exists(path):
        die(f"{path}: not found")
    src = open(path, encoding="utf-8").read()

    if "credential helpers */" in src:
        print("  susfs.c: credential helpers already guarded")
        return
    if SWITCH_SIG not in src:
        print("  susfs.c: credential helpers not present (nothing to do)")
        return

    # comment block that documents susfs_switch_to_ksu_domain()
    doc = src.find(DOC_START)
    start = src.rfind("/*", 0, doc) if doc > 0 else src.find(SWITCH_SIG)
    if start < 0:
        die("could not locate the helper's doc comment")
    if SWITCH_SIG not in src[start:start + 4000]:
        die("doc comment does not precede susfs_switch_to_ksu_domain()")

    end = brace_end(src, RESTORE_SIG)
    src = src[:end] + "\n" + ENDIF + src[end:]
    src = src[:start] + GUARD + src[start:]

    open(path, "w", encoding="utf-8").write(src)

    check = open(path, encoding="utf-8").read()
    guard_at = check.find(GUARD)
    switch_at = check.find(SWITCH_SIG)
    restore_at = check.find(RESTORE_SIG)
    endif_at = check.find(ENDIF)
    if not (0 <= guard_at < switch_at < restore_at < endif_at):
        die("guard did not enclose both helpers after write")
    print("  susfs.c: credential helpers wrapped in CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER")


if __name__ == "__main__":
    main()
