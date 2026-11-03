#!/usr/bin/env python3
"""Export init_ipc_ns / put_ipc_ns so android17-6.18's rust_binder.ko links.

6.18's gki_defconfig builds CONFIG_ANDROID_BINDER_IPC_RUST=m and the Rust driver
references both symbols, but neither is exported in this tree, so modpost dies:

  ERROR: modpost: "put_ipc_ns"  [drivers/android/binder/rust_binder.ko] undefined!
  ERROR: modpost: "init_ipc_ns" [drivers/android/binder/rust_binder.ko] undefined!

Turning the module off is not an option: Kleaf's GKI target expects
drivers/android/binder/rust_binder.ko in its outputs and fails the build with
"Unable to find drivers/android/binder/rust_binder.ko in any of the following
directories". Exporting the two symbols is the minimal fix and matches what the
driver assumes.

Idempotent, anchor-checked.

Usage: binder_ipc_ns_exports.py <kernel/common>
"""

import os
import sys
from typing import NoReturn


def die(msg: str) -> NoReturn:
    sys.exit(f"ERROR: {msg}")


def find_definition(text: str, signature: str) -> int:
    """Return the offset just past the closing brace of a definition."""
    start = text.find(signature)
    if start < 0:
        die(f"signature not found: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        die(f"opening brace not found for {signature}")
    i, depth = brace + 1, 1
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    if depth:
        die(f"unbalanced braces for {signature}")
    return i


def export_after(path: str, anchor: str, export: str, is_struct: bool) -> None:
    src = open(path, encoding="utf-8").read()
    if export in src:
        print(f"  {os.path.basename(path)}: {export} already present")
        return
    end = find_definition(src, anchor)
    if is_struct:
        # find_definition stops just past the closing brace; step over the
        # trailing semicolon so the export lands after "};" and not inside it.
        j = end
        if j < len(src) and src[j] == ";":
            j += 1
        src = src[:j] + "\n" + export + src[j:]
    else:
        src = src[:end] + "\n" + export + src[end:]
    open(path, "w", encoding="utf-8").write(src)
    print(f"  {os.path.basename(path)}: added {export}")


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: binder_ipc_ns_exports.py <kernel/common>")
    root = sys.argv[1].rstrip("/")
    print(f"[+] rust_binder ipc_ns exports: {root}")
    export_after(
        os.path.join(root, "ipc/msgutil.c"),
        "struct ipc_namespace init_ipc_ns = {",
        "EXPORT_SYMBOL_GPL(init_ipc_ns);",
        is_struct=True,
    )
    export_after(
        os.path.join(root, "ipc/namespace.c"),
        "void put_ipc_ns(struct ipc_namespace *ns)",
        "EXPORT_SYMBOL_GPL(put_ipc_ns);",
        is_struct=False,
    )
    for rel, needle in (
        ("ipc/msgutil.c", "EXPORT_SYMBOL_GPL(init_ipc_ns);"),
        ("ipc/namespace.c", "EXPORT_SYMBOL_GPL(put_ipc_ns);"),
    ):
        if needle not in open(os.path.join(root, rel), encoding="utf-8").read():
            die(f"{rel}: {needle} missing after write")
    print("[+] exports verified")


if __name__ == "__main__":
    main()
