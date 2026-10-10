#!/usr/bin/env python3
"""Relocate BORE 7.0.0's inline task_struct bore_ctx into KABI reserve slots.

BORE 7.0.0 (6.12/6.18) adds `struct bore_ctx bore;` as an INLINE member of
task_struct (right after the scx member). task_struct is the most
vendor-referenced struct in the KMI: every android_vh vendor hook passes a
task_struct*, so a 40-byte inline insertion shifts every later member and
stock vendor modules read wrong offsets - users bootloop (reported on 6.12
builds after run 38015274643).

The fix overlays the state onto the five consecutive free reserve slots in
task_struct's tail:

  slot 4: u64 burst_time
  slot 5: u64 credit_sleep
  slot 6: u16 prev_penalty, u16 curr_penalty, u16 penalty,
          bool stop_update, bool futex_waiting   (6B payload)
  slot 7: struct bore_bc subtree
  slot 8: struct bore_bc group

bore_ctx is 40 raw bytes = 5 x 8B slots exactly, and the members stay
flat-accessible because ANDROID_KABI_USE unions them in place: `p->bore.X`
becomes `p->X`. No field is narrowed; bore_bc keeps its packed
timestamp:48|penalty:16 u64 shape.

Under genksyms (KMI symbol generation) the macro collapses to the stock
reserved u64, so the emitted symbol list is unchanged - same property the
working 5.10/5.15/6.1 sched_entity relocation (bore_kabi_612.py) depends on.

Layout verified by compiling the standalone struct: stock tail 40 ==
slotted tail 40, all _Static_asserts green.

Usage: bore_task_slots_7.py <sched.h> [sched.h ...]
Idempotent: skips files already carrying the marker.
"""
import sys

MARK = "/* bore-kabi: bore_ctx lives in ANDROID_KABI_RESERVE(4..8) */"

# The inline bore_ctx member the 7.0.0 patch adds to task_struct.
INLINE_OLD = (
    "#ifdef CONFIG_SCHED_BORE\n"
    "\tstruct bore_ctx\t\t\tbore;\n"
    "#endif /* CONFIG_SCHED_BORE */\n"
)

# The task_struct tail slots we consume. Note ANDROID_KABI_USE(3) region and
# errata-slot 2 stay untouched; slots 4-8 are free on both 6.12 and 6.18.
RES_OLD = (
    "\tANDROID_KABI_RESERVE(4);\n"
    "\tANDROID_KABI_RESERVE(5);\n"
    "\tANDROID_KABI_RESERVE(6);\n"
    "\tANDROID_KABI_RESERVE(7);\n"
    "\tANDROID_KABI_RESERVE(8);\n"
)

# Helper macro for slot 6's multi-member payload: commas introduced by
# macro EXPANSION are not argument separators (same trick the 5.1.0
# relocation uses for its slots 3/4).
SLOT6_HELPER = (
    "#ifdef CONFIG_SCHED_BORE\n"
    "/* bore-kabi: slot-6 payload (see ANDROID_KABI_USE(6) below) */\n"
    "#define __BORE_TS_SLOT6 struct { u16 prev_penalty; u16 curr_penalty; \\\n"
    "\tu16 penalty; bool stop_update; bool futex_waiting; }\n"
    "#endif /* CONFIG_SCHED_BORE */\n"
    "\n"
)

RES_NEW = (
    "#ifdef CONFIG_SCHED_BORE\n"
    "\t" + MARK + "\n"
    "\tANDROID_KABI_USE(4, u64 burst_time);\n"
    "\tANDROID_KABI_USE(5, u64 credit_sleep);\n"
    "\tANDROID_KABI_USE(6, __BORE_TS_SLOT6);\n"
    "\tANDROID_KABI_USE(7, struct bore_bc subtree);\n"
    "\tANDROID_KABI_USE(8, struct bore_bc group);\n"
    "#else\n"
    "\tANDROID_KABI_RESERVE(4);\n"
    "\tANDROID_KABI_RESERVE(5);\n"
    "\tANDROID_KABI_RESERVE(6);\n"
    "\tANDROID_KABI_RESERVE(7);\n"
    "\tANDROID_KABI_RESERVE(8);\n"
    "#endif\n"
)


def process(path: str) -> bool:
    with open(path, encoding="utf-8", errors="surrogateescape") as fh:
        src = fh.read()

    if MARK in src:
        print(f"bore-task-slots: {path}: already relocated")
        return True
    if INLINE_OLD not in src:
        # Not the 7.0.0 shape (5.x/6.6 generations put state elsewhere) -
        # not an error; the caller's shape gates handle reporting.
        print(f"bore-task-slots: {path}: no inline bore_ctx member (7.0.0 "
              f"shape absent); no edit")
        return True
    if src.count(RES_OLD) != 1:
        print(f"bore-task-slots: {path}: expected exactly 1 free-slot tail "
              f"(4..8), found {src.count(RES_OLD)}; aborting", file=sys.stderr)
        return False

    out = src.replace(INLINE_OLD, "", 1)
    out = out.replace("struct task_struct {",
                      SLOT6_HELPER + "struct task_struct {", 1)
    out = out.replace(RES_OLD, RES_NEW, 1)
    with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(out)
    print(f"bore-task-slots: {path}: bore_ctx relocated into slots 4..8 "
          f"(flat access, no narrowing, KMI tail preserved)")
    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    ok = all(process(p) for p in sys.argv[1:])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())