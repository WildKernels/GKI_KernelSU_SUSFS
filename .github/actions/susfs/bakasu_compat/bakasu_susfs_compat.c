/* BakaSU SUSFS compat: the one symbol BakaSU cannot provide itself.
 *
 * Copied into kernel/BakaSU/kernel/ at build time by apply.sh, next to
 * selinux_hide.c, and registered as obj-y in BakaSU's Kbuild.
 *
 * Unlike my_write_context / my_write_access (globals in BakaSU through
 * __maybe_static) and the preinit pair (compiled in via preinit_runner.mk),
 * BakaSU has no global my_setprocattr: selinux_hide.c only keeps a local
 * `setprocattr_fn my_setprocattr` for patch_text plus a #define alias.
 *
 * The susfs patch calls my_setprocattr() from handle_selinux_setprocattr(),
 * which it wires into LSM_HOOK_INIT(setprocattr, ...), so routing it to
 * BakaSU's real implementation is what makes the setprocattr hide work.
 * Weak, so anything that defines the symbol for real still wins.
 */

#include <linux/fs.h>

struct filename;
struct user_arg_ptr;

/* BakaSU, kernel/feature/selinux_hide.h (>= 4.11 prototype). */
extern int ksu_handle_selinux_setprocattr(const char *name, void *value, size_t size);

__weak int my_setprocattr(const char *name, void *value, size_t size)
{
    return ksu_handle_selinux_setprocattr(name, value, size);
}

/* Preinit: only exists on the KSU_NO_PREINIT path. BakaSU's preinit_runner.mk
 * puts -DKSU_NO_PREINIT into this module's ccflags-y when it cannot find
 * $(objtree)/usr/include/linux/unistd.h, and preinit.h then only offers
 * static-inline stubs that the patch's fs/exec.c externs cannot see. Gated so
 * the normal build - where preinit.o supplies strong definitions - carries no
 * dead stubs at all. */

#ifdef KSU_NO_PREINIT
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
#endif /* KSU_NO_PREINIT */
