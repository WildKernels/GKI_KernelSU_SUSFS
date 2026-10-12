#!/usr/bin/env python3
"""Move BORE's sched_entity burst_* fields into ANDROID_KABI_RESERVE slots.

BORE adds eight fields to struct sched_entity - 25 raw, 40 with alignment -
but sched_entity reserves only four u64 slots (32 bytes). Left inline, every
member after the insertion point shifts and the GKI KMI breaks; stock vendor
modules read from the wrong offsets.

The fix uses the kernel's own ANDROID_KABI_USE() macros, not hand-rolled
unions:

  - flat access is preserved, so BORE's `p->se.burst_score` keeps compiling
    (a first attempt wrapped the fields in a named member and failed CI with
    "no member named 'prev_burst_penalty'")
  - under __GENKSYMS__ the macros collapse to the stock reserved u64, so the
    KMI symbol list is unchanged - the same property the droidspaces
    SYSVIPC patch depends on
  - the built-in _Static_assert fails the build loudly if a slot's contents
    ever exceed 8 bytes, instead of silently shifting offsets

No field is narrowed. burst_time accumulates delta_exec without bound and
child_burst_last_cached holds a sched_clock() timestamp (ns since boot), so
both genuinely require u64; an earlier draft narrowed them to u32, which
would have wrapped after ~4.3s of uptime.

Slot layout (40 raw bytes -> 4 x 8):
  slot 1: u64 burst_time
  slot 2: u64 child_burst_last_cached
  slot 3: u32 child_burst_cnt; u8 prev_burst_penalty
  slot 4: u8 curr_burst_penalty; u8 burst_penalty;
          u8 burst_score;     u8 child_burst

Slots 3 and 4 hold several members, but ANDROID_KABI_USE takes exactly two
macro arguments and top-level commas split arguments, so the multi-member
payloads are passed as helper macros - commas introduced by macro EXPANSION
are not argument separators.

Usage: bore_kabi_612.py <sched.h> [--revert]
"""
import sys

MARK = "/* bore-kabi: burst_* fields live in ANDROID_KABI_RESERVE slots */"

# Helper macros inserted just before struct sched_entity. Expansion-time
# commas are safe; argument-time commas are not.
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
        src = src.replace(SLOT_MACROS, "")
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
    out = out.replace("struct sched_entity {",
                      SLOT_MACROS + "struct sched_entity {", 1)
    out = out.replace(RES_OLD, RES_NEW, 1)
    with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(out)
    print("bore-kabi: burst_* fields moved into kABI reservations "
          "(flat access, no narrowing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())