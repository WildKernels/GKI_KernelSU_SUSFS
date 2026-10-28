#!/usr/bin/env python3
"""Rewrite fs/susfs.c idmap calls for kernels that predate i_user_ns().

susfs4ksu's fs/susfs.c is written against the newer helper:

    i_uid_into_mnt(i_user_ns(&fi->inode), &fi->inode)
    i_uid_into_mnt(i_user_ns(inode), inode)

Kernels before ~6.3 pass the mount namespace explicitly and have no i_user_ns(),
so they fail with:

    error: implicit declaration of function 'i_user_ns' [-Werror]
    error: incompatible integer to pointer conversion passing 'int' to
           parameter of type 'struct user_namespace *' [-Werror]
    make[1]: *** [...: fs/susfs.o] Error 1

Rewrite both call sites to &init_user_ns, which is what the pre-i_user_ns API
expects. Idempotent; asserts nothing still references i_user_ns.

Done in Python rather than sed on purpose: `&` in a sed replacement expands to
the whole match, which mangled the file when the rewrite was first attempted.

Usage: susfs_idmap_compat.py <path/to/fs/susfs.c>
"""
import pathlib
import re
import sys

CALL = re.compile(r'i_uid_into_mnt\(i_user_ns\(([^()]*)\),')


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: susfs_idmap_compat.py <fs/susfs.c>')
    path = pathlib.Path(sys.argv[1])
    src = path.read_text()
    if 'i_user_ns' not in src:
        print('fs/susfs.c has no i_user_ns reference - nothing to do')
        return 0
    out, n = CALL.subn(r'i_uid_into_mnt(&init_user_ns,', src)
    if n == 0:
        raise SystemExit('ERROR: i_user_ns present but the expected call shape was not found')
    path.write_text(out)
    left = out.count('i_user_ns')
    if left:
        raise SystemExit(f'ERROR: {left} i_user_ns reference(s) still present after rewrite')
    print(f'rewrote {n} i_uid_into_mnt(i_user_ns(...)) call(s) to &init_user_ns')
    return 0


if __name__ == '__main__':
    sys.exit(main())
