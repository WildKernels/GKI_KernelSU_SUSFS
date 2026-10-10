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

# task_struct tail slots: slot 3 is free on 6.6. TWO tail shapes exist
# across the 6.6 sublevels (run 38046971754: every 6.6 job failed with
# 'expected exactly 1 slot-3 tail, found 0' because the anchor below was
# 6.6.143-specific):
#   - newer (6.6.14x): slot 1 = dmabuf_info, slot 2 = user_dumpable (USEs)
#   - older (<= 6.6.139): slots 1-2 are plain RESERVEs - the dmabuf block
#     is itself a GKI 6.6.14x-era change, verified against googlesource's
#     android15-6.6-2025-03 (6.6.77): plain RESERVE(1..8).
# Handle both; consume slot 3 in either.
TS_SLOT3_NEW_FORMS = [
    # newer shape (dmabuf_info + user_dumpable present)
    (
        "\tANDROID_KABI_USE(1, struct task_dma_buf_info *dmabuf_info);\n"
        "\tANDROID_KABI_USE(2, struct {\n"
        "\t\t/* Save user-dumpable when mm goes away */\n"
        "\t\tunsigned\tuser_dumpable:1;\n"
        "\t\t});\n"
        "\n"
        "\tANDROID_KABI_RESERVE(3);\n"
    ),
    # older shape (plain reserves): task_struct is disambiguated by the
    # l1d_flush_kill #ifdef block that directly precedes its tail (sched_avg
    # and sched_rt_entity share the bare RESERVE prefix but lack it).
    (
        "#ifdef CONFIG_ARCH_HAS_PARANOID_L1D_FLUSH\n"
        "\t/*\n"
        "\t * If L1D flush is supported on mm context switch\n"
        "\t * then we use this callback head to queue kill work\n"
        "\t * to kill tasks that are not running on SMT disabled\n"
        "\t * cores\n"
        "\t */\n"
        "\tstruct callback_head\t\tl1d_flush_kill;\n"
        "#endif\n"
        "\tANDROID_KABI_RESERVE(1);\n"
        "\tANDROID_KABI_RESERVE(2);\n"
        "\tANDROID_KABI_RESERVE(3);\n"
    ),
]

SLOT3_USE = (
    "#ifdef CONFIG_SCHED_BORE\n"
    "\t" + MARK + "\n"
    "\tANDROID_KABI_USE(3, struct bore_state *bore_state);\n"
    "#else\n"
    "\tANDROID_KABI_RESERVE(3);\n"
    "#endif\n"
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

    # Find which task_struct tail shape this sublevel carries and locate
    # its slot-3 RESERVE. Each form tuple ends with the slot-3 line; the
    # prefix (dmabuf USEs or plain reserves) disambiguates task_struct from
    # sibling structs with similar tails. Exactly one form must match once.
    matched = None
    for prefix_and_slot in TS_SLOT3_NEW_FORMS:
        n = src.count(prefix_and_slot)
        if n == 1:
            matched = prefix_and_slot
            break
        if n > 1:
            print(f"bore66-state: {path}: slot-3 tail form matched {n}x; "
                  f"aborting", file=sys.stderr)
            return False
    if matched is None:
        print(f"bore66-state: {path}: no known task_struct slot-3 tail "
              f"shape (neither dmabuf-era nor plain-reserve); aborting",
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
    # Replace ONLY the slot-3 line within the matched form's context:
    # split the matched form at its final line (the slot-3 RESERVE).
    prefix = matched.rsplit("\tANDROID_KABI_RESERVE(3);\n", 1)[0]
    out = out.replace(prefix + "\tANDROID_KABI_RESERVE(3);\n",
                      prefix + SLOT3_USE, 1)

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