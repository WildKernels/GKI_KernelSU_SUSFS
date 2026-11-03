#!/usr/bin/env python3
"""Compile fixes for the ported SUSFS tree on android17-6.18.

Three 6.18 deltas that the 6.12 patch cannot carry, all anchor-based:

1. fs/namespace.c - susfs_alloc_unshare_ksu_vfsmnt() / _non_unshare_() were
   copies of 6.12's alloc_vfsmnt() so a ksu mount could take a fake mnt_id
   without touching the allocator. 6.18 moved mount ids to an xarray and changed
   struct mount around them, and the branches do not even agree with each other
   (some have mnt_hash as list_head, all dropped mnt_umounting, mnt_id_ida is now
   mnt_id_xa):

     namespace.c:367: incompatible pointer types passing 'struct hlist_head *' to
                     parameter of type 'struct list_head *'
     namespace.c:370: no member named 'mnt_umounting' in 'struct mount'
     namespace.c:395: use of undeclared identifier 'mnt_id_ida'

   A per-branch copy cannot work, so both become thin wrappers around the tree's
   own alloc_vfsmnt(): the mounts are allocated normally and carry a real
   mnt_id. Mount *hiding* is unaffected (that comes from the lookup hooks); only
   the fake-id layer is not ported.

2. fs/namespace.c - the three susfs_get_non_sus_* helpers are defined without a
   prior declaration, which -Wmissing-prototypes treats as an error in GKI
   builds. Declaration added above each definition.

3. security/selinux/hooks.c - 6.18 split SELinux's per-cred state:
   selinux_cred() now returns struct cred_security_struct (task_security_struct
   only keeps the AVC cache), so the copied selinux_setprocattr body needs the
   new type. Member names (sid/exec_sid/create_sid/keycreate_sid/) are unchanged.

Idempotent, anchor-checked, fails loudly on drift.

Usage: susfs_618_compile_fixes.py <kernel/common>
"""

import os
import re
import sys
from typing import NoReturn


def die(msg: str) -> NoReturn:
    sys.exit(f"ERROR: {msg}")


ALLOC_FWD = "static struct mount *alloc_vfsmnt(const char *name);\n\n"

ALLOC_HELPER = """/* 6.18 port of the SUSFS mount allocators.
 *
 * 6.12 copied alloc_vfsmnt()'s body so a ksu mount could take a fake mnt_id
 * without borrowing the IDA. 6.18 moved mount ids to an xarray and reworked
 * struct mount (mnt_hash container, no mnt_umounting), and the branches differ
 * from each other, so copying the body cannot work. Instead allocate with the
 * tree's own alloc_vfsmnt() and then swap the id: the real one is released back
 * to the xarray and the mount takes the id SUSFS wants. Nothing else in struct
 * mount has to be known here.
 */
static struct mount *susfs_alloc_ksu_vfsmnt(const char *name, int forced_mnt_id)
{
	struct mount *mnt = alloc_vfsmnt(name);

	if (!mnt)
		return NULL;

	/* release the id alloc_vfsmnt() took ... */
	xa_erase(&mnt_id_xa, mnt->mnt_id);

	if (forced_mnt_id) {
		/* ... and re-use the original mount's id (unshared clone) */
		mnt->mnt_id = forced_mnt_id;
	} else {
		int id = DEFAULT_KSU_MNT_ID + (int)atomic64_inc_return(&sus_mnt_id_ctr);

		while (xa_load(&mnt_id_xa, id))
			id++;
		mnt->mnt_id = id;
	}

	/* never collide with a real mnt_id_unique */
	mnt->mnt_id_unique = READ_ONCE(mnt_id_ctr) + atomic64_inc_return(&sus_mnt_id_ctr);
	return mnt;
}

static struct mount *susfs_alloc_unshare_ksu_vfsmnt(const char *name, int old_mnt_id)
{
	return susfs_alloc_ksu_vfsmnt(name, old_mnt_id);
}

static struct mount *susfs_alloc_non_unshare_ksu_vfsmnt(const char *name)
{
	return susfs_alloc_ksu_vfsmnt(name, 0);
}
"""

PROTOS = """int susfs_get_non_sus_mnt_id_from_mnt(struct mount *orig_mnt);
u64 susfs_get_non_sus_mnt_id_unique_from_mnt(struct mount *orig_mnt);
struct vfsmount *susfs_get_non_sus_vfsmnt_from_vfsmnt(struct vfsmount *vfsmnt);

"""


def find_func(text: str, signature: str) -> tuple[int, int]:
    """Return (start, end) offsets of a function definition, end is past the closing brace."""
    start = text.find(signature)
    if start < 0:
        die(f"signature not found: {signature}")
    brace = text.find("\n{", start)
    if brace < 0:
        die(f"opening brace not found for {signature}")
    i = brace + 2
    depth = 1
    while i < len(text) and depth:
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    if depth:
        die(f"unbalanced braces for {signature}")
    return start, i


def rewrite_alloc_helpers(root: str) -> None:
    path = os.path.join(root, "fs/namespace.c")
    src = open(path, encoding="utf-8").read()
    changed = False

    unshare_sig = "static struct mount *susfs_alloc_unshare_ksu_vfsmnt(const char *name, int old_mnt_id)"
    plain_sig = "static struct mount *susfs_alloc_non_unshare_ksu_vfsmnt(const char *name)"

    if "susfs_alloc_ksu_vfsmnt(const char *name, int forced_mnt_id)" in src:
        print("  namespace.c: fake-id allocators already ported")
    else:
        # Drop the copied 6.12 body of the second allocator, then replace the
        # first with the ported implementation (which defines both names).
        start, end = find_func(src, plain_sig)
        if "kmem_cache_zalloc" not in src[start:end]:
            die("namespace.c: susfs_alloc_non_unshare_ksu_vfsmnt is not the ported allocator")
        src = src[:start] + src[end:]
        start, end = find_func(src, unshare_sig)
        src = src[:start] + ALLOC_HELPER + src[end:]
        changed = True
        print("  namespace.c: allocators replaced by susfs_alloc_ksu_vfsmnt() (fake ids restored)")

    if changed and ALLOC_FWD not in src:
        anchor = "static struct mount *susfs_alloc_unshare_ksu_vfsmnt("
        at = src.find(anchor)
        if at < 0:
            die("namespace.c: allocator wrapper anchor vanished")
        block_start = src.rfind("#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT", 0, at)
        at = block_start if block_start > 0 else at
        src = src[:at] + ALLOC_FWD + src[at:]
        print("  namespace.c: forward declaration for alloc_vfsmnt() added")

    open(path, "w", encoding="utf-8").write(src)


def drop_fake_id_free_guard(root: str) -> None:
    """mnt_free_id() skipped freeing for mounts flagged KSU_UNSHARED_MNT.

    That guard only makes sense when the mount took a fake id from the old IDA
    scheme. With real ids (the wrappers above) skipping the free would leak an
    xarray slot, so drop the guard.
    """
    path = os.path.join(root, "fs/namespace.c")
    src = open(path, encoding="utf-8").read()
    guard = (
        "#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n"
        "\tif (unlikely(mnt->mnt.mnt_flags & VFSMOUNT_MNT_FLAGS_KSU_UNSHARED_MNT))\n"
        "\t\treturn;\n"
        "#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n"
    )
    if guard not in src:
        print("  namespace.c: mnt_free_id() guard already absent")
        return
    src = src.replace(guard, "", 1)
    open(path, "w", encoding="utf-8").write(src)
    print("  namespace.c: dropped mnt_free_id() fake-id guard (ids are real now)")


def add_missing_prototypes(root: str) -> None:
    path = os.path.join(root, "fs/namespace.c")
    src = open(path, encoding="utf-8").read()
    if PROTOS.split("\n")[0] + "\n" in src and src.count("int susfs_get_non_sus_mnt_id_from_mnt(struct mount *orig_mnt)") > 1:
        print("  namespace.c: susfs_get_non_sus_* prototypes already present")
        return
    sig = "int susfs_get_non_sus_mnt_id_from_mnt(struct mount *orig_mnt) {"
    if sig not in src:
        print("  namespace.c: susfs_get_non_sus_* definitions not found (nothing to do)")
        return
    at = src.find(sig)
    src = src[:at] + PROTOS + src[at:]
    open(path, "w", encoding="utf-8").write(src)
    print("  namespace.c: susfs_get_non_sus_* prototypes added")


SVC_PROTOS = """int susfs_security_context_to_sid(const char *scontext, u32 scontext_len, u32 *sid, gfp_t gfp);
int susfs_security_context_str_to_sid(const char *scontext, u32 *sid, gfp_t gfp);
void susfs_security_compute_av_user(u32 ssid, u32 tsid, u16 tclass, struct av_decision *avd);

"""


def add_services_prototypes(root: str) -> None:
    """-Wmissing-prototypes: the ported helpers need declarations above them."""
    path = os.path.join(root, "security/selinux/ss/services.c")
    src = open(path, encoding="utf-8").read()
    sig = "int susfs_security_context_to_sid(const char *scontext, u32 scontext_len, u32 *sid,"
    if sig not in src:
        print("  services.c: susfs_security_* definitions not found (nothing to do)")
        return
    if "int susfs_security_context_to_sid(const char *scontext, u32 scontext_len, u32 *sid, gfp_t gfp);" in src:
        print("  services.c: susfs_security_* prototypes already present")
        return
    at = src.find(sig)
    src = src[:at] + SVC_PROTOS + src[at:]
    open(path, "w", encoding="utf-8").write(src)
    print("  services.c: susfs_security_* prototypes added")


STATFS_PROTOS = """int statfs_by_dentry_wrapper(struct dentry *dentry, struct kstatfs *buf);
int calculate_f_flags_wrapper(struct vfsmount *mnt);

"""


def add_statfs_prototypes(root: str) -> None:
    """-Wmissing-prototypes: statfs wrappers are exported for KernelSU to call."""
    path = os.path.join(root, "fs/statfs.c")
    if not os.path.exists(path):
        print("  statfs.c: not present (nothing to do)")
        return
    src = open(path, encoding="utf-8").read()
    sig = "int statfs_by_dentry_wrapper(struct dentry *dentry, struct kstatfs *buf){"
    if sig not in src:
        print("  statfs.c: wrapper definitions not found (nothing to do)")
        return
    if "int statfs_by_dentry_wrapper(struct dentry *dentry, struct kstatfs *buf);" in src:
        print("  statfs.c: prototypes already present")
        return
    at = src.find(sig)
    src = src[:at] + STATFS_PROTOS + src[at:]
    open(path, "w", encoding="utf-8").write(src)
    print("  statfs.c: wrapper prototypes added")


def fix_selinux_cred_type(root: str) -> None:
    path = os.path.join(root, "security/selinux/hooks.c")
    src = open(path, encoding="utf-8").read()
    fn = src.find("static int susfs_selinux_lsm_setattr(")
    if fn < 0:
        print("  hooks.c: susfs_selinux_lsm_setattr not found (nothing to do)")
        return
    end = src.find("\nstatic ", fn + 10)
    region = src[fn : end if end > 0 else len(src)]
    if "struct cred_security_struct *tsec;" in region:
        print("  hooks.c: cred_security_struct already in use")
        return
    if "struct task_security_struct *tsec;" not in region:
        die("hooks.c: expected `struct task_security_struct *tsec;` in susfs_selinux_lsm_setattr")
    new_region = region.replace(
        "struct task_security_struct *tsec;",
        "struct cred_security_struct *tsec; /* 6.18: selinux_cred() returns cred state */",
        1,
    )
    src = src[:fn] + new_region + src[end if end > 0 else len(src) :]
    open(path, "w", encoding="utf-8").write(src)
    print("  hooks.c: susfs_selinux_lsm_setattr -> cred_security_struct")


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: susfs_618_compile_fixes.py <kernel/common>")
    root = sys.argv[1].rstrip("/")
    print(f"[+] 6.18 SUSFS compile fixes: {root}")
    rewrite_alloc_helpers(root)
    add_missing_prototypes(root)
    add_services_prototypes(root)
    add_statfs_prototypes(root)
    fix_selinux_cred_type(root)
    print("[+] done")


if __name__ == "__main__":
    main()
