#!/usr/bin/env bash
# BakaSU kernel-side SUSFS compat layer
#
# susfs4ksu's 50_add_susfs_in_gki patch extern-declares symbols that the root
# implementation is expected to export. Re-checked against BakaSU d5e9e025 and
# susfs4ksu gki-* @ 2026-10-30 (ee155a1a / 6b60a305 / 8930474a):
#
#   my_setprocattr                      NEEDED. BakaSU has no global function of
#       this name at all: selinux_hide.c only has a local `setprocattr_fn
#       my_setprocattr` used for patch_text plus a #define alias. The patch calls
#       it from handle_selinux_setprocattr(), which it wires into
#       LSM_HOOK_INIT(setprocattr, ...), so the reference is live. Delegate to
#       BakaSU's real global ksu_handle_selinux_setprocattr() rather than
#       returning 0, or the hide write silently no-ops while reporting success.
#
#   ksu_setup_preinit_file              FALLBACK. BakaSU does build preinit:
#   ksu_preinit_handle_post_execveat    Kbuild -> tools/code_generation/
#       code_generation.mk -> preinit_runner.mk adds preinit/preinit.o +
#       preinit/blob.o once $(objtree)/usr/include/linux/unistd.h exists (it runs
#       headers_install if not). Those are strong definitions, so these weak ones
#       only take over on the KSU_NO_PREINIT path, where preinit.h supplies
#       static-inline stubs that cannot satisfy the patch's externs.
#
#   my_write_context, my_write_access   NOT NEEDED. BakaSU declares both
#       __maybe_static, which expands to nothing when
#       KSU_COMPAT_HAS_SUSFS_FEATURE_SELINUX_HIDE is set - and BakaSU's own
#       susfs_compat.mk sets it whenever the applied patch puts
#       ksu_selinux_hide_running into security/selinux/hooks.c, which the current
#       patch does. So they are already global. (KernelSU-Next and tiann keep
#       them static and rely on kernel_patches/KernelSU/10_enable_susfs_for_ksu
#       to strip `static` instead - a different route to the same symbol.)
#
# We drop bakasu_susfs_compat.c directly into kernel/BakaSU/kernel/ (the
# directory symlinked into common/drivers/kernelsu/) and add it to
# kernelsu-objs in Kbuild so it's compiled and linked into vmlinux.

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

# The compat source is a real, reviewable file next to this script; copy it in.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPAT_SRC="$SCRIPT_DIR/bakasu_susfs_compat.c"
[ -f "$COMPAT_SRC" ] || {
  echo "::error::compat source missing: $COMPAT_SRC" >&2
  exit 1
}
cp -f "$COMPAT_SRC" "$BAKASU_KSU/bakasu_susfs_compat.c"
echo "BakaSU compat: installed $(basename "$COMPAT_SRC")"

# Register compat object in Kbuild
if ! grep -q 'bakasu_susfs_compat.o' "$BAKASU_KBUILD"; then
  cat >> "$BAKASU_KBUILD" <<'KBUILD'

# BakaSU SUSFS compat object
obj-y += bakasu_susfs_compat.o
KBUILD
  echo "BakaSU compat: added obj-y to Kbuild"
fi

echo "BakaSU SUSFS compat layer applied (bakasu_susfs_compat.c + Kbuild)"
