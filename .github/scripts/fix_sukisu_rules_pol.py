#!/usr/bin/env python3
"""Fix the `policydb->latest_granting` typo in SukiSU-Ultra's selinux/rules.c.

SukiSU-Ultra commits that merged tiann/KernelSU#3964 ("Fix SELinux generation
tracking for policy updates") shipped this line in apply_kernelsu_rules():

    db = &pol->policydb;

    policydb->latest_granting = old_pol->latest_granting + 1;   <-- typo

There is no variable called `policydb` in that scope (the locals are `pol`,
`old_pol` and `db`), so clang resolves the name to `struct policydb` and the
whole kernel build dies with:

    rules.c:194:5: error: must use 'struct' tag to refer to type 'policydb'
    rules.c:194:13: error: expected identifier or '('

`latest_granting` lives in `struct selinux_policy` on 5.10+, and the sibling
function a few hundred lines below already spells it `pol->latest_granting`.
Upstream main fixed the line; pinned commits from the affected window did not.

Usage:  fix_sukisu_rules_pol.py <path-to-SukiSU-Ultra-checkout>

Behaviour:
  * buggy line absent      -> prints "not needed" and exits 0 (upstream fixed it)
  * buggy line present     -> rewrites it to `pol->latest_granting`, then
                              re-reads the file and exits 1 if the typo is
                              still there or `pol` is not a declared
                              `struct selinux_policy *` in the enclosing code
There is no best-effort mode: a half-applied fix would only move the failure
into the 10-minute Bazel build.
"""

import re
import sys
from pathlib import Path
from typing import NoReturn

BUGGY_RE = re.compile(
    r"^(?P<indent>[ \t]*)policydb->latest_granting"
    r"(?P<rest>[ \t]*=[ \t]*old_pol->latest_granting[ \t]*\+[ \t]*1;.*)$"
)
ANY_BUGGY_RE = re.compile(r"\bpolicydb->latest_granting\b")
POL_DECL_RE = re.compile(r"struct\s+selinux_policy\s*\*[^;{]*\bpol\b")
LOOKBACK_LINES = 120


def fail(msg: str) -> NoReturn:
    sys.exit(f"ERROR: {msg}")


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: fix_sukisu_rules_pol.py <path-to-SukiSU-Ultra-checkout>")

    rules = Path(sys.argv[1]) / "kernel" / "selinux" / "rules.c"
    if not rules.is_file():
        fail(f"{rules} not found")

    lines = rules.read_text(encoding="utf-8").splitlines(keepends=True)

    hits = [i for i, ln in enumerate(lines) if BUGGY_RE.match(ln.rstrip("\r\n"))]
    if not hits:
        if any(ANY_BUGGY_RE.search(ln) for ln in lines):
            fail(
                "found 'policydb->latest_granting' in a shape this script does not "
                "recognise -- inspect kernel/selinux/rules.c by hand"
            )
        print("[=] SukiSU rules.c: latest_granting typo not present, nothing to do")
        return

    for i in hits:
        window = lines[max(0, i - LOOKBACK_LINES):i]
        if not any(POL_DECL_RE.search(ln) for ln in window):
            fail(
                f"{rules}:{i + 1}: no 'struct selinux_policy *pol' declared within "
                f"{LOOKBACK_LINES} lines above -- the fix would reference an undeclared "
                "variable"
            )

    for i in hits:
        m = BUGGY_RE.match(lines[i].rstrip("\r\n"))
        eol = lines[i][len(lines[i].rstrip("\r\n")):]
        lines[i] = f"{m.group('indent')}pol->latest_granting{m.group('rest')}{eol}"

    rules.write_text("".join(lines), encoding="utf-8")

    after = rules.read_text(encoding="utf-8").splitlines()
    if any(ANY_BUGGY_RE.search(ln) for ln in after):
        fail(f"{rules}: typo still present after patching")
    patched = [ln for ln in after if re.search(r"\bpol->latest_granting\s*=\s*old_pol->latest_granting", ln)]
    if len(patched) < len(hits):
        fail(f"{rules}: expected at least {len(hits)} pol->latest_granting assignment(s) after patching")

    print(
        f"[+] SukiSU rules.c: policydb->latest_granting -> pol->latest_granting "
        f"({len(hits)} occurrence(s), line(s) {', '.join(str(i + 1) for i in hits)})"
    )


if __name__ == "__main__":
    main()
