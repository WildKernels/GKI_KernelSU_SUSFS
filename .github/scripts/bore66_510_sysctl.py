#!/usr/bin/env python3
"""Repair the 5.1.0-on-6.6 sysctl reject in kernel/sched/fair.c.

The 0001-linux6.6.67-bore5.1.0.patch sysctl hunk targets upstream 6.6.67
declarations; GKI android15-6.6 differs (base_slice defaults are 700000ULL,
normalized_sysctl_sched_base_slice carries __maybe_unused, and an
EXPORT_SYMBOL_GPL sits between the declarations). The hunk rejects, and every
BORE hunk referencing sysctl_sched_min_base_slice or
configured_sched_base_slice then fails to compile.

Unlike sed line-splicing (which produced duplicate symbol definitions when
hand-rehearsed), this rewrites the WHOLE declaration region deterministically
from exact anchors: everything from the tunable-scaling comment opener through
the normalized_... line is replaced by one canonical #ifdef block. Fails
loudly when an anchor is missing (tree drift) instead of half-merging.

Resulting block:
  #ifdef CONFIG_SCHED_BORE    -> tunable NONE, base_slice 1s/HZ,
                                 configured_sched_base_slice 1s/HZ,
                                 min_base_slice 2000000 (Kconfig default)
  #else                       -> Android stock literals (700000ULL),
                                 normalized __maybe_unused
  EXPORT_SYMBOL_GPL(sysctl_sched_base_slice) kept OUTSIDE the ifdef so the
  exported symbol stays defined under both configurations.

Idempotent: keyed on the '#else // !CONFIG_SCHED_BORE' line inside the
rewritten region; a second run finds it and no-ops.

Usage: bore66_510_sysctl.py kernel/sched/fair.c
"""
import sys

# The full region the upstream hunk would have rewritten, anchored on text
# that exists in the GKI tree AFTER the patch's other hunks applied (the
# hunk's context lines are stable; only the declarations differ).
OPEN_ANCHOR = "*   SCHED_TUNABLESCALING_NONE - unscaled, always *1"
# The last line of the region: normalized_sysctl... (with or without
# __maybe_unused, either 700000/750000 literal). Matched as a prefix.
CLOSE_PREFIX = "static unsigned int normalized_sysctl_sched_base_slice"

BORE_ARM = """#ifdef CONFIG_SCHED_BORE
unsigned int sysctl_sched_tunable_scaling = SCHED_TUNABLESCALING_NONE;
#else // !CONFIG_SCHED_BORE
unsigned int sysctl_sched_tunable_scaling = SCHED_TUNABLESCALING_LOG;
#endif // CONFIG_SCHED_BORE

/*
 * Minimal preemption granularity for CPU-bound tasks:
 *
 * (BORE  default: max(1 sec / HZ, min_base_slice) constant, units: nanoseconds)
 * (EEVDF default: 0.75 msec * (1 + ilog(ncpus)), units: nanoseconds)
 */
#ifdef CONFIG_SCHED_BORE
unsigned int            sysctl_sched_base_slice = 1000000000ULL / HZ;
static unsigned int configured_sched_base_slice = 1000000000ULL / HZ;
unsigned int        sysctl_sched_min_base_slice =    2000000ULL;
#else // !CONFIG_SCHED_BORE
unsigned int sysctl_sched_base_slice\t\t\t= 700000ULL;
static unsigned int normalized_sysctl_sched_base_slice\t= 700000ULL;
#endif // CONFIG_SCHED_BORE
EXPORT_SYMBOL_GPL(sysctl_sched_base_slice);"""


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    path = sys.argv[1]

    with open(path, encoding="utf-8", errors="surrogateescape") as fh:
        src = fh.read()

    if ("static unsigned int configured_sched_base_slice"
            " = 1000000000ULL / HZ;" in src):
        # The DECLARATION (not a use site - update_sysctl's BORE arm applies
        # cleanly and references configured_) is the repair's marker.
        print("bore66-510-sysctl: already repaired")
        return 0

    open_pos = src.find(OPEN_ANCHOR)
    if open_pos < 0:
        print(f"bore66-510-sysctl: FATAL anchor '{OPEN_ANCHOR[:40]}...' not "
              f"found - tree drift, refusing to guess", file=sys.stderr)
        return 1
    # Back up to the start of the comment line containing the anchor.
    region_start = src.rfind("\n", 0, open_pos) + 1
    # Walk forward to the END of the normalized_... line.
    close_pos = src.find(CLOSE_PREFIX, open_pos)
    if close_pos < 0:
        print("bore66-510-sysctl: FATAL normalized_sysctl_sched_base_slice "
              "not found after anchor - tree drift", file=sys.stderr)
        return 1
    region_end = src.find("\n", close_pos)
    if region_end < 0:
        print("bore66-510-sysctl: FATAL unterminated normalized line",
              file=sys.stderr)
        return 1
    region_end += 1  # include the newline

    # Sanity: the region must not already contain a BORE arm (would mean a
    # partial prior repair we would clobber inconsistently).
    region = src[region_start:region_end]
    if "CONFIG_SCHED_BORE" in region:
        print("bore66-510-sysctl: FATAL region already contains "
              "CONFIG_SCHED_BORE - unexpected state", file=sys.stderr)
        return 1

    out = src[:region_start] + BORE_ARM + "\n" + src[region_end:]
    with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(out)
    print("bore66-510-sysctl: rebuilt sysctl declaration region "
          f"({len(region)} bytes -> {len(BORE_ARM) + 1})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
