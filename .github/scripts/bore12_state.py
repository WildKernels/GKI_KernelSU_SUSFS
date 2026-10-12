#!/usr/bin/env python3
"""Move BORE 7.0.0's inline `struct bore_ctx bore` member out of task_struct.

BORE 7.0.0 embeds a 40-byte bore_ctx in task_struct (between scx and
sched_class). Inline, it shifts every member after it - the KMI break that
bootlooped stock-vendor 6.12 devices (run 38015274643). bore_task_slots_7.py
fixed that by flattening the members into task_struct's KABI slots 4..8, but
that occupies FIVE slots, and Google is actively consuming 6.12 slots: slots
1..3 went to dmabuf_info / erratum-4193714 / user_dumpable between the
2025-06 and 2026-09 sublevels. Slot 4 is the next one Google will take, and
our block starts exactly there.

So this script relocates the WHOLE context out-of-line instead (the proven
6.6 bore_state design):

  1. Remove the inline `struct bore_ctx bore;` member (stock layout restored).
  2. task_struct consumes only ANDROID_KABI_RESERVE(8) - the LAST slot,
     farthest from Google's low-slot consumption frontier - for
     `struct bore_ctx *bore`. Under __GENKSYMS__ the macro collapses to the
     stock reserved u64, so KMI symbol CRCs are unchanged. Slot 8 is free in
     every built 6.12 sublevel (verified stock sched.h 6.12.23-2025-06 and
     6.12.92-2026-09_r4).
  3. Companion bore12_flat.py rewrites every `p->bore.X` accessor to
     `p->bore->X`, drops the & on ctx-shorthand locals, NULL-guards the
     entry points, allocates in copy_process, and frees in __put_task_struct.

Usage: bore12_state.py <sched.h>
Idempotent: skips files carrying the marker; fails loudly on anchor misses.
"""
import sys

MARK = "/* bore-kabi: bore_ctx lives out-of-line; task_struct slot 8 = pointer */"

INLINE_OLD = (
    "#ifdef CONFIG_SCHED_BORE\n"
    "\tstruct bore_ctx\t\t\tbore;\n"
    "#endif /* CONFIG_SCHED_BORE */\n"
)

RESERVE8_OLD = "\tANDROID_KABI_RESERVE(8);\n"

RESERVE8_NEW = (
    "#ifdef CONFIG_SCHED_BORE\n"
    "\t" + MARK + "\n"
    "\tANDROID_KABI_USE(8, struct bore_ctx *bore);\n"
    "#else\n"
    "\tANDROID_KABI_RESERVE(8);\n"
    "#endif\n"
)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: bore12_state.py <sched.h>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    with open(path) as f:
        src = f.read()

    if MARK in src:
        print("bore12-state: already relocated; nothing to do")
        return 0

    if "struct bore_ctx {" not in src:
        print("bore12-state: struct bore_ctx definition missing "
              "(did the BORE patch apply?)", file=sys.stderr)
        return 1

    if src.count(INLINE_OLD) != 1:
        print(f"bore12-state: found {src.count(INLINE_OLD)} inline bore_ctx "
              "member blocks (expected 1)", file=sys.stderr)
        return 1

    if src.count(RESERVE8_OLD) != 1:
        print(f"bore12-state: found {src.count(RESERVE8_OLD)} "
              "ANDROID_KABI_RESERVE(8) lines (expected 1); Google may have "
              "consumed slot 8 - relocate manually", file=sys.stderr)
        return 1

    out = src.replace(INLINE_OLD, "", 1)
    out = out.replace(RESERVE8_OLD, RESERVE8_NEW, 1)

    with open(path, "w") as f:
        f.write(out)
    print("bore12-state: inline bore_ctx member removed, "
          "task_struct slot 8 = pointer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
