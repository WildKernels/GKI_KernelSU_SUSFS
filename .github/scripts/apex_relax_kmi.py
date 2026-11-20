#!/usr/bin/env python3
"""Relax GKI KMI enforcement for a build: the plain-make behaviour, in kleaf.

Why. Vendor modules on a shipping device are built for the sublevel it shipped
with, and the KMI unprotected list is regenerated every kernel release. A kleaf
build populates that list (CONFIG_UNUSED_KSYMS_WHITELIST) and trims exports down
to it (trim_nonlisted_kmi), so a vendor module that imports a symbol the newer
list no longer carries is refused - or, with trimming, finds the symbol gone.

Either way the module never loads. For Bluetooth or sound that is a dead feature;
for a storage, clock, regulator or pinctrl module it is first-stage init failing
to mount super, which produces no logcat, no adb, and nothing in pstore.

A plain `make` build (arch/arm64/configs/gki_defconfig, no whitelist) leaves the
KMI symbol file empty, and kernel/module/gki_module.c short-circuits on exactly
that: exports may not be protected and any symbol may be imported. That is why
device trees built that way load every unsigned vendor module regardless of
sublevel.

This script reproduces that inside kleaf, without disabling anything that could
change behaviour for a kernel that already works:

  BUILD.bazel    trim_nonlisted_kmi False - stops trimming exports down to the
                 KMI list and stops populating CONFIG_UNUSED_KSYMS_WHITELIST,
                 which by itself short-circuits both KMI gates
  BUILD.bazel    drop protected_modules_list / protected_module_names_list
                 references, so no protected-module set is generated
  modules.bzl    protected_modules = [] in get_gki_protected_modules_list()
  gki_module.c   CONFIG_APEX_RELAX_GKI_MODULE_KMI, belt and braces for the case
                 where something repopulates the whitelist (6.1 and 6.6 only -
                 the file does not exist in 5.10/5.15, where this code lives in
                 kernel/module.c, nor in 6.12/6.18, which dropped it)

Not touched: MODVERSIONS CRC verification. A module built against genuinely
incompatible types still fails with "disagrees about version of symbol". This
never loads a layout-mismatched module - that is the other bypass, bad_version,
which is a different gate and is not part of this.

Usage: apex_relax_kmi.py <kernel/common>
Idempotent.
"""
import re
import subprocess
import sys
from pathlib import Path

PATCH = Path(__file__).resolve().parent.parent / "patches/apex-relax/0001-relax-gki-module-kmi.patch"


def die(msg: str):
    sys.stderr.write(f"error: {msg}\n")
    sys.exit(1)


def read(p: Path) -> str:
    if not p.is_file():
        die(f"{p}: not found")
    return p.read_text()


def relax_build_bazel(root: Path) -> list:
    notes = []
    p = root / "BUILD.bazel"
    t = read(p)
    orig = t

    n = t.count('"trim_nonlisted_kmi": True')
    if n:
        t = t.replace('"trim_nonlisted_kmi": True', '"trim_nonlisted_kmi": False')
        notes.append(f"BUILD.bazel: trim_nonlisted_kmi True -> False ({n} target(s))")
    elif '"trim_nonlisted_kmi": False' not in t:
        notes.append("BUILD.bazel: no trim_nonlisted_kmi setting found - nothing to relax")

    # no protected-module set at all
    for key in ("protected_modules_list", "protected_module_names_list"):
        pattern = re.compile(r'^\s*"' + key + r'":\s*"[^"]*",\s*$\n?', re.MULTILINE)
        removed = len(pattern.findall(t))
        if removed:
            t = pattern.sub("", t)
            notes.append(f"BUILD.bazel: removed {key} ({removed} occurrence(s))")

    if t != orig:
        p.write_text(t)
    return notes


def relax_modules_bzl(root: Path) -> list:
    notes = []
    p = root / "modules.bzl"
    if not p.is_file():
        return ["modules.bzl: not present - skipped"]
    t = read(p)
    orig = t

    # top-level assignment form
    if re.search(r"^protected_modules = \[", t, re.MULTILINE):
        t = re.sub(r"^protected_modules = \[.*\]", "protected_modules = []",
                   t, flags=re.MULTILINE)

    # computed form inside get_gki_protected_modules_list()
    t = re.sub(r"^\s*protected_modules = \[mod for mod in all_gki_modules[^\]]*\]",
               "    protected_modules = []", t, flags=re.MULTILINE)

    if t != orig:
        p.write_text(t)
        notes.append("modules.bzl: protected_modules = []")
    else:
        notes.append("modules.bzl: no protected_modules computation found - left alone")
    return notes


def apply_relax_patch(root: Path) -> list:
    if not (root / "kernel/module/gki_module.c").is_file():
        return ["gki_module.c: absent in this family - import-gate patch skipped "
                "(the trimmed/whitelist change above is what matters)"]
    if not PATCH.is_file():
        die(f"{PATCH}: not found")

    check = subprocess.run(["patch", "-p1", "--dry-run", "--forward", "-f", "-i", str(PATCH)],
                           cwd=root, capture_output=True, text=True)
    if check.returncode != 0:
        if "Reversed (or previously applied)" in check.stdout + check.stderr or \
           "Skipping patch" in check.stdout + check.stderr:
            return ["gki_module.c: relax patch already applied"]
        die("relax patch does not apply:\n" + check.stdout + check.stderr)

    run = subprocess.run(["patch", "-p1", "--forward", "-f", "-i", str(PATCH)],
                         cwd=root, capture_output=True, text=True)
    if run.returncode != 0:
        die("relax patch failed to apply:\n" + run.stdout + run.stderr)

    conf = root / "arch/arm64/configs/gki_defconfig"
    if conf.is_file() and "CONFIG_APEX_RELAX_GKI_MODULE_KMI=y" not in conf.read_text():
        die("relax patch applied but gki_defconfig has no CONFIG_APEX_RELAX_GKI_MODULE_KMI")

    return ["gki_module.c: CONFIG_APEX_RELAX_GKI_MODULE_KMI=y"]


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: apex_relax_kmi.py <kernel/common>")
    root = Path(sys.argv[1])
    if not (root / "BUILD.bazel").is_file():
        # 5.10/5.15 build through build/build.sh, which never populates the KMI
        # whitelist - the gates are already short-circuited there.
        if (root.parent / "build/build.sh").is_file() or (root / "build/build.sh").is_file():
            print("apex relax: legacy build.sh tree, KMI lists are already empty - nothing to do")
            return
        die(f"{root}/BUILD.bazel not found - is this kernel/common?")

    notes = relax_build_bazel(root) + relax_modules_bzl(root) + apply_relax_patch(root)
    for n in notes:
        print(f"apex relax: {n}")
    print("apex relax: KMI enforcement relaxed for this build")


if __name__ == "__main__":
    main()
