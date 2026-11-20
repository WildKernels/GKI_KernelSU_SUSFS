#!/usr/bin/env python3
"""Turn off KMI symbol trimming for a build - the minimal relax.

What trimming does. A kleaf build with trim_nonlisted_kmi=True sets
CONFIG_TRIM_UNUSED_KSYMS together with CONFIG_UNUSED_KSYMS_WHITELIST, and the
linker drops every export that is not on android/abi_gki_aarch64. That is a KMI
size opt-in, not a correctness requirement: the symbols simply cease to exist.

Why it matters for a device. Vendor modules are built for the sublevel the device
shipped with. If one of them imports a symbol that the newer KMI list no longer
carries, the symbol is not merely refused - it is absent, so the module fails with
"Unknown symbol". For Bluetooth or sound that is a dead feature; for storage,
clock, regulator or pinctrl it is first-stage init failing to mount super, which
produces no console, no adb and nothing in pstore.

What this changes:
  BUILD.bazel        trim_nonlisted_kmi False, and kmi_symbol_list_strict_mode
                     False - without trimming the export set is a superset of the
                     list, and strict mode treats every new export as a violation
  gki_defconfig      explicit "# CONFIG_TRIM_UNUSED_KSYMS is not set", so the
                     intent is visible in .config and survives non-kleaf paths

ABI effect: none for anything that exists today. Trimming only removes exports,
so switching it off restores a superset of the current set - every symbol keeps
the CRC it already had. Nothing that loads today can start failing, and
MODVERSIONS still refuses genuinely incompatible modules. That is also why the
2-way CRC gate is unaffected: it joins on symbol name and compares CRCs of the
symbols both sides have.

Usage: kmi_no_trim.py <kernel/common>
Idempotent.
"""
import re
import sys
from pathlib import Path

DEFCONFIG_LINE = "# CONFIG_TRIM_UNUSED_KSYMS is not set"


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

    s = t.count('"kmi_symbol_list_strict_mode": True')
    if s:
        t = t.replace('"kmi_symbol_list_strict_mode": True', '"kmi_symbol_list_strict_mode": False')
        notes.append(f"BUILD.bazel: kmi_symbol_list_strict_mode True -> False ({s} target(s))")

    if t != orig:
        p.write_text(t)
    return notes


def explicit_defconfig(root: Path) -> list:
    p = root / "arch/arm64/configs/gki_defconfig"
    if not p.is_file():
        return ["gki_defconfig: not present - skipped"]
    t = p.read_text()
    if DEFCONFIG_LINE in t:
        return ["gki_defconfig: trim already disabled explicitly"]
    # next to the other module/KMI switches, so the intent reads in one place
    for anchor in ("CONFIG_APEX_RELAX_GKI_MODULE_KMI=y\n",
                   "CONFIG_MODULE_SIG_PROTECT=y\n"):
        if anchor in t:
            p.write_text(t.replace(anchor, anchor + DEFCONFIG_LINE + "\n", 1))
            return [f"gki_defconfig: added '{DEFCONFIG_LINE}'"]
    p.write_text(t.replace("CONFIG_MODVERSIONS=y\n",
                           "CONFIG_MODVERSIONS=y\n" + DEFCONFIG_LINE + "\n", 1))
    return [f"gki_defconfig: added '{DEFCONFIG_LINE}' after CONFIG_MODVERSIONS"]


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: kmi_no_trim.py <kernel/common>")
    root = Path(sys.argv[1])

    if not (root / "BUILD.bazel").is_file():
        # 5.10/5.15 build through build/build.sh, which never sets a whitelist.
        if (root.parent / "build/build.sh").is_file() or (root / "build/build.sh").is_file():
            print("kmi no-trim: legacy build.sh tree - no KMI whitelist, nothing to do")
            return
        die(f"{root}/BUILD.bazel not found - is this kernel/common?")

    notes = relax_build_bazel(root) + explicit_defconfig(root)
    for n in notes:
        print(f"kmi no-trim: {n}")
    print("kmi no-trim: symbol trimming disabled for this build")


if __name__ == "__main__":
    main()
