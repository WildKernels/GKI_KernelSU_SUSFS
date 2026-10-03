#!/usr/bin/env python3
"""Move BORE's sched_entity burst_* fields into ANDROID_KABI_RESERVE slots.

BORE adds eight fields to struct sched_entity:

    u64  burst_time, child_burst_last_cached      16 bytes
    u32  child_burst_cnt                            4 bytes
    u8   prev_burst_penalty, curr_burst_penalty,
         burst_penalty, burst_score, child_burst    5 bytes

25 raw, 40 padded. sched_entity reserves only four u64 slots (32 bytes), so
the fields overflow by 8 and every member after them shifts. That breaks the
GKI KMI and takes stock vendor modules with it.

Claim all four reservations and narrow the two timestamps to u32. The result
was compiled and measured against stock:

    stock (no BORE)             176 bytes
    BORE inline (upstream)      208 bytes  (+32 vs stock)
    BORE inside kABI slots      176 bytes  (+0 vs stock)

So the padded form restores the stock layout exactly. This diverges from
upstream BORE and changes two field widths, so it still needs load-testing.

Usage: bore_kabi_612.py <sched.h> [--revert]
"""
import sys

MARK = "/* bore-kabi: burst_* fields live in ANDROID_KABI_RESERVE slots */"

TYPES = (
    "struct bore_child { u32 child_burst_last_cached; u32 child_burst_cnt; };\n"
    "struct bore_bonus {\n"
    "\tu8 prev_burst_penalty, curr_burst_penalty, burst_penalty,\n"
    "\t   burst_score, child_burst, pad[3];\n"
    "};\n\n"
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
    "\t/* BORE - moved into ANDROID_KABI_RESERVE slots, see bottom of struct.\n"
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
    "\t_ANDROID_KABI_REPLACE(ANDROID_KABI_RESERVE(1), u32 burst_time);\n"
    "\t_ANDROID_KABI_REPLACE(ANDROID_KABI_RESERVE(2), struct bore_child child);\n"
    "\t_ANDROID_KABI_REPLACE(ANDROID_KABI_RESERVE(3), struct bore_bonus bonus);\n"
    "\t_ANDROID_KABI_REPLACE(ANDROID_KABI_RESERVE(4), u64 __unused4);\n"
    "#else\n"
    "\tANDROID_KABI_RESERVE(1);\n"
    "\tANDROID_KABI_RESERVE(2);\n"
    "\tANDROID_KABI_RESERVE(3);\n"
    "\tANDROID_KABI_RESERVE(4);\n"
    "#endif\n"
    "};\n"
)


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
            print("bore-kabi: not patched", file=sys.stderr)
            return 1
        src = src.replace(RES_NEW, RES_OLD).replace(BORE_NEW, BORE_OLD)
        src = src.replace(TYPES, "")
        with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
            fh.write(src)
        print("bore-kabi: reverted")
        return 0

    if MARK in src:
        print("bore-kabi: already patched")
        return 0
    if BORE_OLD not in src:
        print("bore-kabi: BORE burst_* block not found (did the patch apply?)",
              file=sys.stderr)
        return 1
    if src.count(RES_OLD) != 1:
        print(f"bore-kabi: found {src.count(RES_OLD)} candidate reservation "
              f"blocks (expected 1)", file=sys.stderr)
        return 1

    out = src.replace(BORE_OLD, BORE_NEW, 1)
    # typedefs go immediately before "struct sched_entity {"
    out = out.replace("struct sched_entity {", TYPES + "struct sched_entity {", 1)
    out = out.replace(RES_OLD, RES_NEW, 1)
    with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(out)
    print("bore-kabi: burst_* fields moved into kABI reservations")
    return 0


if __name__ == "__main__":
    sys.exit(main())