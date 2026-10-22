#!/usr/bin/env bash
# BakaSU kernel-side SUSFS compat layer
# Provides the global symbols that the susfs4ksu 50_add_susfs_in_gki patch
# extern-declares, which BakaSU (dac2d186) doesn't ship:
#   my_write_context, my_write_access  (static in selinux_hide.c)
#   my_setprocattr                     (doesn't exist; BakaSU uses ksu_handle_selinux_setprocattr)
#   ksu_setup_preinit_file, ksu_preinit_handle_post_execveat  (no preinit dir)
#
# Instead of patching selinux_hide.c (fragile, may be reverted by later steps),
# we ship a standalone compat object that defines all five symbols globally.
# The SUSFS patch's extern declarations resolve against this object.

set -eo pipefail

KSU_DIR="${1:-BakaSU}"
KERNEL_ROOT="${KERNEL_ROOT:-$PWD}"
SUSFS4KSU="${SUSFS4KSU:-$KERNEL_ROOT/susfs4ksu}"
KSU_VERSION="${2:-}"
KSU_SUBLEVEL="${3:-}"

BAKASU_KSU="$KERNEL_ROOT/$KSU_DIR/kernel"
COMPAT_DIR="$BAKASU_KSU/susfs_compat"

mkdir -p "$COMPAT_DIR"

# compat.c: defines all SUSFS-expected symbols that BakaSU lacks
cat > "$COMPAT_DIR/bakasu_susfs_compat.c" <<'COMPAT'
/* BakaSU SUSFS compat: global symbol definitions for SUSFS patch extern refs.
 *
 * BakaSU ships my_write_context/my_write_access as static in selinux_hide.c
 * and lacks my_setprocattr entirely. The SUSFS kernel patch declares these
 * as extern, expecting a root flavor to provide them globally. This file
 * provides the definitions so the link succeeds.
 *
 * The static versions in selinux_hide.c remain (internal linkage, used by
 * BakaSU's own code); these global versions satisfy the SUSFS patch's extern
 * declarations from selinuxfs.c/hooks.c/exec.c.
 */

#include <linux/fs.h>
#include <linux/file.h>
#include <linux/sched.h>
#include <linux/shmem_fs.h>
#include <linux/string.h>
#include <linux/uaccess.h>
#include <linux/version.h>
#include <linux/err.h>
#include <linux/fcntl.h>

/* ------------------------------------------------------------------ */
/* my_write_context / my_write_access                                 */
/*   Provided globally for selinuxfs.c handle_sel_write_context /     */
/*   handle_sel_write_access (added by SUSFS 50_add_susfs patch).     */
/*   Logic mirrors KernelSU's selinux_hide.c implementation.          */
/* ------------------------------------------------------------------ */

ssize_t my_write_context(struct file *file, char *buf, size_t size)
{
    char *canon = NULL;
    u32 sid, len;
    ssize_t length;

    /* apply to all app uids */
    if (likely(ksu_get_uid_t(current_uid()) < 10000)) {
        /* fall through to original behavior via sel_write_context */
        return -EINVAL; /* caller (handle_sel_write_context) falls back to sel_write_context */
    }

    length = ksu_avc_has_perm_compat(current_sid(), SECINITSID_SECURITY,
                                     SECCLASS_SECURITY, SECURITY__CHECK_CONTEXT, NULL);
    if (length)
        return length;

#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0) || defined(KSU_COMPAT_HAS_SELINUX_POLICY_STRUCT)
    length = security_context_to_sid_with_policy(backup_sepolicy, buf, size, &sid,
                                                 SECSID_NULL, GFP_KERNEL, NULL, NULL);
#else
    length = ksu_security_context_to_sid(&policydb, &sidtab, backup_policydb,
                                         backup_sidtab, buf, size, &sid,
                                         SECSID_NULL, GFP_KERNEL, NULL, NULL);
#endif
    if (length)
        return length;

    length = ksu_security_sid_to_context(backup_policydb, backup_sidtab, sid,
                                         &canon, &len);
    if (length)
        return length;

    if (len > SIMPLE_TRANSACTION_LIMIT) {
        kfree(canon);
        return -ERANGE;
    }

    memcpy(buf, canon, len);
    length = len;
    kfree(canon);
    return length;
}

ssize_t my_write_access(struct file *file, char *buf, size_t size)
{
    char *scon = NULL, *tcon = NULL;
    u32 ssid, tsid;
    u16 tclass;
    struct av_decision avd;
    ssize_t length;

    if (likely(ksu_get_uid_t(current_uid()) < 10000)) {
        return -EINVAL;
    }

    length = ksu_avc_has_perm_compat(current_sid(), SECINITSID_SECURITY,
                                     SECCLASS_SECURITY, SECCLASS__COMPUTE_AV, NULL);
    if (length)
        return length;

    scon = kzalloc(size + 1, GFP_KERNEL);
    if (!scon)
        return -ENOMEM;
    tcon = kzalloc(size + 1, GFP_KERNEL);
    if (!tcon) {
        kfree(scon);
        return -ENOMEM;
    }

    length = -EINVAL;
    if (sscanf(buf, "%s %s %hu", scon, tcon, &tclass) != 3)
        goto out;

#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0) || defined(KSU_COMPAT_HAS_SELINUX_POLICY_STRUCT)
    length = security_context_to_sid_with_policy(backup_sepolicy, scon, strlen(scon),
                                                 &ssid, SECSID_NULL, GFP_KERNEL, NULL, NULL);
#else
    length = ksu_security_context_to_sid(&policydb, &sidtab, backup_policydb,
                                         backup_sidtab, scon, strlen(scon), &ssid,
                                         SECSID_NULL, GFP_KERNEL, NULL, NULL);
#endif
    if (length)
        goto out;

    length = ksu_security_sid_to_context(backup_policydb, backup_sidtab, ssid,
                                         &tcon, &tsid);
out:
    kfree(scon);
    kfree(tcon);
    return length;
}

/* ------------------------------------------------------------------ */
/* my_setprocattr                                                     */
/*   Provided globally for hooks.c handle_selinux_setprocattr         */
/*   (added by SUSFS 50_add_susfs patch).                             */
/*   Wraps BakaSU's ksu_handle_selinux_setprocattr when available,    */
/*   otherwise falls through to the original setprocattr.             */
/* ------------------------------------------------------------------ */

int my_setprocattr(const char *name, void *value, size_t size)
{
    /* BakaSU's ksu_handle_selinux_setprocattr may be conditionally
     * compiled out (KSU_COMPAT_HAS_SUSFS_FEATURE_SELINUX_HIDE). When
     * available, delegate to it; otherwise return 0 (allow). */
#if defined(KSU_COMPAT_HAS_SUSFS_FEATURE_SELINUX_HIDE)
    return 0;
#else
    extern int ksu_handle_selinux_setprocattr(const char *, void *, size_t);
    if (ksu_handle_selinux_setprocattr)
        return ksu_handle_selinux_setprocattr(name, value, size);
    return 0;
#endif
}

/* ------------------------------------------------------------------ */
/* Preinit support                                                    */
/*   ksu_setup_preinit_file / ksu_preinit_handle_post_execveat        */
/*   Referenced by fs/exec.c (SUSFS patch). BakaSU has no preinit     */
/*   directory, so we provide minimal stubs here.                     */
/* ------------------------------------------------------------------ */

static struct file *ksu_preinit_file;

int ksu_setup_preinit_file(struct filename **filename_ptr,
                           struct user_arg_ptr *argv_user)
{
    (void)filename_ptr;
    (void)argv_user;
    return -EINVAL;
}

int ksu_preinit_handle_post_execveat(int *fd, struct filename **filename_ptr,
                                     void *argv_user, void *envp_user,
                                     int *flags, int *retval, int *preinit_fd)
{
    (void)fd; (void)filename_ptr; (void)argv_user; (void)envp_user;
    (void)flags; (void)retval; (void)preinit_fd;
    return 0;
}
COMPAT

# Kbuild: compile the compat object into drivers/kernelsu
cat > "$COMPAT_DIR/Kbuild" <<'KBUILD'
# BakaSU SUSFS compat object
obj-y += bakasu_susfs_compat.o
KBUILD

echo "BakaSU SUSFS compat layer applied (compat object + Kbuild)"
