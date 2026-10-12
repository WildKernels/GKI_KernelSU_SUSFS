#!/usr/bin/env python3
"""Translate BORE 5.9.6 cache accessors for the inline KABI-slot layout.

Companion to bore66_state.py (DroidSpaces method). After relocation:

  - burst_time + the four penalty/score u8s live FLAT in sched_entity's
    KABI slots 1-2 -> the patch's own `se->X` / `p->se.X` accessors for
    those members compile UNCHANGED. No translation, no guards.
  - child_burst / group_burst moved from sched_entity into task_struct's
    merged KABI slots -> only THEIR accessors change:

      se->child_burst            -> task_of(se)->child_burst
      X->se.child_burst          -> X->child_burst
      P(se.child_burst...)       -> P(child_burst...)   (debug.c helpers
                                    all operate on task_struct *p)

  No allocation, no free hooks, no init_task special-casing: the state is
  ordinary struct memory copied by fork's dup and re-initialized by the
  patch's own spin_lock_init-at-fork hook.

Idempotent: a second run finds no residual cache hops and exits 0.

Usage: bore66_flat.py <bore.c> <fair.c> <fork.c> [more files...]
"""
import re
import sys

CACHES = ("child_burst", "group_burst")
CACHE = "|".join(CACHES)


def translate_c(src: str) -> str:
    # 1. bare sched_entity pointer named se: se->child_burst.lock etc.
    src = re.sub(r"\bse->(%s)\b" % CACHE,
                 r"task_of(se)->\1", src)
    # 2. other bare receivers holding a sched_entity (curr, p, prev, next):
    #    curr->child_burst in fair.c's update_curr path.
    src = re.sub(r"\b(curr|p|prev|next|donor)->(%s)\b" % CACHE,
                 r"task_of(\1)->\2", src)
    # 3. X->se.child_burst (any receiver: parent, anc, child, task, t ...)
    src = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)->se\.(%s)\b" % CACHE,
                 r"\1->\2", src)
    # 4. sched-debug macro-arg form: P(se.child_burst) / P(se.group_burst)
    #    in debug.c - the print helpers operate on task_struct *p.
    src = re.sub(r"\bP\(se\.(%s)\b" % CACHE, r"P(\1", src)
    return src


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    rc = 0
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8", errors="surrogateescape") as fh:
            src = fh.read()
        orig = src
        src = translate_c(src)
        if src != orig:
            with open(path, "w", encoding="utf-8",
                      errors="surrogateescape") as fh:
                fh.write(src)
            print(f"bore66-flat: {path}: translated")
        else:
            print(f"bore66-flat: {path}: nothing to do")
        # residual check: any cache hop through se left?
        resid = re.search(r"->se\.(%s)\b|\bse->(%s)\b" % (CACHE, CACHE), src)
        if resid:
            print(f"bore66-flat: {path}: WARNING residual cache accessor "
                  f"near {resid.group(0)!r}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
