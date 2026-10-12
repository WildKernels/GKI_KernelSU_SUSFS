#!/usr/bin/env python3
"""Translate BORE 5.9.6 group_burst accessors for the DS-combo layout.

Companion to bore66_state.py (DS-combo edition). After relocation:

  - burst_time + the four penalty/score u8s live FLAT in sched_entity's
    KABI slots 1-2 -> the patch's own `se->X` / `p->se.X` accessors for
    those members compile UNCHANGED. No translation, no guards.
  - child_burst lives in sched_entity's KABI slots 3-4 -> its accessors
    (`p->se.child_burst`, `parent->se.child_burst`, ...) compile
    UNCHANGED. No translation.
  - group_burst moved from sched_entity into task_struct's merged KABI
    slots -> only ITS accessors change:

      X->se.group_burst          -> X->group_burst   (X is task_struct *)
      se->group_burst            -> task_of(se)->group_burst
                                    (sched_clone_bore: se = &p->se, a
                                     task's own entity - always safe)
      P(se.group_burst...)       -> P(group_burst...)  (debug.c helpers
                                    operate on task_struct *p)

  No allocation, no free hooks, no init_task special-casing: the state is
  ordinary struct memory copied by fork's dup and re-initialized by the
  patch's own spin_lock_init-at-fork hook.

Idempotent: a second run finds no residual group hops and exits 0.

Usage: bore66_flat.py <bore.c> <fair.c> <fork.c> [more files...]
"""
import re
import sys

GROUP = "group_burst"


def translate_c(src: str) -> str:
    # 1. X->se.group_burst (any receiver: p, parent, task, ...)
    src = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)->se\.group_burst\b",
                 r"\1->group_burst", src)
    # 2. bare sched_entity receiver named se (sched_clone_bore tail);
    #    se = &p->se there - a task's own entity, task_of is safe.
    src = re.sub(r"\bse->group_burst\b",
                 r"task_of(se)->group_burst", src)
    # 3. sched-debug macro-arg form: P(se.group_burst) in debug.c - the
    #    print helpers operate on task_struct *p.
    src = re.sub(r"\bP\(se\.group_burst\b", r"P(group_burst", src)
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
        # residual check: any group hop through se left?
        resid = re.search(r"->se\.group_burst\b|\bse->group_burst\b", src)
        if resid:
            print(f"bore66-flat: {path}: WARNING residual group_burst "
                  f"accessor near {resid.group(0)!r}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
