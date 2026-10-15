#!/usr/bin/env python3
"""Relocate BORE 5.9.6 (6.6) burst state into KABI slots - inline, the
DroidSpaces method.

BORE 5.9.6 stores its burst state INLINE in struct sched_entity: burst_time,
four u8 penalty/score fields, and two spinlocked sched_burst_cache structs
(24-byte def; ~60 bytes). The 6.6 GKI KMI pins sched_entity structurally at its
stock size, so every member after the insertion shifts - a confirmed
bootloop on stock-vendor devices.

The caches cannot fit single 8-byte slots, so instead of a heap pointer this
version follows the DroidSpaces slot-merge method (_ANDROID_KABI_REPLACE over
consecutive reserves, exactly their SYSVIPC shape) and lays the state FLAT
across the structs' own free KABI reserves, DS-combo edition:

  1. struct sched_entity, RESERVE(1)+RESERVE(2) merged:
     burst_time (u64) + the four u8 penalty/score fields as an ANONYMOUS
     payload - the patch's own `se->burst_time`-style accessors compile
     UNCHANGED through the anonymous union nesting.
  2. struct sched_entity, RESERVE(3)+RESERVE(4) merged: child_burst as a
     NAMED `struct sched_burst_cache child_burst;` payload (the def is
     packed to 16 bytes first, so it fits). bore66_flat.py leaves every
     `se->child_burst` / `p->se.child_burst` accessor untouched: the
     member keeps its name AND its type, so `&se->child_burst` still
     type-checks as `struct sched_burst_cache *` for the cache helpers.
  3. struct task_struct, RESERVE(3..5) merged: group_burst as a NAMED
     `struct sched_burst_cache group_burst;` payload (16 of the 24
     bytes). Only ITS accessors change - bore66_flat.py rewrites
     `X->se.group_burst` -> `X->group_burst` and the se/task_of form.

  Zero runtime machinery: no heap allocation, no fork/exit hooks, no NULL
  guards, no pointer-alias hazard. The caches are copied by fork's
  dup_task_struct exactly as the upstream inline design intends, and the
  patch's own spin_lock_init-at-fork hook re-initializes them.

Slot budget (GKI 6.6): sched_entity has 4 free reserves, all consumed
(2 scalars + 16 bytes of child_burst). task_struct spends 3 of its slots
3-8 on group_burst; slots 6-8 stay stock for DroidSpaces - the DS 6.6
patch does not consume task_struct KABI slots anyway (its SYSVIPC gap
fix relocates sysvsem/sysvshm), so the two features coexist.

NAMED-MEMBER INVARIANT: the cache payloads MUST be named members. The
481e4486 draft shipped them as anonymous `struct { ... };` payloads -
layout-assert green but nameless, so `se->child_burst` and `p->group_burst`
resolved to nothing and run 38648460454 failed all 60 6.6 jobs at bore.c
with "no member named 'child_burst' in 'struct sched_entity'". The
post-splice verifier refuses to write a splice that drops either name.

Every transform fails loudly on anchor misses instead of shipping a
half-merged tree.

Usage: bore66_state.py <sched.h> [sched.h ...]
Idempotent: skips files carrying the marker.
"""
import re
import sys

MARK = "/* bore-kabi: 6.6 burst state in KABI slots (DroidSpaces method) */"

# The patch's inline sched_entity burst block (removed: it shifts SE's KMI).
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

# sched_entity tail: RESERVE(1..4) then '} __randomize_layout;'. On 6.6 the
# __randomize closing is unique to sched_entity (sched_rt_entity ends bare).
SE_RESERVES_OLD = (
    "\tANDROID_KABI_RESERVE(1);\n"
    "\tANDROID_KABI_RESERVE(2);\n"
    "\tANDROID_KABI_RESERVE(3);\n"
    "\tANDROID_KABI_RESERVE(4);\n"
    "} __randomize_layout;\n"
)

# DroidSpaces-style merge, DS-combo edition: SE slots 1+2 carry the
# scalars (patch's se->burst_time accessors need no translation), SE
# slots 3+4 carry child_burst packed to 16 bytes (timestamp u64,
# spinlock, count u16, score u8 - count caps at 64 so u16 is ample),
# and task_struct slots 3-5 carry group_burst in the same packed form
# (16 of the 24 available bytes). Slots 5-8 of SE and 6-8 of TS stay
# untouched so the DroidSpaces SYSVIPC patch (TS slots 6-8) coexists.
SE_RESERVES_NEW = (
    "#ifdef CONFIG_SCHED_BORE\n"
    "\t" + MARK + "\n"
    "\t_ANDROID_KABI_REPLACE(\n"
    "\t\tANDROID_KABI_RESERVE(1);\n"
    "\t\tANDROID_KABI_RESERVE(2),\n"
    "\t\tstruct {\n"
    "\t\t\tu64\tburst_time;\n"
    "\t\t\tu8\tprev_burst_penalty;\n"
    "\t\t\tu8\tcurr_burst_penalty;\n"
    "\t\t\tu8\tburst_penalty;\n"
    "\t\t\tu8\tburst_score;\n"
    "\t\t});\n"
    "\t_ANDROID_KABI_REPLACE(\n"
    "\t\tANDROID_KABI_RESERVE(3);\n"
    "\t\tANDROID_KABI_RESERVE(4),\n"
    "\t\tstruct sched_burst_cache child_burst;\n"
    "\t);\n"
    "#else\n"
    "\tANDROID_KABI_RESERVE(1);\n"
    "\tANDROID_KABI_RESERVE(2);\n"
    "\tANDROID_KABI_RESERVE(3);\n"
    "\tANDROID_KABI_RESERVE(4);\n"
    "#endif\n"
)

# task_struct tail shapes (three GKI eras; each ends at RESERVE(3) - the
# prefixes disambiguate task_struct from sibling structs).
TS_TAIL_FORMS = [
    (
        "\tANDROID_KABI_USE(1, struct task_dma_buf_info *dmabuf_info);\n"
        "\tANDROID_KABI_USE(2, struct {\n"
        "\t\t/* Save user-dumpable when mm goes away */\n"
        "\t\tunsigned\tuser_dumpable:1;\n"
        "\t\t});\n"
        "\n"
        "\tANDROID_KABI_RESERVE(3);\n"
    ),
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
    (
        "\tANDROID_KABI_USE(1, struct task_dma_buf_info *dmabuf_info);\n"
        "\n"
        "\tANDROID_KABI_RESERVE(2);\n"
        "\tANDROID_KABI_RESERVE(3);\n"
    ),
    # DroidSpaces 3_4_5 SYSVIPC variant (if DS ever runs on 6.6): slots
    # 3-5 consumed - recognised so the transform fails LOUDLY with an
    # explanation instead of splicing into the wrong place.
    (
        "\t_ANDROID_KABI_REPLACE(ANDROID_KABI_RESERVE(3); "
        "ANDROID_KABI_RESERVE(4); ANDROID_KABI_RESERVE(5), "
        "struct sysv_shm sysvshm);\n"
    ),
]

DS_CONFLICT_MSG = (
    "DroidSpaces SYSVIPC occupies task_struct slots 3-5 on this tree, but\n"
    "the DS-combo group_burst payload needs those slots. The current DS\n"
    "6.6 patch (SYSVIPC gap fix) consumes no task_struct KABI slots, so\n"
    "this firing means a PRE-COMBO DS patch ran (the old 3-4-5 sysvshm\n"
    "REPLACE). Reorder the patches or move one feature's slots; do not\n"
    "ship a tree where the splice landed on top of the DS payload."
)

# task_struct: group_burst packed into slots 3-5 (16 of the 24 bytes).
# DS-combo: slots 6-8 stay stock (plain reserves, or DroidSpaces'
# SYSVIPC USE/REPLACE when the DS patch ran first) - the transform
# replaces ONLY the RESERVE(3..5) triple and preserves whatever
# follows (the DS #ifdef block or plain reserves).
TS_GROUP_NEW = (
    "#ifdef CONFIG_SCHED_BORE\n"
    "\t" + MARK + "\n"
    "\t_ANDROID_KABI_REPLACE(\n"
    "\t\tANDROID_KABI_RESERVE(3);\n"
    "\t\tANDROID_KABI_RESERVE(4);\n"
    "\t\tANDROID_KABI_RESERVE(5),\n"
    "\t\tstruct sched_burst_cache group_burst;\n"
    "\t);\n"
    "#else\n"
    "\tANDROID_KABI_RESERVE(3);\n"
    "\tANDROID_KABI_RESERVE(4);\n"
    "\tANDROID_KABI_RESERVE(5);\n"
    "#endif\n"
)


def process(path: str) -> bool:
    with open(path, encoding="utf-8", errors="surrogateescape") as fh:
        src = fh.read()

    if MARK in src:
        print(f"bore66-state: {path}: already relocated")
        return True

    # The patch defines `struct sched_burst_cache` (24-byte form) above
    # sched_entity; all cache accessors take pointers to that type. The
    # merged members use a PACKED 16-byte layout (timestamp u64, lock,
    # count u16, score u8) - rewrite the definition to match, or every
    # bc->X access would read the wrong offsets. MUST run BEFORE any
    # offset is computed: the rewrite changes character lengths, and a
    # stale tail_abs splices mid-line (run 38302086915: the 6.6.127 legs
    # died on a '\tAN' fragment at the SE seam).
    struct_def_old = (
        "struct sched_burst_cache {\n"
        "\tu8\t\t\t\tscore;\n"
        "\tu32\t\t\t\tcount;\n"
        "\tu64\t\t\t\ttimestamp;\n"
        "    spinlock_t\t\tlock;\n"
        "};\n"
    )
    struct_def_new = (
        "struct sched_burst_cache {\n"
        "\tu64\t\t\t\ttimestamp;\n"
        "\tspinlock_t\t\tlock;\n"
        "\tu16\t\t\t\tcount;\n"
        "\tu8\t\t\t\tscore;\n"
        "};\n"
    )
    if struct_def_old in src:
        src = src.replace(struct_def_old, struct_def_new, 1)
        print(f"bore66-state: {path}: sched_burst_cache packed to 16 bytes")

    if SE_FIELDS_OLD not in src:
        print(f"bore66-state: {path}: inline sched_entity burst fields "
              f"absent (not the 5.9.6 6.6 shape); no edit")
        return True

    # sched_entity: remove the inline block, then merge RESERVE(1)+RESERVE(2)
    # into the scalar payload (DroidSpaces _ANDROID_KABI_REPLACE shape).
    #
    # ANCHOR WARNING: on 6.6.143 sched_rt_entity ends with a bare '};' and
    # sched_entity with '} __randomize_layout;' - but on 6.6.82 and older
    # sublevels it is INVERTED (run 38191197872: the payload landed in
    # sched_rt_entity on every pre-143 sublevel and all 60 jobs died with
    # "no member named 'burst_time' in 'struct sched_entity'"). So the tail
    # is located POSITIONALLY: it is the first RESERVE(1..4) block after
    # the (just-deleted) inline fields - sched_entity's own tail - and it
    # must appear before sched_rt_entity's opening. The struct's original
    # closing (either form) is preserved verbatim.
    se_pos = src.find(SE_FIELDS_OLD)
    out = src.replace(SE_FIELDS_OLD, "", 1)
    rt_open = out.find("struct sched_rt_entity {", se_pos)
    m = re.search(
        r"\tANDROID_KABI_RESERVE\(1\);\n"
        r"\tANDROID_KABI_RESERVE\(2\);\n"
        r"\tANDROID_KABI_RESERVE\(3\);\n"
        r"\tANDROID_KABI_RESERVE\(4\);\n"
        r"(\};\n|\} __randomize_layout;\n)",
        out[se_pos:])
    if not m or (rt_open != -1 and se_pos + m.start() > rt_open):
        print(f"bore66-state: {path}: sched_entity reserve tail not found "
              f"after the inline fields (before sched_rt_entity); "
              f"aborting", file=sys.stderr)
        return False
    # m.start()/m.end() are offsets WITHIN out[se_pos:] - the absolute end
    # is se_pos + m.end(), NOT tail_abs + m.end() (double-counting
    # m.start() overshoots the slice past the match and swallows whatever
    # follows - run 38198611423 ate all of sched_rt_entity this way).
    tail_abs = se_pos + m.start()
    closing = m.group(1)
    se_new = (
        "#ifdef CONFIG_SCHED_BORE\n"
        "\t" + MARK + "\n"
        "\t_ANDROID_KABI_REPLACE(\n"
        "\t\tANDROID_KABI_RESERVE(1);\n"
        "\t\tANDROID_KABI_RESERVE(2),\n"
        "\t\tstruct {\n"
        "\t\t\tu64\tburst_time;\n"
        "\t\t\tu8\tprev_burst_penalty;\n"
        "\t\t\tu8\tcurr_burst_penalty;\n"
        "\t\t\tu8\tburst_penalty;\n"
        "\t\t\tu8\tburst_score;\n"
        "\t\t});\n"
        "\t_ANDROID_KABI_REPLACE(\n"
        "\t\tANDROID_KABI_RESERVE(3);\n"
        "\t\tANDROID_KABI_RESERVE(4),\n"
        "\t\tstruct sched_burst_cache child_burst;\n"
        "\t);\n"
        "#else\n"
        "\tANDROID_KABI_RESERVE(1);\n"
        "\tANDROID_KABI_RESERVE(2);\n"
        "\tANDROID_KABI_RESERVE(3);\n"
        "\tANDROID_KABI_RESERVE(4);\n"
        "#endif\n"
        + closing
    )
    out = out[:tail_abs] + se_new + out[se_pos + m.end():]

    # task_struct: locate the tail era form, then pack group_burst into
    # the RESERVE(3..5) triple. Slots 6-8 stay untouched.
    matched = None
    for form in TS_TAIL_FORMS:
        n = out.count(form)
        if n == 1:
            matched = form
            break
        if n > 1:
            print(f"bore66-state: {path}: task_struct tail form matched "
                  f"{n}x; aborting", file=sys.stderr)
            return False
    if matched is None:
        print(f"bore66-state: {path}: no known task_struct tail shape; "
              f"aborting", file=sys.stderr)
        return False
    if matched is TS_TAIL_FORMS[3]:
        print(f"bore66-state: {path}: {DS_CONFLICT_MSG}",
              file=sys.stderr)
        return False

    # DS-combo: only the RESERVE(3)(4)(5) triple is consumed (16 bytes of
    # group_burst in 24 bytes of slots). Slots 6-8 stay as-is - plain
    # reserves, or DroidSpaces' SYSVIPC USE/REPLACE when the DS patch ran
    # first (the DS block sits AFTER slot 5 and is preserved verbatim).
    form_pos = out.find(matched)
    r3 = ("\tANDROID_KABI_RESERVE(3);\n"
          "\tANDROID_KABI_RESERVE(4);\n"
          "\tANDROID_KABI_RESERVE(5);\n")
    r3_pos = out.find(r3, form_pos)
    if r3_pos == -1:
        print(f"bore66-state: {path}: RESERVE(3..5) triple not found "
              f"contiguously after the matched tail; aborting",
              file=sys.stderr)
        return False
    out = out[:r3_pos] + TS_GROUP_NEW + out[r3_pos + len(r3):]

    # Post-splice verifier (named-member invariant). 481e4486's draft
    # payloads were layout-green but ANONYMOUS - `se->child_burst` and
    # `p->group_burst` resolved to nothing and run 38648460454 failed
    # all 60 6.6 jobs at bore.c with "no member named ...". Both caches
    # MUST ship as NAMED `struct sched_burst_cache` members or neither
    # the accessors nor the `struct sched_burst_cache *` helper params
    # can resolve. Fail loudly instead of writing a broken tree.
    checks = {
        "sched_entity child_burst payload missing":
            "\t\tstruct sched_burst_cache child_burst;\n" not in out,
        "task_struct group_burst payload missing":
            "\t\tstruct sched_burst_cache group_burst;\n" not in out,
        "packed 16-byte sched_burst_cache def missing":
            struct_def_new not in out,
        "inline burst fields still present":
            SE_FIELDS_OLD in out,
        "splice markers not exactly 2":
            out.count(MARK) != 2,
    }
    bad = [k for k, v in checks.items() if v]
    if bad:
        print(f"bore66-state: {path}: post-splice verifier FAILED "
              f"({'; '.join(bad)}); NOT writing", file=sys.stderr)
        return False

    with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(out)
    print(f"bore66-state: {path}: inline fields removed, scalars merged "
          f"into sched_entity slots 1-2, child_burst into sched_entity "
          f"slots 3-4, group_burst into task_struct slots 3-5 - DroidSpaces "
          f"slots 6-8 preserved (DS-combo method)")
    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    ok = all(process(p) for p in sys.argv[1:])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
