#!/usr/bin/env bash
# close_fd compat fix for KernelSU preinit on kernels < 5.15
#
# The SUSFS 10_enable_susfs_for_ksu.patch rewrites ksu_close_fd(fd) ->
# close_fd(fd) in kernel/preinit/preinit.c. close_fd() is a public kernel
# symbol only on Linux 5.15+; on 5.10 it is undeclared (only __close_fd
# exists), causing:
#
#   preinit.c:130:9: error: implicit declaration of function 'close_fd'
#
# Fix: after the SUSFS patch is applied, restore ksu_close_fd(fd) for
# kernels < 5.15. KernelSU already defines ksu_close_fd via ksyscall(close, fd)
# in kernel/include/util.h.
set -euo pipefail

KERNEL_DIR="${1:-${{ github.workspace }}/kernel}"

for d in common/drivers/kernelsu drivers/kernelsu; do
  F="$KERNEL_DIR/$d/preinit/preinit.c"
  if [ -f "$F" ] && grep -qE '^[[:space:]]*close_fd\(fd\);' "$F"; then
    sed -i 's/^\([[:space:]]*\)close_fd(fd);/\1ksu_close_fd(fd);/' "$F"
    echo "Preinit close_fd fix: restored ksu_close_fd(fd) in $F (kernel < 5.15)"
  else
    echo "No bare close_fd(fd) in $F; skipping"
  fi
done
