#!/usr/bin/env python3
"""Generate the scoped-storage Unicode path-filter patches, one per kernel family.

    .github/scripts/gen_unicode_scoped.py [/path/to/kernel-X-trees...]

Writes .github/patches/unicode-scoped/unicode_scoped_<version>.patch. Each patch adds
include/linux/ucpath.h and calls uc_path_check() from the syscall bodies the bypass
goes through: openat, openat2, faccessat2 and newfstatat.

The check cannot live in filename_lookup(): it resolves the stripped path with
kern_path(), which re-enters filename_lookup() - the syscall bodies are the lowest
level that still sees the user's original string.

Kept ASCII-only in the patch text so it applies identically regardless of locale.
"""

import difflib
import re
import sys
from pathlib import Path

HEADER = r'''/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _LINUX_UCPATH_H
#define _LINUX_UCPATH_H

#include <linux/cred.h>
#include <linux/dcache.h>
#include <linux/err.h>
#include <linux/fs.h>
#include <linux/kernel.h>
#include <linux/limits.h>
#include <linux/namei.h>
#include <linux/slab.h>
#include <linux/string.h>
#include <linux/uaccess.h>

/*
 * Scoped-storage guard against invisible-character path rewriting.
 *
 * /storage/emulated is a FUSE mount, so names are compared as byte strings: a path
 * carrying an invisible formatting character looks identical to the protected one
 * while comparing differently. That is how /sdcard/Android/data gets reached from an
 * app that has no business there. This strips only characters that render as
 * nothing, resolves the stripped path, and refuses when it lands in Android/data or
 * Android/obb for a caller that does not own it.
 *
 * Visible characters are never altered. U+200C ZWNJ, U+200D ZWJ, U+FE00-U+FE0F
 * variation selectors, the Hangul fillers and the Khmer/Mongolian variation
 * selectors are deliberately absent from the list below: they render, or a script
 * requires them, so stripping them would rename files rather than expose a trick.
 */

/* bytes in a codepoint that renders as nothing, 0 for everything else */
static inline int uc_invisible(const unsigned char *s)
{
	if (s[0] == 0xC2 && s[1] == 0xAD)		/* U+00AD soft hyphen */
		return 2;
	if (s[0] == 0xD8 && s[1] == 0x9C)		/* U+061C Arabic letter mark */
		return 2;
	if (s[0] == 0xE1 && s[1] == 0xA0 && s[2] == 0x8E)
		return 3;				/* U+180E Mongolian vowel separator */
	if (s[0] == 0xE2 && s[1] == 0x80) {
		if (s[2] == 0x8B)			/* U+200B zero width space */
			return 3;
		if (s[2] == 0x8E || s[2] == 0x8F)	/* U+200E LRM, U+200F RLM */
			return 3;
		if (s[2] >= 0xAA && s[2] <= 0xAE)	/* U+202A-U+202E bidi overrides */
			return 3;
	}
	if (s[0] == 0xE2 && s[1] == 0x81 && s[2] >= 0xA0 && s[2] <= 0xAF)
		return 3;				/* U+2060-U+206F WJ, isolates */
	if (s[0] == 0xEF && s[1] == 0xBB && s[2] == 0xBF)
		return 3;				/* U+FEFF BOM / ZWNBSP */
	return 0;
}

/* strip those characters; returns how many were removed */
static inline int uc_strip(const char *in, char *out, int outsz)
{
	const unsigned char *r = (const unsigned char *)in;
	int w = 0, stripped = 0, len, drop;

	while (*r && w < outsz - 1) {
		drop = uc_invisible(r);
		if (drop) {
			r += drop;
			stripped++;
			continue;
		}
		if (*r < 0x80)
			len = 1;
		else if (*r < 0xE0)
			len = 2;
		else if (*r < 0xF0)
			len = 3;
		else
			len = 4;
		while (len-- && *r && w < outsz - 1)
			out[w++] = *r++;
	}
	out[w] = '\0';
	return stripped;
}

/*
 * 0 to allow, negative errno to refuse. Nothing is logged: a path in dmesg is one
 * of the first things a detector reads.
 */
static inline int uc_path_check(const char __user *ufname)
{
	char *clean, *resolved, *p;
	struct path path;
	unsigned int user, other;
	kuid_t uid = current_uid();
	int ret = 0;

	if (!ufname)
		return 0;
	/* system, root and the zygote-isolated range are untouched */
	if (uid.val % 100000 < 2000)
		return 0;

	clean = kmalloc(PATH_MAX, GFP_KERNEL);
	resolved = kmalloc(PATH_MAX, GFP_KERNEL);
	if (!clean || !resolved) {
		kfree(clean);
		kfree(resolved);
		return 0;
	}

	if (strncpy_from_user(clean, ufname, PATH_MAX) <= 0)
		goto out;
	clean[PATH_MAX - 1] = '\0';

	if (!uc_strip(clean, resolved, PATH_MAX))
		goto out;			/* nothing invisible: stock behaviour */
	memcpy(clean, resolved, PATH_MAX);

	if (kern_path(clean, LOOKUP_FOLLOW, &path))
		goto out;
	p = d_path(&path, resolved, PATH_MAX);
	if (IS_ERR(p)) {
		path_put(&path);
		goto out;
	}

	user = uid.val / 100000;
	if (strncmp(p, "/storage/emulated/", 18) == 0) {
		char own[64];
		int n = scnprintf(own, sizeof(own), "/storage/emulated/%u/Android", user);

		if (strncmp(p, own, n) == 0)
			ret = -ENOENT;		/* an app's own Android tree */
		else if (sscanf(p + 18, "%u", &other) == 1 && other != user)
			ret = -EACCES;		/* another user's storage */
	}
	path_put(&path);
out:
	kfree(clean);
	kfree(resolved);
	return ret;
}

#endif /* _LINUX_UCPATH_H */
'''

CALL = "\tint uc_err = uc_path_check(filename);\n\n\tif (uc_err)\n\t\treturn uc_err;\n"
INC = "#include <linux/ucpath.h>\n"

CALLS = [("openat", "fs/open.c"), ("openat2", "fs/open.c"),
         ("faccessat2", "fs/open.c"), ("newfstatat", "fs/stat.c")]


def add_call(src, fn):
    m = re.search(r"(?m)^SYSCALL_DEFINE\d\(" + fn + r",", src)
    if not m:
        return src, False
    at = src.index("{\n", m.end()) + 2
    return src[:at] + CALL + src[at:], True


def main():
    trees = sys.argv[1:] or [str(p) for p in sorted(Path("/home/james/Projects").glob("kernel-*-lts"))]
    out_dir = Path(__file__).resolve().parents[1] / "patches/unicode-scoped"
    out_dir.mkdir(parents=True, exist_ok=True)

    for tree in trees:
        root = Path(tree) / "common"
        if not (root / "fs/open.c").is_file():
            print(f"{Path(tree).name}: no common/fs/open.c - skipped")
            continue
        # one cumulative diff per FILE: three syscalls live in fs/open.c, and emitting
        # one diff per syscall repeated the include hunk three times, so only the first
        # of them could ever apply.
        chunks = []
        by_file = {}
        for fn, rel in CALLS:
            by_file.setdefault(rel, []).append(fn)
        for rel, fns in by_file.items():
            f = root / rel
            orig = f.read_text()
            work = orig
            for fn in fns:
                work, ok = add_call(work, fn)
                if not ok:
                    print(f"  ERROR: {rel}: SYSCALL_DEFINE4({fn}) not found")
                    return 1
            if INC not in work:
                work = work.replace("#include <linux/", INC + "#include <linux/", 1)
            chunks.append("".join(difflib.unified_diff(
                orig.splitlines(True), work.splitlines(True), f"a/{rel}", f"b/{rel}", n=3)))

        head = ("diff --git a/include/linux/ucpath.h b/include/linux/ucpath.h\n"
                "new file mode 100644\n"
                + "".join(difflib.unified_diff([], HEADER.splitlines(True),
                                              "/dev/null", "b/include/linux/ucpath.h", n=3)))
        ver = Path(tree).name.replace("kernel-", "").replace("-lts", "")
        dst = out_dir / f"unicode_scoped_{ver}.patch"
        dst.write_text(head + "".join(chunks))
        print(f"{Path(tree).name:16s} -> {dst.name} ({dst.stat().st_size} bytes, 4 hooks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
