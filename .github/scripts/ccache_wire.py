#!/usr/bin/env python3
"""Wire ccache into a legacy (build.sh) GKI kernel tree.

Why this exists
---------------
`build-kernel` exported CC/CXX/HOSTCC/HOSTCXX pointing at ccache, and none of it
reached the compiler. Two independent reasons, both measured on run 40056822635
(android12-5.10, 988 s build):

1. `build/build.sh` (and `build/_setup_env.sh` on 13-5.10/13-5.15) takes the
   LLVM branch, which *resets* `CC=clang` / `HOSTCC=clang` after the
   environment has been read, and forwards only `LLVM=1` to make -- no `CC=`
   on the make command line. The wrapper is discarded there.
2. `make ... LLVM=1` makes the kernel Makefile assign them unconditionally
   (`ifneq ($(LLVM),)` / `CC = clang` / `HOSTCC = clang`), and a make-level
   assignment beats the environment.

Observable symptom: the ccache directory was byte-identical before and after
the build (0.6 / 12.0 GB) and `ccache -s` reported no counters, i.e. ~2.8k
translation units were compiled with no caching at all.

What this does
--------------
* common/Makefile: replace `CC = clang` / `HOSTCC = clang` with an origin
  guard, so the environment wins but the tree still defaults to clang. A plain
  `?=` would NOT work: make predefines `CC=cc` (origin `default`, so `?=` never
  fires) and `HOSTCC` has no default at all (origin `undefined`), hence the
  filter over both origins.
* build/{_setup_env,build}.sh: rewrite the LLVM-branch reset to
  `CC="${CCACHE_PREFIX:-}clang"` so an optional wrapper prefix survives, and
  stays plain `clang` when the variable is unset (forks, non-ccache builds).

Idempotent. Exits non-zero when the tree does not look like what it expects,
so a kernel-side refactor fails the leg loudly instead of silently losing the
cache again.
"""

import re
import sys
from pathlib import Path

ORIGIN_GUARD = (
    "ifeq ($(filter undefined default,$(origin {var})),$(origin {var}))\n"
    "{var} := clang\n"
    "endif"
)
GUARDED_RE = re.compile(
    r"^ifeq \(\$\(filter undefined default,\$\(origin (CC|HOSTCC)\)\),\$\(origin \1\)\)\n"
    r"\1 := clang\nendif$",
    re.M,
)
BARE_ASSIGN_RE = re.compile(r"^(?P<indent>[ ]*)(?P<var>CC|HOSTCC)[ \t]*=[ \t]*clang[ \t]*$", re.M)
SCRIPT_RESET_RE = re.compile(r"^(?P<indent>  )(?P<var>CC|HOSTCC)=clang$", re.M)
SCRIPT_HOOK_SUFFIX = '"${CCACHE_PREFIX:-}clang"'

SCRIPT_CANDIDATES = ("build/_setup_env.sh", "build/build.sh")


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def wire_makefile(path: Path) -> str:
    text = path.read_text()
    guarded = set(GUARDED_RE.findall(text))
    if guarded == {"CC", "HOSTCC"}:
        return "already guarded"

    hits = list(BARE_ASSIGN_RE.finditer(text))
    names = sorted(m.group("var") for m in hits)
    if names != ["CC", "HOSTCC"]:
        fail(
            f"{path}: expected exactly one `CC = clang` and one `HOSTCC = clang` in the "
            f"LLVM block, found {names or 'none'}"
        )

    for m in reversed(hits):
        var = m.group("var")
        text = text[: m.start()] + ORIGIN_GUARD.format(var=var) + text[m.end():]

    if sorted(GUARDED_RE.findall(text)) != ["CC", "HOSTCC"]:
        fail(f"{path}: rewrite did not produce the expected guards")
    if BARE_ASSIGN_RE.search(text):
        fail(f"{path}: a bare `CC/HOSTCC = clang` assignment survived")
    path.write_text(text)
    return "guards written"


def wire_scripts(tree: Path):
    """Return (patched, already) lists. Either one being non-empty means a
    build script still takes CC from the (prefixed) environment."""
    patched, already = [], []
    for rel in SCRIPT_CANDIDATES:
        p = tree / rel
        if not p.exists():
            continue
        text = p.read_text()
        hits = list(SCRIPT_RESET_RE.finditer(text))
        if not hits:
            if SCRIPT_HOOK_SUFFIX in text:
                already.append(rel)
            continue
        for m in reversed(hits):
            var, indent = m.group("var"), m.group("indent")
            text = text[: m.start()] + f'{indent}{var}=' + SCRIPT_HOOK_SUFFIX + text[m.end():]
        leftover = SCRIPT_RESET_RE.findall(text)
        if leftover:
            fail(f"{p}: still resets {leftover} unconditionally")
        p.write_text(text)
        patched.append(f"{rel} ({len(hits)} reset(s))")
    return patched, already


def main() -> int:
    tree = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    makefile = tree / "common" / "Makefile"
    if not makefile.exists():
        fail(f"{makefile}: not found (is this a build.sh kernel tree?)")

    status = wire_makefile(makefile)
    patched, already = wire_scripts(tree)
    if not (patched or already):
        fail(
            "no build script carried the LLVM compiler reset "
            f"(looked for {', '.join(SCRIPT_CANDIDATES)}) -- ccache prefix has nowhere to land"
        )

    parts = [f"common/Makefile {status}"]
    if patched:
        parts.append("patched " + "; ".join(patched))
    if already:
        parts.append("already hooked " + "; ".join(already))
    print("[+] ccache wiring: " + ", ".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
