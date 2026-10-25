#!/usr/bin/env bash
# BakaSU kernel-side SUSFS compat layer
# Provides weak fallbacks for symbols extern-declared by susfs4ksu's
# 50_add_susfs_in_gki patch, but missing in older BakaSU (dac2d186):
#   my_write_context, my_write_access  (static in selinux_hide.c)
#   my_setprocattr                     (doesn't exist; BakaSU uses ksu_handle_selinux_setprocattr)
#   ksu_setup_preinit_file, ksu_preinit_handle_post_execveat  (no preinit dir)
#
# We drop bakasu_susfs_compat.c directly into kernel/BakaSU/kernel/ (the
# directory symlinked into common/drivers/kernelsu/) and add it to
# kernelsu-objs in Kbuild so it's compiled and linked into vmlinux.
#
# The stubs return simple values so the SUSFS patch's static wrappers
# (handle_sel_write_context, handle_sel_write_access, handle_selinux_setprocattr)
# fall back to original behavior. No SELinux internals needed.

set -eo pipefail

KSU_DIR="${1:-BakaSU}"
KERNEL_ROOT="${KERNEL_ROOT:-$PWD}"

BAKASU_KSU="$KERNEL_ROOT/$KSU_DIR/kernel"
BAKASU_KBUILD="$BAKASU_KSU/Kbuild"

[ -f "$BAKASU_KSU/feature/selinux_hide.c" ] || {
  echo "::error::BakaSU selinux_hide.c not found at $BAKASU_KSU/feature/selinux_hide.c" >&2
  exit 1
}
[ -f "$BAKASU_KBUILD" ] || {
  echo "::error::BakaSU Kbuild not found at $BAKASU_KBUILD" >&2
  exit 1
}

# compat.c: defines all SUSFS-expected symbols that BakaSU lacks
cat > "$BAKASU_KSU/bakasu_susfs_compat.c" <<'COMPAT'
/* BakaSU SUSFS compat: global symbol definitions for SUSFS patch extern refs.
 *
 * BakaSU ships my_write_context/my_write_access as static in selinux_hide.c
 * and lacks my_setprocattr entirely. The SUSFS kernel patch declares these
 * as extern, expecting a root flavor to provide them globally. This file
 * provides the definitions so the link succeeds.
 *
 * Weak fallbacks satisfy the SUSFS patch's externs for older BakaSU revisions;
 * newer BakaSU's real global definitions override them.
 *
 * Stubs return simple values so SUSFS static wrappers fall back to original
 * behavior when CONFIG_KSU_SUSFS is enabled but BakaSU can't provide full
 * SUSFS integration.
 */

#include <linux/fs.h>

struct filename;
struct user_arg_ptr;

/* ------------------------------------------------------------------ */
/* my_write_context / my_write_access                                 */
/*   Provided globally for selinuxfs.c handle_sel_write_context /     */
/*   handle_sel_write_access (added by SUSFS 50_add_susfs patch).     */
/*   These replace sel_write_context/sel_write_access in write_op[].   */
/*   Return -EINVAL so callers fall back to original behavior.         */
/* ------------------------------------------------------------------ */

__weak ssize_t my_write_context(struct file *file, char *buf, size_t size)
{
    return -EINVAL;
}

__weak ssize_t my_write_access(struct file *file, char *buf, size_t size)
{
    return -EINVAL;
}

/* ------------------------------------------------------------------ */
/* my_setprocattr                                                     */
/*   Provided globally for hooks.c handle_selinux_setprocattr         */
/*   (added by SUSFS 50_add_susfs patch).                             */
/*   Replaces selinux_setprocattr in LSM hooks. Return 0 (allow).     */
/* ------------------------------------------------------------------ */

__weak int my_setprocattr(const char *name, void *value, size_t size)
{
    return 0;
}

/* ------------------------------------------------------------------ */
/* Preinit support                                                    */
/*   ksu_setup_preinit_file / ksu_preinit_handle_post_execveat        */
/*   Referenced by fs/exec.c (SUSFS patch). BakaSU has no preinit     */
/*   directory, so we provide minimal stubs here.                     */
/* ------------------------------------------------------------------ */

__weak int ksu_setup_preinit_file(struct filename **filename_ptr,
                           struct user_arg_ptr *argv_user)
{
    return -EINVAL;
}

__weak int ksu_preinit_handle_post_execveat(int *fd, struct filename **filename_ptr,
                                     void *argv_user, void *envp_user,
                                     int *flags, int *retval, int *preinit_fd)
{
    return 0;
}
COMPAT

# Register compat object in Kbuild
if ! grep -q 'bakasu_susfs_compat.o' "$BAKASU_KBUILD"; then
  cat >> "$BAKASU_KBUILD" <<'KBUILD'

# BakaSU SUSFS compat object
obj-y += bakasu_susfs_compat.o
KBUILD
  echo "BakaSU compat: added obj-y to Kbuild"
fi

echo "BakaSU SUSFS compat layer applied (bakasu_susfs_compat.c + Kbuild)"
