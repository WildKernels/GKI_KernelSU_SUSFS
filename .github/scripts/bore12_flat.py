#!/usr/bin/env python3
"""Translate BORE 7.0.0 accessor/alloc/free sites for out-of-line bore_ctx.

Companion to bore12_state.py, which removes the inline `struct bore_ctx
bore` member from task_struct and consumes KABI slot 8 for a
`struct bore_ctx *bore` pointer. This script rewrites the C side:

  1. Arrow hops:    `X->bore.MEMBER` -> `X->bore->MEMBER`   (all files)
  2. ctx locals:    `struct bore_ctx *ctx = &X->bore;`
                              -> `struct bore_ctx *ctx = X->bore;`
  3. bore.h bore_score: NULL-guarded (0 score -> stock prio) - covers
     set_load_weight on init_task before sched_init_bore and idle forks.
  4. NULL guards on the extern entry points that can see a stateless
     task (only idle tasks, pid 0): update_curr_bore, restart_burst_bore,
     bore_note_sleep, bore_credit_ns (stock 0 credit), task_fork_bore
     (also requires parent state), reset_task_bore. effective_prio_bore
     is covered through bore_score.
  5. fork.c copy_process: `p->bore = NULL;` immediately after
     dup_task_struct - CRITICAL: the dup memcpy aliases the parent's
     pointer; without the early NULL, an early-failure free_task would
     kfree the parent's live context. Then kzalloc + task_fork_bore for
     pid != 0 at the patch's call site, failure unwinding to a private
     bad_fork_cleanup_bore label that falls through to
     bad_fork_cancel_cgroup (the same unwind sched_cgroup_fork's own
     failure uses at that position).
  6. fork.c free_task: kfree the state. free_task is the single choke
     point every task_struct death path funnels into (__put_task_struct,
     bad_fork_free via delayed_free_task).
  7. bore.c sched_init_bore: allocate init_task's state before
     reset_task_bore(&init_task); sched_init_bore runs inside sched_init
     before set_load_weight(&init_task), so the first bore_score read on
     init_task sees real state. Alloc failure leaves NULL - every entry
     is guarded.

Stateless tasks are exactly: idle threads (pid 0) and init_task before
sched_init_bore. Guards make those exactly stock-BORE-disabled.

Usage: bore12_flat.py <file.c-or-.h> [more files...]
Idempotent: a second run finds no `->bore.` hop and no anchors to add.
"""
import re
import sys

HOPS = re.compile(r"->bore\.")
CTX_LOCAL = re.compile(r"= &([A-Za-z_][A-Za-z0-9_]*->bore);")


def rewrite_generic(src: str, path: str) -> str:
    src, _ = HOPS.subn("->bore->", src)
    src = CTX_LOCAL.sub(r"= \1;", src)
    return src


def rewrite_bore_h(src: str, path: str) -> str:
    src = rewrite_generic(src, path)
    old = "{ return p->bore->penalty >> 8; }"
    new = ("{ return unlikely(!p->bore) ? 0 "
           ": (p->bore->penalty >> 8); }")
    if old in src:
        src = src.replace(old, new, 1)
    elif "unlikely(!p->bore) ? 0" not in src:
        print(f"bore12-flat: {path}: bore_score anchor missing", file=sys.stderr)
        sys.exit(1)
    return src


def rewrite_bore_c(src: str, path: str) -> str:
    src = rewrite_generic(src, path)

    # update_curr_bore: guard right after the ctx decl (statement after a
    # declaration - C89-clean).
    old = ("\tstruct bore_ctx *ctx = p->bore;\n"
           "\tif (ctx->stop_update) return;\n")
    new = ("\tstruct bore_ctx *ctx = p->bore;\n"
           "\tif (unlikely(!ctx)) return;\n"
           "\tif (ctx->stop_update) return;\n")
    if old in src:
        src = src.replace(old, new, 1)
    elif "if (unlikely(!ctx)) return;" not in src:
        print(f"bore12-flat: {path}: update_curr_bore anchor missing",
              file=sys.stderr)
        sys.exit(1)

    # restart_burst_bore: the second declaration initializes from ctx, so
    # split the declaration and guard between the two (C89-clean).
    old = ("\tstruct bore_ctx *ctx = p->bore;\n"
           "\tu32 new_penalty = binary_smooth(ctx->curr_penalty, "
           "ctx->prev_penalty);\n")
    new = ("\tstruct bore_ctx *ctx = p->bore;\n"
           "\tu32 new_penalty;\n"
           "\tif (unlikely(!ctx)) return;\n"
           "\tnew_penalty = binary_smooth(ctx->curr_penalty, "
           "ctx->prev_penalty);\n")
    if old in src:
        src = src.replace(old, new, 1)
    elif "u32 new_penalty;\n" in src:
        pass
    else:
        print(f"bore12-flat: {path}: restart_burst_bore anchor missing",
              file=sys.stderr)
        sys.exit(1)

    # bore_note_sleep: single-statement body, guard goes first.
    old = ("void bore_note_sleep(struct task_struct *p, u64 now)\n"
           "{\n"
           "\tp->bore->credit_sleep = now;\n"
           "}\n")
    new = ("void bore_note_sleep(struct task_struct *p, u64 now)\n"
           "{\n"
           "\tif (unlikely(!p->bore)) return;\n"
           "\tp->bore->credit_sleep = now;\n"
           "}\n")
    if old in src:
        src = src.replace(old, new, 1)
    elif "void bore_note_sleep(struct task_struct *p, u64 now)" not in src:
        print(f"bore12-flat: {path}: bore_note_sleep anchor missing",
              file=sys.stderr)
        sys.exit(1)

    # bore_credit_ns: declarations first, guard after them.
    old = "\tu64 slept = 0, credit = 0;\n"
    new = ("\tu64 slept = 0, credit = 0;\n"
           "\n"
           "\tif (unlikely(!p->bore)) return 0;\n")
    if old in src:
        src = src.replace(old, new, 1)
    elif "if (unlikely(!p->bore)) return 0;" in src:
        pass
    else:
        print(f"bore12-flat: {path}: bore_credit_ns anchor missing",
              file=sys.stderr)
        sys.exit(1)

    # reset_task_bore: NULL-guarded memset through the pointer.
    old = "{ memset(&p->bore, 0, sizeof(struct bore_ctx)); }"
    new = ("{ if (unlikely(!p->bore)) return; "
           "memset(p->bore, 0, sizeof(struct bore_ctx)); }")
    if old in src:
        src = src.replace(old, new, 1)
    elif "memset(p->bore, 0, sizeof(struct bore_ctx))" not in src:
        print(f"bore12-flat: {path}: reset_task_bore anchor missing",
              file=sys.stderr)
        sys.exit(1)

    # sched_init_bore: init_task is static (never forked) - allocate its
    # state before the first reset. sched_init calls sched_init_bore before
    # set_load_weight(&init_task), so ordering is guaranteed.
    old = "\treset_task_bore(&init_task);\n"
    new = ("\tinit_task.bore = kzalloc(sizeof(struct bore_ctx), GFP_KERNEL);\n"
           "\tif (!init_task.bore)\n"
           "\t\tprintk(KERN_ERR \"BORE: init_task bore_ctx alloc failed\\n\");\n"
           "\treset_task_bore(&init_task);\n")
    if old in src:
        src = src.replace(old, new, 1)
    elif "init_task.bore = kzalloc" not in src:
        print(f"bore12-flat: {path}: sched_init_bore anchor missing",
              file=sys.stderr)
        sys.exit(1)

    # task_fork_bore: guard after the author's own first statement (the
    # function already mixes statements and declarations, so appending a
    # statement introduces no new C89 violation).
    old = ("\tif (!static_branch_likely(&sched_bore_key) || "
           "!task_is_bore_eligible(p)) return;\n")
    new = (old +
           "\tif (unlikely(!p->bore || !parent->bore)) return;\n")
    if old in src:
        src = src.replace(old, new, 1)
    elif "if (unlikely(!p->bore || !parent->bore)) return;" in src:
        pass
    else:
        print(f"bore12-flat: {path}: task_fork_bore anchor missing",
              file=sys.stderr)
        sys.exit(1)

    return src


def rewrite_fork_c(src: str, path: str) -> str:
    src = rewrite_generic(src, path)

    # 1. Early NULL right after dup_task_struct: the memcpy aliases the
    # parent's pointer; every early-failure path (copy_creds, RLIMIT_NPROC,
    # ...) can reach free_task before the late alloc point, and free_task
    # kfrees the pointer. Without this NULL those paths would free the
    # parent's live context.
    old = ("\tp = dup_task_struct(current, node);\n"
           "\tif (!p)\n"
           "\t\tgoto fork_out;\n")
    new = (old +
           "#ifdef CONFIG_SCHED_BORE\n"
           "\tp->bore = NULL;\n"
           "#endif /* CONFIG_SCHED_BORE */\n")
    if old in src:
        src = src.replace(old, new, 1)
    elif "p->bore = NULL;" in src:
        pass
    else:
        print(f"bore12-flat: {path}: dup_task_struct anchor missing",
              file=sys.stderr)
        sys.exit(1)

    # 2. Alloc at the patch's task_fork_bore call site; failure unwinds to
    # our private label (same unwind sched_cgroup_fork's failure uses).
    old = ("#ifdef CONFIG_SCHED_BORE\n"
           "\tif (likely(p->pid))\n"
           "\t\ttask_fork_bore(p, current, clone_flags, p->start_time);\n"
           "#endif /* CONFIG_SCHED_BORE */\n")
    new = ("#ifdef CONFIG_SCHED_BORE\n"
           "\tif (likely(p->pid)) {\n"
           "\t\tp->bore = kzalloc(sizeof(struct bore_ctx), GFP_KERNEL);\n"
           "\t\tif (unlikely(!p->bore))\n"
           "\t\t\tgoto bad_fork_cleanup_bore;\n"
           "\t\ttask_fork_bore(p, current, clone_flags, p->start_time);\n"
           "\t}\n"
           "#endif /* CONFIG_SCHED_BORE */\n")
    if old in src:
        src = src.replace(old, new, 1)
    elif "goto bad_fork_cleanup_bore;" in src:
        pass
    else:
        print(f"bore12-flat: {path}: task_fork_bore call-site anchor missing",
              file=sys.stderr)
        sys.exit(1)

    # 3. The cleanup label, falling through to bad_fork_cancel_cgroup.
    lbl_anchor = "bad_fork_cancel_cgroup:\n"
    lbl = ("bad_fork_cleanup_bore:\n"
           "#ifdef CONFIG_SCHED_BORE\n"
           "\tkfree(p->bore);\n"
           "\tp->bore = NULL;\n"
           "#endif /* CONFIG_SCHED_BORE */\n"
           + lbl_anchor)
    if lbl_anchor in src and "bad_fork_cleanup_bore:\n" not in src:
        src = src.replace(lbl_anchor, lbl, 1)
    elif "bad_fork_cleanup_bore:\n" in src:
        pass
    else:
        print(f"bore12-flat: {path}: bad_fork_cancel_cgroup label missing",
              file=sys.stderr)
        sys.exit(1)

    # 4. Free hook in free_task - the single choke point every death path
    # (including early copy_process failures, which see NULL) funnels into.
    anchor = "void free_task(struct task_struct *tsk)\n{\n"
    hook = (anchor +
            "#ifdef CONFIG_SCHED_BORE\n"
            "\tkfree(tsk->bore);\n"
            "\ttsk->bore = NULL;\n"
            "#endif /* CONFIG_SCHED_BORE */\n")
    if anchor in src and "kfree(tsk->bore);" not in src:
        src = src.replace(anchor, hook, 1)
    elif "kfree(tsk->bore);" in src:
        pass
    else:
        print(f"bore12-flat: {path}: free_task anchor missing",
              file=sys.stderr)
        sys.exit(1)

    return src


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: bore12_flat.py <file> [file...]", file=sys.stderr)
        return 2
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8", errors="surrogateescape") as fh:
            src = fh.read()
        orig = src
        if path.endswith("bore.h"):
            src = rewrite_bore_h(src, path)
        elif path.endswith("bore.c"):
            src = rewrite_bore_c(src, path)
        elif path.endswith("fork.c"):
            src = rewrite_fork_c(src, path)
        else:
            src = rewrite_generic(src, path)
        if src != orig:
            with open(path, "w", encoding="utf-8",
                      errors="surrogateescape") as fh:
                fh.write(src)
        hops = len(HOPS.findall(orig))
        print(f"bore12-flat: {path}: {hops} arrow hops rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
