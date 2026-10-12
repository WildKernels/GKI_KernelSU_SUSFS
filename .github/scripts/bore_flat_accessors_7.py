#!/usr/bin/env python3
"""Translate BORE 7.0.0 `p->bore.X` accessors to flat task_struct members.

Companion to bore_task_slots_7.py, which moves bore_ctx into task_struct's
ANDROID_KABI_RESERVE(4..8) slots. Once slotted, the members are flat
(p->burst_time, p->penalty, ...), so every accessor must drop the `.bore`
hops. Handles three shapes:

  1. Direct member hops:  `X->bore.MEMBER`         -> `X->MEMBER`
     (any expression before ->bore, e.g. current->bore.futex_waiting,
      task_of(se)->bore.futex_waiting, parent->bore.subtree)
  2. ctx pointer locals:  `struct bore_ctx *ctx = &p->bore;`
     -> removed; every later `ctx->M` in the same function becomes `p->M`.
     The four 7.0.0 functions using this shorthand (update_penalty,
     update_curr_bore, restart_burst_bore, task_fork_bore) reference only
     slotted members through ctx, verified by shape audit.
  3. reset_task_bore's contiguous memset becomes per-member assignments
     (the state is no longer one contiguous object).

Idempotent: a second run finds no `->bore.` and no ctx locals, and exits 0.

Usage: bore_flat_accessors_7.py <file.c> [file.c ...]
"""
import re
import sys

MEMBERS = ("burst_time", "credit_sleep", "prev_penalty", "curr_penalty",
           "penalty", "stop_update", "futex_waiting", "subtree", "group")

CTX_LOCAL = re.compile(
    r"^\s*struct bore_ctx \*ctx = &([A-Za-z_][A-Za-z0-9_]*)->bore;\n",
    re.M)


def flatten_ctx_funcs(src: str) -> str:
    """Remove `struct bore_ctx *ctx = &X->bore;` lines and rewrite the
    function bodies' ctx->M to X->M."""
    while True:
        m = CTX_LOCAL.search(src)
        if not m:
            break
        var = m.group(1)
        start = m.start()
        # find the end of the enclosing function: the next line that is
        # exactly '}' at column 0 after the local's position
        close = src.find("\n}\n", m.end())
        if close == -1:
            print("bore-flat: could not find function end after ctx local; "
                  "aborting", file=sys.stderr)
            sys.exit(1)
        body_end = close + len("\n}\n")
        body = src[start:body_end]
        newbody = body[m.end() - start:]
        newbody = re.sub(r"\bctx->(%s)\b" % "|".join(MEMBERS),
                         rf"{var}->\1", newbody)
        # drop the local declaration line itself
        head = src[:start]
        tail = src[body_end:]
        src = head + newbody + tail
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

        # 3. reset_task_bore memset -> per-member assigns
        memset_re = re.compile(
            r"\{ memset\(&p->bore, 0, sizeof\(struct bore_ctx\)\); \}")
        if memset_re.search(src):
            zero = ("{\n\tp->burst_time = 0;\n\tp->credit_sleep = 0;\n"
                    "\tp->prev_penalty = 0;\n\tp->curr_penalty = 0;\n"
                    "\tp->penalty = 0;\n\tp->stop_update = false;\n"
                    "\tp->futex_waiting = false;\n\tp->subtree.value = 0;\n"
                    "\tp->group.value = 0;\n}")
            src = memset_re.sub(zero, src)

        # 2. ctx pointer locals
        src = flatten_ctx_funcs(src)

        # 1. remaining direct hops (incl. &parent->bore.subtree shapes)
        src = re.sub(r"->bore\.(%s)\b" % "|".join(MEMBERS), r"->\1", src)

        if src != orig:
            with open(path, "w", encoding="utf-8",
                      errors="surrogateescape") as fh:
                fh.write(src)
            print(f"bore-flat: {path}: accessors flattened")
        else:
            print(f"bore-flat: {path}: nothing to translate")
        if re.search(r"->bore\.|struct bore_ctx \*ctx", src):
            print(f"bore-flat: {path}: WARNING residual bore_ctx access",
                  file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())