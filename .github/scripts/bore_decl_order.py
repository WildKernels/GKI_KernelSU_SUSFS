#!/usr/bin/env python3
"""Hoist BORE's declarations above its early-return guard.

BORE inserts into kernel/sched/fair.c:

    static void update_burst_score(struct sched_entity *se) {
            if (!entity_is_task(se)) return;
            struct task_struct *p = task_of(se);
            u8 prio = p->static_prio - MAX_RT_PRIO;
            u8 prev_prio = min(39, prio + se->burst_score);

The guard is a statement, so the declarations that follow it trip
-Wdeclaration-after-statement, which the kernel builds treat as -Werror:

    kernel/sched/fair.c:174:22: error: mixing declarations and code is
    incompatible with standards before C99 [-Werror,-Wdeclaration-after-statement]

Hoisting them above the guard is semantically identical: task_of(se) is only
reached when entity_is_task(se) was already true.

Only rewrite inside update_burst_score(). A bare "p = task_of(se);" occurs in
several unrelated stock functions, so probing the whole file for it would
falsely report an unpatched tree as already done.

Idempotent, and refuses to edit if the anchor is not found exactly once.

Usage: bore_decl_order.py <fair.c>
"""
import re
import sys

FUNC_RE = re.compile(
    r"^static void update_burst_score\(struct sched_entity \*se\) \{$", re.M)

OLD = """\tif (!entity_is_task(se)) return;
\tstruct task_struct *p = task_of(se);
\tu8 prio = p->static_prio - MAX_RT_PRIO;
\tu8 prev_prio = min(39, prio + se->burst_score);
"""

NEW = """\tstruct task_struct *p;
\tu8 prio, prev_prio;

\tif (!entity_is_task(se)) return;
\tp = task_of(se);
\tprio = p->static_prio - MAX_RT_PRIO;
\tprev_prio = min(39, prio + se->burst_score);
"""


def main():
    if len(sys.argv) != 2:
        print("usage: bore_decl_order.py <fair.c>", file=sys.stderr)
        return 2
    path = sys.argv[1]

    with open(path, encoding="utf-8", errors="surrogateescape") as fh:
        src = fh.read()

    if not FUNC_RE.search(src):
        print("bore-decl-order: update_burst_score() not present "
              "(BORE patch may not have applied); nothing to do")
        return 0

    # Scope the rewrite to the function body so unrelated occurrences of the
    # same statements elsewhere in fair.c are untouched.
    m = FUNC_RE.search(src)
    if m is None:
        print("bore-decl-order: function header not found; skipped",
              file=sys.stderr)
        return 1
    start = m.start()
    end = src.index("\n}\n", start) + 3
    body = src[start:end]

    if OLD not in body:
        if NEW.split("\n")[1] in body:
            print("bore-decl-order: already hoisted")
            return 0
        print("bore-decl-order: anchor not found inside update_burst_score(); "
              "skipped", file=sys.stderr)
        return 1

    patched = body.replace(OLD, NEW, 1)
    with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(src[:start] + patched + src[end:])
    print("bore-decl-order: hoisted declarations in update_burst_score()")
    return 0


if __name__ == "__main__":
    sys.exit(main())