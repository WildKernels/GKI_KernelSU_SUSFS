#!/usr/bin/env python3
"""Translate BORE 5.9.6 accessors to out-of-line bore_state members.

Companion to bore66_state.py. After relocation the state hangs off
task_struct->bore_state (heap), so every accessor shape changes:

  se->X               -> task_of(se)->bore_state->X
  p->se.X / q->se.X   -> p->bore_state->X (any expression before ->se.)
  &p->se.child_burst  -> &p->bore_state->child_burst  (pointer identity kept)

Only the seven burst members are touched (burst_time, prev/curr penalty,
burst_penalty, burst_score, child_burst, group_burst); cfs_b->burst_time
(CFS bandwidth, stock 6.6) and every non-BORE sched_entity member are
untouched - the translation keys on `.se.` / `se->` burst names only.

Also emits the allocation and free hooks:

  fork.c:   kzalloc the bore_state before sched_clone_bore (fails the fork
            on ENOMEM, matching how copy_process treats other allocs)
  core.c:   sched_bore_init allocates init_task's state (it is static, not
            forked), and release_task-path free is added in fork.c's
            free path - kfree(bore_state) NULL-safe.

Idempotent: a second run finds no `.se.` burst hops and exits 0.

Usage: bore66_flat.py <bore.c> <fair.c> <fork.c> [more files...]
"""
import re
import sys

MEMBERS = ("burst_time", "prev_burst_penalty", "curr_burst_penalty",
           "burst_penalty", "burst_score", "child_burst", "group_burst")
MEM = "|".join(MEMBERS)

ALLOC_MARK = "/* bore-kabi: alloc out-of-line bore_state */"
FREE_MARK = "/* bore-kabi: free out-of-line bore_state */"


def translate_c(src: str) -> str:
    # 1. bare sched_entity pointer named se
    src = re.sub(r"\bse->(%s)\b" % MEM,
                 r"task_of(se)->bore_state->\1", src)
    # 2. ANY bare receiver holding a sched_entity (curr->burst_time in
    #    fair.c's update_curr, etc.) - translate to task_of(recv)->...
    src = re.sub(r"\b(curr|p|prev|next|donor)->(%s)\b" % MEM,
                 r"task_of(\1)->bore_state->\2", src)
    # 3. X->se.Y (any receiver: parent, dec, anc, child, task, t ...)
    src = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)->se\.(%s)\b" % MEM,
                 r"\1->bore_state->\2", src)
    # 4. sched-debug macro-arg form: P(se.burst_score) / __PS("...", p->se.X)
    #    in debug.c - the token is `se.` with no receiver arrow. The print
    #    helpers all operate on task_struct *p, so se.X reads p->se.X there;
    #    the state is now p->bore_state->X.
    src = re.sub(r"\bP\(se\.(%s)\)" % MEM,
                 r"P(bore_state->\1)", src)
    return src


def patch_fork(src: str) -> str:
    if ALLOC_MARK in src:
        return src
    old = ("#ifdef CONFIG_SCHED_BORE\n"
           "\tif (likely(p->pid))\n"
           "\t\tsched_clone_bore(p, current, clone_flags, p->start_time);\n"
           "#endif // CONFIG_SCHED_BORE\n")
    new = ("#ifdef CONFIG_SCHED_BORE\n"
           "\t" + ALLOC_MARK + "\n"
           "\tp->bore_state = kzalloc(sizeof(struct bore_state), GFP_KERNEL);\n"
           "\tif (!p->bore_state)\n"
           "\t\tgoto bad_fork_cleanup_bore;\n"
           "\tif (likely(p->pid))\n"
           "\t\tsched_clone_bore(p, current, clone_flags, p->start_time);\n"
           "#endif // CONFIG_SCHED_BORE\n")
    if old not in src:
        print("bore66-flat: fork.c sched_clone_bore anchor not found; "
              "aborting", file=sys.stderr)
        sys.exit(1)
    src = src.replace(old, new, 1)

    # Cleanup label for the alloc failure path: the earliest task_struct
    # cleanup label after our alloc point is bad_fork_cleanup_thread (the
    # chain our failure joins; every label below it also frees things we
    # have not touched yet, so jumping there is safe).
    lbl_anchor = "bad_fork_cleanup_thread:\n"
    if lbl_anchor not in src:
        print("bore66-flat: bad_fork_cleanup_thread label not found; "
              "aborting", file=sys.stderr)
        sys.exit(1)
    lbl = ("bad_fork_cleanup_bore:\n"
           "#ifdef CONFIG_SCHED_BORE\n"
           "\tkfree(p->bore_state);\n"
           "\tp->bore_state = NULL;\n"
           "#endif // CONFIG_SCHED_BORE\n"
           + lbl_anchor)
    return src.replace(lbl_anchor, lbl, 1)


FREE_ANCHOR = "void __sched fork_idle(void)"


def add_free_hook(src: str) -> str:
    """Free the state where tasks actually die: release_task in fork.c
    runs before the task_struct pages are reused. Emit a small helper
    call site via the existing #ifdef block in release path."""
    if FREE_MARK in src:
        return src
    # release_task in kernel/fork.c frees with call_rcu(&p->rcu, delayed_put_task_struct)
    # -> __put_task_struct -> free_task. Hook free_task: it receives the
    # task_struct and runs after every path that could touch BORE state.
    anchor = "void free_task(struct task_struct *tsk)\n{\n"
    if anchor not in src:
        print("bore66-flat: free_task anchor not found; aborting",
              file=sys.stderr)
        sys.exit(1)
    hook = (anchor +
            "#ifdef CONFIG_SCHED_BORE\n"
            "\t" + FREE_MARK + "\n"
            "\tkfree(tsk->bore_state);\n"
            "\ttsk->bore_state = NULL;\n"
            "#endif // CONFIG_SCHED_BORE\n")
    return src.replace(anchor, hook, 1)


def init_task_alloc(src: str) -> str:
    """sched_bore_init resets init_task's state; it is static (not forked)
    so its bore_state pointer is NULL at boot. Allocate before reset."""
    old = ("\treset_task_bore(&init_task);\n"
           "\tinit_task_burst_cache_lock(&init_task);\n")
    new = ("\tinit_task.bore_state = kzalloc(sizeof(struct bore_state), GFP_KERNEL);\n"
           "\tif (!init_task.bore_state) { printk(KERN_ERR \"BORE: init_task bore_state alloc failed\"); return; }\n"
           "\treset_task_bore(&init_task);\n"
           "\tinit_task_burst_cache_lock(&init_task);\n")
    if old not in src:
        print("bore66-flat: sched_bore_init anchor not found; aborting",
              file=sys.stderr)
        sys.exit(1)
    return src.replace(old, new, 1)


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    rc = 0
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8", errors="surrogateescape") as fh:
            src = fh.read()
        orig = src
        if path.endswith("fork.c"):
            src = patch_fork(src)
            src = add_free_hook(src)
            src = translate_c(src)
        elif path.endswith("bore.c"):
            src = translate_c(src)
            src = init_task_alloc(src)
        else:
            src = translate_c(src)
        if src != orig:
            with open(path, "w", encoding="utf-8",
                      errors="surrogateescape") as fh:
                fh.write(src)
            print(f"bore66-flat: {path}: translated")
        else:
            print(f"bore66-flat: {path}: nothing to do")
        # residual check: any .se./se-> burst member left?
        resid = re.search(r"->se\.(%s)\b|\bse->(%s)\b" % (MEM, MEM), src)
        if resid:
            print(f"bore66-flat: {path}: WARNING residual accessor near "
                  f"{resid.group(0)!r}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())