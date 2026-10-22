#!/usr/bin/env bash
# BakaSU kernel-side SUSFS compat layer
# Makes selinux_hide symbols global and adds preinit support
# so the susfs4ksu 50_add_susfs_in_gki-android14-6.1.patch extern declarations resolve.
#
# BakaSU (dac2d186) carries my_write_context/my_write_access as `static` in
# kernel/feature/selinux_hide.c and has no my_setprocattr or preinit functions.
# The SUSFS patch at b57ed199 expects these as global symbols:
#   extern ssize_t my_write_context(...)
#   extern ssize_t my_write_access(...)
#   extern int   my_setprocattr(...)
#   extern int   ksu_setup_preinit_file(...)
#   extern int   ksu_preinit_handle_post_execveat(...)
#
# This script applies the equivalent of KernelSU's 10_enable_susfs_for_ksu.patch
# symbol-export changes to BakaSU's source so the link succeeds.

set -eo pipefail

KSU_DIR="${1:-BakaSU}"
KERNEL_ROOT="${KERNEL_ROOT:-$PWD}"
SUSFS4KSU="${SUSFS4KSU:-$KERNEL_ROOT/susfs4ksu}"
KSU_VERSION="${2:-}"
KSU_SUBLEVEL="${3:-}"

BAKASU_KSU="$KERNEL_ROOT/$KSU_DIR/kernel"
BAKASU_SELINUX_HIDE="$BAKASU_KSU/feature/selinux_hide.c"
BAKASU_KSU_H="$BAKASU_KSU/include/ksu.h"

[ -f "$BAKASU_SELINUX_HIDE" ] || {
  echo "::error::BakaSU selinux_hide.c not found at $BAKASU_SELINUX_HIDE" >&2
  exit 1
}

# 1) Remove static from my_write_context / my_write_access / my_setprocattr
#    The SUSFS patch declares these as extern; they must be global to link.
if grep -q '^static ssize_t my_write_context(' "$BAKASU_SELINUX_HIDE"; then
  sed -i 's/^static ssize_t my_write_context(/ssize_t my_write_context(/' "$BAKASU_SELINUX_HIDE"
  echo "BakaSU compat: my_write_context -> global"
fi
if grep -q '^static ssize_t my_write_access(' "$BAKASU_SELINUX_HIDE"; then
  sed -i 's/^static ssize_t my_write_access(/ssize_t my_write_access(/' "$BAKASU_SELINUX_HIDE"
  echo "BakaSU compat: my_write_access -> global"
fi
if grep -q '^static int my_setprocattr(' "$BAKASU_SELINUX_HIDE"; then
  sed -i 's/^static int my_setprocattr(/int my_setprocattr(/' "$BAKASU_SELINUX_HIDE"
  echo "BakaSU compat: my_setprocattr -> global"
fi
if grep -q '^static int __nocfi my_setprocattr(' "$BAKASU_SELINUX_HIDE"; then
  sed -i 's/^static int __nocfi my_setprocattr(/int __nocfi my_setprocattr(/' "$BAKASU_SELINUX_HIDE"
  echo "BakaSU compat: my_setprocattr (__nocfi) -> global"
fi

# 2) Add my_setprocattr wrapper if BakaSU only has ksu_handle_selinux_setprocattr
#    (BakaSU's hook function has the same signature as my_setprocattr).
if ! grep -q '^int my_setprocattr\|^ssize_t my_setprocattr\|^static int my_setprocattr' "$BAKASU_SELINUX_HIDE" 2>/dev/null; then
  if grep -q 'ksu_handle_selinux_setprocattr' "$BAKASU_SELINUX_HIDE"; then
    cat >> "$BAKASU_SELINUX_HIDE" <<'WRAPPER'

/* BakaSU SUSFS compat: my_setprocattr wrapper for SUSFS extern resolution */
int my_setprocattr(const char *name, void *value, size_t size)
{
    return ksu_handle_selinux_setprocattr(name, value, size);
}
WRAPPER
    echo "BakaSU compat: added my_setprocattr wrapper"
  fi
fi

# 3) Add preinit support - BakaSU has no preinit/ directory
mkdir -p "$BAKASU_KSU/preinit"

cat > "$BAKASU_KSU/preinit/preinit.h" <<'HEADER'
#ifndef __KSU_H_PREINIT
#define __KSU_H_PREINIT

#include <linux/types.h>
#include <asm/ptrace.h>

#ifndef KSU_NO_PREINIT
void ksu_preinit_init(void);
void ksu_preinit_exit(void);
bool ksu_preinit_handle_execve(const char __user **filename_user,
                               const char __user *const __user *argv_user,
                               int orig_nr, struct pt_regs *regs, long *ret);
void ksu_preinit_release(void);
bool ksu_preinit_enabled_param(void);

/* SUSFS integration: preinit file setup for execveat hooking */
int ksu_setup_preinit_file(struct filename **filename_ptr, struct user_arg_ptr *argv_user);
int ksu_preinit_handle_post_execveat(int *fd, struct filename **filename_ptr,
                                     void *argv_user, void *envp_user,
                                     int *flags, int *retval, int *preinit_fd);
#else
static inline void ksu_preinit_init(void) {}
static inline void ksu_preinit_exit(void) {}
static inline bool ksu_preinit_handle_execve(const char __user **filename_user,
                                             const char __user *const __user *argv_user, int orig_nr,
                                             struct pt_regs *regs, long *ret) { return false; }
static inline void ksu_preinit_release(void) {}
static inline bool ksu_preinit_enabled_param(void) { return false; }
static inline int ksu_setup_preinit_file(struct filename **filename_ptr, struct user_arg_ptr *argv_user) { return -EINVAL; }
static inline int ksu_preinit_handle_post_execveat(int *fd, struct filename **filename_ptr,
                                                    void *argv_user, void *envp_user,
                                                    int *flags, int *retval, int *preinit_fd) { return -EINVAL; }
#endif
#endif
HEADER

cat > "$BAKASU_KSU/preinit/preinit.c" <<'PREINIT'
#include <linux/err.h>
#include <linux/fcntl.h>
#include <linux/file.h>
#include <linux/fs.h>
#include <linux/moduleparam.h>
#include <linux/namei.h>
#include <linux/sched.h>
#include <linux/shmem_fs.h>
#include <linux/string.h>
#include <linux/uaccess.h>
#include <linux/version.h>

#include "klog.h"
#include "util.h"
#include "hook/syscall_hook.h"
#include "preinit/preinit.h"

#define INIT_PATH "/system/bin/init"

static bool ksu_preinit_enabled = true;
module_param_named(preinit, ksu_preinit_enabled, bool, 0);

static struct file *ksu_preinit_file;

void __init ksu_preinit_init(void)
{
    size_t size = 4096;
    struct file *file;
    loff_t pos = 0;
    ssize_t written;

    if (!ksu_preinit_enabled) {
        pr_info("preinit: disabled\n");
        return;
    }

    file = shmem_file_setup("ksu_preinit", size, 0);
    if (IS_ERR(file)) {
        pr_err("preinit: shmem_file_setup failed: %ld\n", PTR_ERR(file));
        return;
    }

    written = kernel_write(file, INIT_PATH, strlen(INIT_PATH), &pos);
    if (written < 0) {
        pr_err("preinit: write runner failed: %zd\n", written);
        fput(file);
        return;
    }

    ksu_preinit_file = file;
    pr_info("preinit: staged\n");
}

void ksu_preinit_release(void)
{
    struct file *file = xchg(&ksu_preinit_file, NULL);
    if (file) fput(file);
}

void ksu_preinit_exit(void)
{
    ksu_preinit_release();
}

bool ksu_preinit_handle_execve(const char __user **filename_user,
                               const char __user *const __user *argv_user,
                               int orig_nr, struct pt_regs *regs, long *ret)
{
    return false;
}

bool ksu_preinit_enabled_param(void)
{
    return ksu_preinit_enabled;
}

int ksu_setup_preinit_file(struct filename **filename_ptr, struct user_arg_ptr *argv_user)
{
    char fd_path[32] = {0};
    struct file *file;
    struct path path;
    int fd, len;

    if (likely(!READ_ONCE(ksu_preinit_file)))
        return -EINVAL;

    if (strcmp((*filename_ptr)->name, INIT_PATH))
        return -EINVAL;

    file = xchg(&ksu_preinit_file, NULL);
    if (!file)
        return -EINVAL;

    fd = get_unused_fd_flags(O_CLOEXEC);
    if (fd < 0) {
        pr_err("preinit: get fd failed: %d\n", fd);
        fput(file);
        return -EINVAL;
    }
    fd_install(fd, file);

    len = snprintf(fd_path, sizeof(fd_path), "/proc/self/fd/%d", fd);
    if (kern_path(fd_path, LOOKUP_FOLLOW, &path)) {
        pr_err("preinit: %s not reachable\n", fd_path);
        close_fd(fd);
        return -EINVAL;
    }
    path_put(&path);

    memset((void *)(*filename_ptr)->name, 0, strlen((*filename_ptr)->name));
    memcpy((void *)(*filename_ptr)->name, fd_path, strlen(fd_path));

    pr_info("preinit: exec runner via %s\n", fd_path);
    return fd;
}

int ksu_preinit_handle_post_execveat(int *fd, struct filename **filename_ptr,
                                     void *argv_user, void *envp_user,
                                     int *flags, int *retval, int *preinit_fd)
{
    if (*retval && *preinit_fd > 0) {
        close_fd(*preinit_fd);
        memset((void *)(*filename_ptr)->name, 0, strlen((*filename_ptr)->name));
        memcpy((void *)(*filename_ptr)->name, INIT_PATH, strlen(INIT_PATH));
        return -EINVAL;
    }
    return 0;
}
PREINIT

echo "BakaSU SUSFS compat layer applied"
