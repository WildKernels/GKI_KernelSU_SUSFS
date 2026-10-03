#!/usr/bin/env python3
"""Backport task_of() to kernels that predate it.

BORE's update_burst_score() calls task_of(se):

        if (!entity_is_task(se)) return;
        struct task_struct *p = task_of(se);

task_of() is a trivial container_of() wrapper, but it only exists from 5.15
onwards. On 5.10 the call fails to compile:

    error: implicit declaration of function 'task_of'
    [-Werror,-Wimplicit-function-declaration]

Only the wrapper is missing. entity_is_task() and task_struct.se both exist on
5.10 - task_struct embeds the entity at include/linux/sched.h:707 - so
container_of(se, struct task_struct, se) is valid. This adds the same two
inline definitions 5.15 carries, in the same place: immediately after
se_runnable() inside the CONFIG_FAIR_GROUP_SCHED block, plus the non-group
variant in its #else.

Adds no fields and no members, so the KMI is untouched.

Usage: bore_task_of.py <sched.h> [--revert]
"""
import sys

MARK = "/* bore: task_of() backport - EEVDF helper BORE needs */"

# Inserted at the end of the CONFIG_FAIR_GROUP_SCHED block (after se_runnable).
GROUP_OLD = """static inline long se_runnable(struct sched_entity *se)
{
\tif (entity_is_task(se))
\t\treturn !!se->on_rq;
\telse
\t\treturn se->runnable_weight;
}

#else
"""

GROUP_NEW = """static inline long se_runnable(struct sched_entity *se)
{
\tif (entity_is_task(se))
\t\treturn !!se->on_rq;
\telse
\t\treturn se->runnable_weight;
}

#ifdef CONFIG_FAIR_GROUP_SCHED
""" + MARK + """
static inline struct task_struct *task_of(struct sched_entity *se)
{
\tSCHED_WARN_ON(!entity_is_task(se));
\treturn container_of(se, struct task_struct, se);
}
#endif

#else
"""

# Inserted in the #else branch, matching 5.15's non-group variant.
NOGROUP_OLD = """static inline long se_runnable(struct sched_entity *se)
{
\treturn !!se->on_rq;
}
#endif
"""

NOGROUP_NEW = """static inline long se_runnable(struct sched_entity *se)
{
\treturn !!se->on_rq;
}
""" + MARK + """
static inline struct task_struct *task_of(struct sched_entity *se)
{
\treturn container_of(se, struct task_struct, se);
}
#endif
"""


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
            print("bore-task-of: not patched", file=sys.stderr)
            return 1
        src = src.replace(GROUP_NEW, GROUP_OLD).replace(NOGROUP_NEW, NOGROUP_OLD)
        with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
            fh.write(src)
        print("bore-task-of: reverted")
        return 0

    # Already have it upstream? Nothing to do.
    if "task_of(struct sched_entity *se)" in src and MARK not in src:
        print("bore-task-of: task_of() already present upstream; nothing to do")
        return 0

    if MARK in src:
        print("bore-task-of: already patched")
        return 0
    if src.count(GROUP_OLD) != 1:
        print(f"bore-task-of: group-sched anchor found {src.count(GROUP_OLD)} "
              f"times (expected 1)", file=sys.stderr)
        return 1
    if src.count(NOGROUP_OLD) != 1:
        print(f"bore-task-of: non-group anchor found {src.count(NOGROUP_OLD)} "
              f"times (expected 1)", file=sys.stderr)
        return 1

    out = src.replace(GROUP_OLD, GROUP_NEW, 1).replace(NOGROUP_OLD, NOGROUP_NEW, 1)
    with open(path, "w", encoding="utf-8", errors="surrogateescape") as fh:
        fh.write(out)
    print("bore-task-of: task_of() backported")
    return 0


if __name__ == "__main__":
    sys.exit(main())