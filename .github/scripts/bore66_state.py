#!/usr/bin/env python3
"""Relocate BORE 5.9.6 (6.6) inline sched_entity burst state out-of-line.

BORE 5.9.6 stores its burst state INLINE in struct sched_entity: burst_time,
four u8 penalty/score fields, and two 24-byte spinlocked sched_burst_cache
structs (~64 bytes total). The 6.6 GKI KMI pins sched_entity structurally at
its stock size, so every member after the insertion (on_rq, vruntime, vlag,
slice, ...) shifts - a confirmed bootloop on at least one user's stock-vendor
device (6.6 BORE builds; the same failure class the 6.12 task_struct
insertion caused).

The caches cannot go into ANDROID_KABI slots: 24 bytes > 8-byte slots and
the kernel's _Static_assert refuses it (verified by compiling). So instead:

  1. Remove the inline fields from struct sched_entity (restores stock
     layout exactly).
  2. Define struct bore_state with the SAME field layout - both
     sched_burst_cache instances and all scalars - so the author's locking
     design and every cache-pointer identity are preserved unchanged.
  3. task_struct consumes free ANDROID_KABI_RESERVE(3) for
     'struct bore_state *bore_state' (precedent: dmabuf_info at slot 1).
     Under genksyms the macro collapses to the stock reserved u64, so the
     KMI symbol list is unchanged.
  4. Accessor translation (companion script bore66_flat.py): se->X becomes
     task_of(se)->bore_state->X, p->se.X becomes p->bore_state->X.
  5. Allocation: fork.c allocates the state right before sched_clone_bore
     (GFP_KERNEL, kzalloc so all fields zero - the 5.9.6 semantic is
     zero-init via reset_task_bore + spin_lock_init at first use); the
     free path kfrees NULL-safely in release_task, so tasks created before
     BORE init (and init_task until sched_bore_init allocates its own)
     carry NULL and every accessor is guarded by the bore_state != NULL
     check the companion script emits at the BORE entry points.

Usage: bore66_state.py <sched.h> [sched.h ...]
Idempotent: skips files carrying the marker.
"""
import sys

MARK = "/* bore-kabi: 6.6 burst state lives out-of-line via bore_state */"

# The struct sched_burst_cache definition block (kept as-is, reused inside
# bore_state). The inline sched_entity fields are what we remove.
SE_FIELDS_OLD = (
    "#ifdef CONFIG_SCHED_BORE\n"
    "\tu64\t\t\t\tburst_time;\n"
    "\tu8\t\t\t\tprev_burst_penalty;\n"
    "\tu8\t\t\t\tcurr_burst_penalty;\n"
    "\tu8\t\t\t\tburst_penalty;\n"
    "\tu8\t\t\t\tburst_score;\n"
    "\tstruct sched_burst_cache child_burst;\n"
    "\tstruct sched_burst_cache group_burst;\n"
    "#endif // CONFIG_SCHED_BORE\n"
)

BORE_STATE_DEF = (
    "#ifdef CONFIG_SCHED_BORE\n"
    "/* bore-kabi: 6.6 burst state lives out-of-line via bore_state.\n"
    " * Same field layout the 5.9.6 patch placed inline in sched_entity;\n"
    " * removed from there so sched_entity keeps its stock KMI layout.\n"
    " */\n"
    "struct bore_state {\n"
    "\tu64\t\t\t\tburst_time;\n"
    "\tu8\t\t\t\tprev_burst_penalty;\n"
    "\tu8\t\t\t\tcurr_burst_penalty;\n"
    "\tu8\t\t\t\tburst_penalty;\n"
    "\tu8\t\t\t\tburst_score;\n"
    "\tstruct sched_burst_cache child_burst;\n"
    "\tstruct sched_burst_cache group_burst;\n"
    "};\n"
    "#endif // CONFIG_SCHED_BORE\n"
)

# task_struct tail slots: 3 is free on 6.6 (1=dmabuf_info, 2=user_dumpable).
# Anchor on the dmabuf_info USE(1) - unique to task_struct - so sibling
# structs with plain RESERVE(3)+RESERVE(4) tails (mm_struct etc.) are not
# miscounted. The full block through RESERVE(8) is matched and slot 3
# replaced in place.
TS_SLOT3_OLD = (
    "\tANDROID_KABI_USE(1, struct task_dma_buf_info *dmabuf_info);\n"
    "\tANDROID_KABI_USE(2, struct {\n"
    "\t\t/* Save user-dumpable when mm goes away */\n"
    "\t\tunsigned\tuser_dumpable:1;\n"
    "\t\t});\n"
    "\n"
    "\tANDROID_KABI_RESERVE(3);\n"
    "\tANDROID_KABI_RESERVE(4);\n"
    "\tANDROID_KABI_RESERVE(5);\n"
    "\tANDROID_KABI_RESERVE(6);\n"
    "\tANDROID_KABI_RESERVE(7);\n"
    "\tANDROID_KABI_RESERVE(8);\n"
)

TS_SLOT3_NEW = (
    "\tANDROID_KABI_USE(1, struct task_dma_buf_info *dmabuf_info);\n"
    "\tANDROID_KABI_USE(2, struct {\n"
    "\t\t/* Save user-dumpable when mm goes away */\n"
    "\t\tunsigned\tuser_dumpable:1;\n"
    "\t\t});\n"
    "\n"
    "#ifdef CONFIG_SCHED_BORE\n"
    "\t" + MARK + "\n"
    "\tANDROID_KABI_USE(3, struct bore_state *bore_state);\n"
    "#else\n"
    "\tANDROID_KABI_RESERVE(3);\n"
    "#endif\n"
    "\tANDROID_KABI_RESERVE(4);\n"
    "\tANDROID_KABI_RESERVE(5);\n"
    "\tANDROID_KABI_RESERVE(6);\n"
    "\tANDROID_KABI_RESERVE(7);\n"
    "\tANDROID_KABI_RESERVE(8);\n"
)


def process(path: str) -> bool:
    with open(path, encoding="utf-8", errors="surrogateescape") as fh:
        src = fh.read()

    if MARK in src:
        print(f"bore66-state: {path}: already relocated")
        return True
    if SE_FIELDS_OLD not in src:
        print(f"bore66-state: {path}: inline sched_entity burst fields "
              f"absent (not the 5.9.6 6.6 shape); no edit")
        return True
    if src.count(TS_SLOT3_OLD) != 1:
        print(f"bore66-state: {path}: expected exactly 1 task_struct "
              f"slot-3 tail, found {src.count(TS_SLOT3_OLD)}; aborting",
              file=sys.stderr)
        return False

    out = src.replace(SE_FIELDS_OLD, "", 1)
    # bore_state definition goes right after sched_burst_cache's block.
    anchor = "#endif // CONFIG_SCHED_BORE\n\nstruct sched_entity {"
    if anchor not in out:
        print(f"bore66-state: {path}: sched_burst_cache->sched_entity "
              f"anchor not found; aborting", file=sys.stderr)
        return False
    out = out.replace(anchor,
                      "#endif // CONFIG_SCHED_BORE\n\n" + BORE_STATE_DEF +
                      "\nstruct sched_entity {", 1)
    out = out.replace(TS_SLOT3_OLD, TS_SLOT3_NEW, 1)

    with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(out)
    print(f"bore66-state: {path}: inline fields removed, bore_state "
          f"def added, task_struct slot 3 consumed")
    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    ok = all(process(p) for p in sys.argv[1:])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())