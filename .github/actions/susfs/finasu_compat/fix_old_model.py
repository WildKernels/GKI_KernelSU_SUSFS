#!/usr/bin/env python3
"""Complete the 10_enable selinux_hide port for pre-6.6 kernels.

When the susfs selinux_hide rewrite applies only partially, the file can end
up without fake_state entirely, while the susfs kernel patch's
security/selinux/selinuxfs.c externs it (and expects it backed by the sepolicy
backup, per the 10_enable old-model design). Define it globally, initialise it
from backup_sepolicy in enable(), and globalise the fake_status trio for the
patch's externs. No-op when fake_state is already present.
"""
import sys

def main():
    if len(sys.argv) != 2:
        print("usage: fix_old_model.py <selinux_hide.c>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    try:
        src = open(path, encoding="utf-8").read()
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return 1
    if "fake_state" in src:
        print("selinux_hide.c: fake_state already present, no-op")
        return 0

    mutex = "static DEFINE_MUTEX(selinux_hide_mutex);\n"
    assert src.count(mutex) == 1, "mutex anchor not unique"
    src = src.replace(mutex, mutex + "struct selinux_state fake_state;\n", 1)

    src = src.replace(
        "static DEFINE_STATIC_KEY_FALSE(fake_status_initialize_key);",
        "DEFINE_STATIC_KEY_FALSE(fake_status_initialize_key);", 1)
    src = src.replace(
        "static struct page *fake_status = NULL;",
        "struct page *fake_status = NULL;\nvoid initialize_fake_status(void);", 1)
    src = src.replace(
        "static void initialize_fake_status()",
        "void initialize_fake_status(void)", 1)

    # susfs owns selinuxfs: skip ksu-side hooks, but prime fake_state from the
    # backup policy so the patch's selinuxfs handlers resolve contexts <6.6.
    anchor = "#ifdef CONFIG_KSU_SUSFS\n    /* FINASU_SUSFS_OWNS_SELINUXFS"
    assert anchor in src, "FINASU_SUSFS_OWNS_SELINUXFS guard not found"
    src = src.replace(
        anchor,
        anchor
        + "\n#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 6, 0)\n"
        "    fake_state.initialized = true;\n"
        "    fake_state.policy = backup_sepolicy;\n"
        "#endif",
        1)

    try:
        open(path, "w", encoding="utf-8").write(src)
    except OSError as exc:
        print(f"error: cannot write {path}: {exc}", file=sys.stderr)
        return 1
    print("selinux_hide.c: fake_state defined/globalised for susfs kernel patch")
    return 0

if __name__ == "__main__":
    sys.exit(main())
