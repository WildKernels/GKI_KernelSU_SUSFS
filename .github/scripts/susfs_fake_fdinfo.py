#!/usr/bin/env python3
"""Reshape fs/notify/fdinfo.c so the susfs4ksu 50_add_susfs_in_gki patch applies.

The 5.10/5.15 SUSFS patches carry a hunk whose context is the *post-fake-patch*
form of inotify_fdinfo():

        if (inode) {
                seq_printf(m, "inotify wd:%x ino:%lx sdev:%x mask:%x ignored_mask:0 ",
                           inode_mark->wd, inode->i_ino, inode->i_sb->s_dev,
                           inotify_mark_user_mask(mark));

Android GKI sources at those sublevels still carry the upstream form: the
IN_ALL_EVENTS comment block, a local `u32 mask` variable, `ignored_mask:%x`,
and `mask, mark->ignored_mask` as the last two arguments. While that text is
present, the hunk's trailing context cannot match and patch reports
"Hunk #4 FAILED".

Earlier revisions of this transformation used a brace-delimited perl
substitution (`s{(if \\(inode\\) {\\n)...}{$1}gs`). Perl balances braces inside
{} delimiters, so the literal `{` in `if (inode) {` desynchronised the parser
and the substitution died before touching the file - leaving the comment and
the `u32 mask` line in place and the SUSFS hunk rejecting on every run.

This script performs the same reshape with explicit, anchored regexes and then
verifies the file really is in the shape the patch expects, so CI fails loudly
instead of silently shipping a half-applied fake patch.

Usage: susfs_fake_fdinfo.py <path-to-fdinfo.c>
"""

import re
import sys

HELPER = """static inline u32 inotify_mark_user_mask(struct fsnotify_mark *mark)
{
\treturn mark->mask & IN_ALL_EVENTS;
}
"""

# `if (inode) {` followed by the IN_ALL_EVENTS comment block inside
# inotify_fdinfo(). Only the first occurrence (inotify) is in scope.
COMMENT_RE = re.compile(
    r"(if \(inode\) \{\n)[ \t]*/\*.*?\n[ \t]*\*/[ \t]*\n",
    re.S,
)

# The local mask variable that becomes dead once the helper is used.
MASK_DECL_RE = re.compile(r"^[ \t]*u32 mask = mark->mask & IN_ALL_EVENTS;\n", re.M)

# The inotify seq_printf call, in its upstream form.
INOTIFY_CALL_RE = re.compile(
    r"(?P<ind>[ \t]*)seq_printf\(m, \"inotify wd:%x ino:%lx sdev:%x mask:%x "
    r"ignored_mask:%x \",\n"
    r"(?P<cont>[ \t]*)inode_mark->wd, inode->i_ino, inode->i_sb->s_dev,\n"
    r"[ \t]*mask, mark->ignored_mask\);",
)

# The same call in the form the SUSFS hunk expects (used for validation and
# for idempotent re-runs).
TARGET_CALL_RE = re.compile(
    r"seq_printf\(m, \"inotify wd:%x ino:%lx sdev:%x mask:%x ignored_mask:0 \",\n"
    r"[ \t]*inode_mark->wd, inode->i_ino, inode->i_sb->s_dev,\n"
    r"[ \t]*inotify_mark_user_mask\(mark\)\);",
)

FDINFO_DECL_RE = re.compile(
    r"^static void inotify_fdinfo\(struct seq_file \*m, struct fsnotify_mark \*mark\)$",
    re.M,
)
HELPER_DECL_RE = re.compile(
    r"^static inline u32 inotify_mark_user_mask\(struct fsnotify_mark \*mark\)$", re.M
)


def shape_ok(src):
    """True when the file already matches what the SUSFS hunk expects."""
    return bool(TARGET_CALL_RE.search(src)) and not MASK_DECL_RE.search(src)


def main(path):
    with open(path) as fh:
        src = fh.read()

    if not FDINFO_DECL_RE.search(src):
        sys.exit("%s: inotify_fdinfo() not found - refusing to touch it" % path)

    if shape_ok(src):
        print("%s: already in SUSFS shape, nothing to do" % path)
        return

    out = src
    notes = []

    # 1. Drop the upstream IN_ALL_EVENTS comment block inside inotify_fdinfo().
    out, n = COMMENT_RE.subn(r"\1", out, count=1)
    if n:
        notes.append("removed IN_ALL_EVENTS comment")

    # 2. Drop the now-unused local mask variable.
    out, n = MASK_DECL_RE.subn("", out, count=1)
    if n:
        notes.append("removed u32 mask declaration")

    # 3. Rewrite the inotify seq_printf: ignored_mask always prints as 0 and
    #    the printed mask comes from the helper the patch's context expects.
    def _call(m):
        return (
            '%sseq_printf(m, "inotify wd:%%x ino:%%lx sdev:%%x mask:%%x '
            'ignored_mask:0 ",\n'
            "%sinode_mark->wd, inode->i_ino, inode->i_sb->s_dev,\n"
            "%sinotify_mark_user_mask(mark));"
            % (m.group("ind"), m.group("cont"), m.group("cont"))
        )

    out, n = INOTIFY_CALL_RE.subn(_call, out, count=1)
    if n:
        notes.append("rewrote inotify seq_printf")

    # 4. Provide the helper definition the patch's context assumes exists.
    if not HELPER_DECL_RE.search(out):
        out = FDINFO_DECL_RE.sub(lambda m: HELPER + "\n" + m.group(0), out, count=1)
        notes.append("inserted inotify_mark_user_mask helper")

    # 5. Never write a file that still fails the patch's expectations.
    if not shape_ok(out):
        sys.exit(
            "%s: could not reshape fdinfo.c (applied: %s); refusing to continue"
            % (path, "; ".join(notes) or "nothing")
        )

    with open(path, "w") as fh:
        fh.write(out)
    print("%s: %s" % (path, "; ".join(notes)))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
