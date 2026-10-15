#!/usr/bin/env python3
"""Move BORE 5.1.0's sched_entity burst_* fields into ANDROID_KABI_RESERVE slots.

6.6 variant of bore_kabi_612.py for the 0001-linux6.6.67-bore5.1.0.patch
(git diff linux-6.6.67..fe5728f9 on firelzrd/bore-scheduler 6.6-bore).

Same transform as the 6.1 script (flat anonymous-struct payloads via helper
macros so `se->burst_time` & co keep compiling; __GENKSYMS__ sees the stock
reserved u64s; the ANDROID_KABI_USE _Static_assert refuses oversize slots),
with ONE structural difference: the RESERVE(1..4)+bare-`};` anchor is searched
ONLY inside the sched_entity slice that starts at the inserted BORE block and
ends at sched_entity's own closing brace.

Why: on 6.6 the bare-`};` closing form SWAPS between sched_entity and
sched_rt_entity across sublevel eras (2025-04 trees: rt_entity bare;
2026-09 trees: sched_entity bare). A whole-file count==1 check on
RESERVE(1..4)+`};` passes on both eras but lands the payload in
sched_rt_entity on the flipped ones. The BORE block itself is
sched_entity-unique (it sits directly before `s64 vlag;`), so bounding the
reserve search to sched_entity's own slice is era-proof. Abort loudly when
the slice holds no matching reserve block.

Usage: bore66_510.py <sched.h> [--revert]
"""
import sys

MARK = "/* bore-kabi: burst_* fields live in ANDROID_KABI_RESERVE slots */"

SLOT_MACROS = (
    "#ifdef CONFIG_SCHED_BORE\n"
    "#define __BORE_KABI_SLOT3 struct { u32 child_burst_cnt; u8 prev_burst_penalty; }\n"
    "#define __BORE_KABI_SLOT4 struct { u8 curr_burst_penalty; u8 burst_penalty; \\\n"
    "\tu8 burst_score; u8 child_burst; }\n"
    "#endif // CONFIG_SCHED_BORE\n\n"
)

BORE_OLD = (
    "#ifdef CONFIG_SCHED_BORE\n"
    "\tu64\t\t\t\tburst_time;\n"
    "\tu8\t\t\t\tprev_burst_penalty;\n"
    "\tu8\t\t\t\tcurr_burst_penalty;\n"
    "\tu8\t\t\t\tburst_penalty;\n"
    "\tu8\t\t\t\tburst_score;\n"
    "\tu8\t\t\t\tchild_burst;\n"
    "\tu32\t\t\t\tchild_burst_cnt;\n"
    "\tu64\t\t\t\tchild_burst_last_cached;\n"
    "#endif // CONFIG_SCHED_BORE\n"
)

BORE_NEW = (
    "#ifdef CONFIG_SCHED_BORE\n"
    "\t/* BORE - moved into the ANDROID_KABI_RESERVE slots at the bottom of\n"
    "\t * the struct; see __BORE_KABI_SLOT3/4 and the ANDROID_KABI_USE lines.\n"
    "\t// u64\t\t\t\tburst_time;\n"
    "\t// u8\t\t\t\tprev_burst_penalty;\n"
    "\t// u8\t\t\t\tcurr_burst_penalty;\n"
    "\t// u8\t\t\t\tburst_penalty;\n"
    "\t// u8\t\t\t\tburst_score;\n"
    "\t// u8\t\t\t\tchild_burst;\n"
    "\t// u32\t\t\t\tchild_burst_cnt;\n"
    "\t// u64\t\t\t\tchild_burst_last_cached; */\n"
    "#endif // CONFIG_SCHED_BORE\n"
)

RES_OLD = (
    "\tANDROID_KABI_RESERVE(1);\n"
    "\tANDROID_KABI_RESERVE(2);\n"
    "\tANDROID_KABI_RESERVE(3);\n"
    "\tANDROID_KABI_RESERVE(4);\n"
    "};\n"
)

RES_NEW = (
    "#ifdef CONFIG_SCHED_BORE\n"
    "\t" + MARK + "\n"
    "\tANDROID_KABI_USE(1, u64 burst_time);\n"
    "\tANDROID_KABI_USE(2, u64 child_burst_last_cached);\n"
    "\tANDROID_KABI_USE(3, __BORE_KABI_SLOT3);\n"
    "\tANDROID_KABI_USE(4, __BORE_KABI_SLOT4);\n"
    "#else\n"
    "\tANDROID_KABI_RESERVE(1);\n"
    "\tANDROID_KABI_RESERVE(2);\n"
    "\tANDROID_KABI_RESERVE(3);\n"
    "\tANDROID_KABI_RESERVE(4);\n"
    "#endif\n"
    "};\n"
)


def sched_entity_slice(src: str, bore_start: int) -> tuple[int, int]:
    """Return [start, end) covering sched_entity's closing brace, starting at
    the inserted BORE block. The first line that is exactly '};' after the
    BORE block closes sched_entity (no nested struct definitions between the
    inserted fields and the struct's reserves)."""
    closer = src.find("\n};\n", bore_start)
    if closer < 0:
        raise ValueError("sched_entity closing brace not found after BORE block")
    return bore_start, closer + len("\n};\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    path = sys.argv[1]
    revert = "--revert" in sys.argv

    with open(path, encoding="utf-8", errors="surrogateescape") as fh:
        src = fh.read()

    if revert:
        if MARK not in src:
            print("bore66-510: not patched", file=sys.stderr)
            return 1
        src = src.replace(RES_NEW, RES_OLD).replace(BORE_NEW, BORE_OLD)
        src = src.replace(SLOT_MACROS, "")
        with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
            fh.write(src)
        print("bore66-510: reverted")
        return 0

    if MARK in src:
        print("bore66-510: already patched")
        return 0
    if BORE_OLD not in src:
        print("bore66-510: BORE burst_* block not found (did the patch apply?)",
              file=sys.stderr)
        return 1
    if src.count(BORE_OLD) != 1:
        print(f"bore66-510: found {src.count(BORE_OLD)} BORE field blocks "
              f"(expected 1)", file=sys.stderr)
        return 1

    bore_pos = src.index(BORE_OLD)
    try:
        slice_start, slice_end = sched_entity_slice(src, bore_pos)
    except ValueError as e:
        print(f"bore66-510: {e}", file=sys.stderr)
        return 1
    se_slice = src[slice_start:slice_end]
    if se_slice.count(RES_OLD) != 1:
        print(f"bore66-510: found {se_slice.count(RES_OLD)} candidate "
              f"reservation blocks inside sched_entity (expected 1)",
              file=sys.stderr)
        return 1

    # Splice within the slice only, then reassemble.
    new_slice = se_slice.replace(BORE_OLD, BORE_NEW, 1)
    new_slice = new_slice.replace(RES_OLD, RES_NEW, 1)
    out = src[:slice_start] + new_slice + src[slice_end:]

    # SLOT_MACROS go right before struct sched_entity (unique opening).
    if out.count("struct sched_entity {") != 1:
        print("bore66-510: 'struct sched_entity {' not unique", file=sys.stderr)
        return 1
    out = out.replace("struct sched_entity {",
                      SLOT_MACROS + "struct sched_entity {", 1)

    with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(out)
    print("bore66-510: burst_* fields moved into sched_entity kABI slots "
          "(flat access, no narrowing, era-proof positional anchor)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
