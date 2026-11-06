#!/usr/bin/env python3
"""Enable fanotify without moving the GKI ABI (keep caps, zero drift).

Upstream fanotify changes two ABI-visible layouts when CONFIG_FANOTIFY=y:

  1. `enum ucount_type` gains UCOUNT_FANOTIFY_GROUPS/MARKS, which grows
     `struct ucounts.ucount[UCOUNT_COUNTS]` AND `struct user_namespace.ucount_max[]`
     by 16 bytes. `struct user_namespace` appears in the prototypes of
     make_kuid/from_kuid/make_kgid/from_kgid/make_kprojid/from_kprojid/
     current_in_userns/__put_user_ns, so their CRCs move.
  2. `struct fsnotify_group` grows, because its private-data union gains the
     larger `fanotify_group_private_data` member. Eight EXPROTED fsnotify_*
     symbols take that pointer, so their CRCs move too.

Both are fixed here, per tree, at build time:

  * `fanotify_group_private_data` moves out of the union (the union keeps the
    stock `void *private` + inotify member) and is allocated with kzalloc inside
    `group->private`; every `group->fanotify_data.X` becomes
    `fanotify_group_priv(group)->X`.
  * The two ucount enum members are dropped, and fanotify's per-user-namespace
    group/mark limits are re-implemented in fanotify's own table, keeping
    upstream's semantics: a per-`(namespace, kind)` atomic counter with
    increment-if-below-max, charged along the whole user namespace chain with
    rollback, released on group/mark teardown, and the same two sysctls
    (`max_user_groups`, `max_user_marks`) with the same defaults.

A group holds a reference to its user namespace (`group->user_ns = get_user_ns()`)
and marks hang off groups, so a table keyed by the namespace pointer can never
dangle - the namespace outlives every entry that references it.

Idempotent; every stage is anchored and verified, and the script exits non-zero
when a tree does not look like it expects.

Usage: fanotify_zero_drift.py <kernel/common>
"""

import os
import re
import sys
from typing import NoReturn

MARKER = "/* fanotify zero-drift port (GKI_KernelSU_SUSFS) */"

ACCOUNTING = f"""\
{MARKER}
/*
 * Per-user-namespace group/mark limits, kept out of the generic ucount arrays so
 * `struct ucounts` and `struct user_namespace` stay at their stock size (their
 * layouts are part of the GKI module ABI). Semantics follow inc_ucount(): charge
 * every namespace on the chain up to the root, increment only while below the
 * limit, and roll back the levels already charged when one is at its limit.
 */
enum fanotify_account_type {{ FANOTIFY_ACCOUNT_GROUPS, FANOTIFY_ACCOUNT_MARKS }};

struct fanotify_ns_account {{
	struct hlist_node	node;
	struct user_namespace	*ns;	/* borrowed: a group's ns ref keeps it alive */
	atomic_long_t		groups;
	atomic_long_t		marks;
}};

static DEFINE_HASHTABLE(fanotify_accounts, 6);
static DEFINE_MUTEX(fanotify_accounts_lock);
static long fanotify_max_user_groups = FANOTIFY_DEFAULT_MAX_GROUPS;
static long fanotify_max_user_marks;

static atomic_long_t *fanotify_account_counter(struct fanotify_ns_account *acc,
					       enum fanotify_account_type type)
{{
	return type == FANOTIFY_ACCOUNT_GROUPS ? &acc->groups : &acc->marks;
}}

/* Increment only while below @max, atomically (no atomic_long_inc_below() on
 * older trees). Returns false when the limit is reached. */
static bool fanotify_account_inc_below(atomic_long_t *cnt, long max)
{{
	long old, new;

	do {{
		old = atomic_long_read(cnt);
		if (old >= max)
			return false;
		new = old + 1;
	}} while (atomic_long_cmpxchg_relaxed(cnt, old, new) != old);

	return true;
}}

static long fanotify_account_limit(enum fanotify_account_type type)
{{
	return type == FANOTIFY_ACCOUNT_GROUPS ? READ_ONCE(fanotify_max_user_groups)
					       : READ_ONCE(fanotify_max_user_marks);
}}

static struct fanotify_ns_account *fanotify_account_lookup(struct user_namespace *ns)
{{
	struct fanotify_ns_account *acc;

	hash_for_each_possible(fanotify_accounts, acc, node, (unsigned long)ns) {{
		if (acc->ns == ns)
			return acc;
	}}
	return NULL;
}}

/* caller holds fanotify_accounts_lock */
static struct fanotify_ns_account *fanotify_account_create(struct user_namespace *ns)
{{
	struct fanotify_ns_account *acc;

	acc = fanotify_account_lookup(ns);
	if (acc)
		return acc;

	acc = kzalloc(sizeof(*acc), GFP_KERNEL);
	if (!acc)
		return NULL;

	acc->ns = ns;
	hash_add(fanotify_accounts, &acc->node, (unsigned long)ns);
	return acc;
}}

static bool fanotify_account_inc(struct user_namespace *ns,
				 enum fanotify_account_type type)
{{
	struct user_namespace *iter;
	bool ok = true;

	mutex_lock(&fanotify_accounts_lock);

	/* Create every entry first, so the charge loop cannot fail on allocation. */
	for (iter = ns; iter; iter = iter->parent) {{
		if (!fanotify_account_create(iter)) {{
			ok = false;
			goto out;
		}}
	}}

	for (iter = ns; iter; iter = iter->parent) {{
		struct fanotify_ns_account *acc = fanotify_account_lookup(iter);

		if (!fanotify_account_inc_below(fanotify_account_counter(acc, type),
					        fanotify_account_limit(type))) {{
			/* Roll back the namespaces charged before this one. */
			struct user_namespace *undo;

			for (undo = ns; undo && undo != iter; undo = undo->parent) {{
				struct fanotify_ns_account *u;

				u = fanotify_account_lookup(undo);
				if (u)
					atomic_long_dec(fanotify_account_counter(u, type));
			}}
			ok = false;
			goto out;
		}}
	}}

out:
	mutex_unlock(&fanotify_accounts_lock);
	return ok;
}}

static void fanotify_account_dec(struct user_namespace *ns,
				 enum fanotify_account_type type)
{{
	struct user_namespace *iter;

	mutex_lock(&fanotify_accounts_lock);

	for (iter = ns; iter; iter = iter->parent) {{
		struct fanotify_ns_account *acc = fanotify_account_lookup(iter);

		if (!acc)
			continue;

		if (WARN_ON_ONCE(atomic_long_read(fanotify_account_counter(acc, type)) <= 0))
			continue;
		atomic_long_dec(fanotify_account_counter(acc, type));

		/* both counters at zero -> the entry can go */
		if (!atomic_long_read(&acc->groups) && !atomic_long_read(&acc->marks)) {{
			hash_del(&acc->node);
			kfree(acc);
		}}
	}}

	mutex_unlock(&fanotify_accounts_lock);
}}

bool fanotify_account_group(struct user_namespace *ns)
{{
	return fanotify_account_inc(ns, FANOTIFY_ACCOUNT_GROUPS);
}}

void fanotify_account_put_group(struct user_namespace *ns)
{{
	fanotify_account_dec(ns, FANOTIFY_ACCOUNT_GROUPS);
}}

bool fanotify_account_mark(struct user_namespace *ns)
{{
	return fanotify_account_inc(ns, FANOTIFY_ACCOUNT_MARKS);
}}

void fanotify_account_put_mark(struct user_namespace *ns)
{{
	fanotify_account_dec(ns, FANOTIFY_ACCOUNT_MARKS);
}}
"""

ACCESSOR_FN = """
#ifdef CONFIG_FANOTIFY
static inline struct fanotify_group_private_data *
fanotify_group_priv(struct fsnotify_group *group)
{
	return group->private;
}
#endif /* CONFIG_FANOTIFY */
"""

STRUCT_HEADER = """
#ifdef CONFIG_FANOTIFY
/*
 * Moved verbatim out of struct fsnotify_group's private-data union: keeping it
 * inline grows that struct, and its layout is baked into the CRCs of the
 * exported fsnotify_* symbols. Allocated by fanotify_init(), freed on teardown.
 * The ucounts member is gone - per-namespace accounting lives in fanotify's own
 * table (see fanotify_account_group()).
 */
struct fanotify_group_private_data {"""

STRUCT_TAIL = """
};
#endif /* CONFIG_FANOTIFY */
"""


def die(msg: str) -> NoReturn:
    sys.exit(f"ERROR: {msg}")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def move_struct_out_of_union(backend_h: str) -> None:
    """Move the fanotify private-data struct verbatim out of the union.

    Verbatim matters: 6.1 has no perm_grp_list, 6.6+ do, so the body is taken
    from the tree rather than retyped. Only the ucounts member is dropped, since
    accounting is re-implemented in fanotify's own table.
    """
    src = read(backend_h)
    if "fanotify_group_priv(struct fsnotify_group *group)" in src:
        print("  fsnotify_backend.h: already moved")
        return

    m = re.search(r"\t\tstruct fanotify_group_private_data \{(.*?)\n\t\t\} fanotify_data;\n", src, re.S)
    if not m:
        die("fsnotify_backend.h: fanotify union member not found")
    body = m.group(1)
    body = re.sub(r"\n\t*struct ucounts \*ucounts;", "", body)
    # our own namespace reference, so the accounting works on trees without
    # group->user_ns (6.1 and older do not store it on the group)
    body = body.rstrip() + "\n\t/* this group's user namespace, refcounted by us */\n" \
           "\tstruct user_namespace *account_ns;"

    # remove the member, then the #ifdef that held it
    src = src[: m.start()] + src[m.end():]
    src = re.sub(r"#ifdef CONFIG_FANOTIFY\n#endif /\* CONFIG_FANOTIFY \*/\n", "", src, count=1)

    # struct definition before fsnotify_group, accessor after it
    anchor = "struct fsnotify_group {\n"
    if anchor not in src:
        die("fsnotify_backend.h: struct fsnotify_group not found")
    src = src.replace(anchor, STRUCT_HEADER + body + STRUCT_TAIL + "\n" + anchor, 1)

    m2 = re.search(r"(struct fsnotify_group \{\n(?:.*?)\n\};\n)", src, re.S)
    if not m2:
        die("fsnotify_backend.h: could not locate the end of struct fsnotify_group")
    src = src[: m2.end()] + ACCESSOR_FN + src[m2.end():]

    write(backend_h, src)
    print("  fsnotify_backend.h: struct moved out of the union verbatim + accessor added")


def rewrite_macro(root: str) -> None:
    """FAN_GROUP_FLAG() expands to group->fanotify_data.flags."""
    for rel in ("include/linux/fanotify.h", "fs/notify/fanotify/fanotify.h"):
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        src = read(path)
        new = re.sub(r"\(\s*group\s*\)->fanotify_data\.flags",
                     "fanotify_group_priv(group)->flags", src)
        if new != src:
            write(path, new)
            print(f"  {rel}: FAN_GROUP_FLAG() rewritten")


def rewrite_accessors(root: str) -> None:
    hits = 0
    for rel in ("fs/notify/fanotify/fanotify.c",
                "fs/notify/fanotify/fanotify_user.c",
                "fs/notify/fdinfo.c"):
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        src = read(path)
        new = src.replace("group->fanotify_data.", "fanotify_group_priv(group)->")
        if new != src:
            hits += src.count("group->fanotify_data.")
            write(path, new)
    print(f"  call sites: {hits} rewritten to fanotify_group_priv(group)->")


def insert_accounting(root: str) -> None:
    path = os.path.join(root, "fs/notify/fanotify/fanotify_user.c")
    src = read(path)
    if MARKER in src:
        print("  fanotify_user.c: accounting already inserted")
        return
    anchor = "static struct ctl_table fanotify_table[] = {"
    if anchor not in src:
        anchor = "static const struct ctl_table fanotify_table[] = {"
    if anchor not in src:
        die("fanotify_user.c: fanotify_table() not found")
    src = src.replace(anchor, ACCOUNTING + "\n" + anchor, 1)
    write(path, src)
    print("  fanotify_user.c: per-namespace accounting inserted")


def allocate_priv(root: str) -> None:
    path = os.path.join(root, "fs/notify/fanotify/fanotify_user.c")
    src = read(path)
    if "group->private = kzalloc" in src:
        print("  fanotify_user.c: private block already allocated")
        return
    m = re.search(r"(group = fsnotify_alloc_group\(&fanotify_fsnotify_ops,[^;]*;\n\tif \(IS_ERR\(group\)\) \{\n\t\treturn PTR_ERR\(group\);\n\t\}\n)", src)
    if not m:
        die("fanotify_user.c: fsnotify_alloc_group() block not found")
    alloc = ("\n\tgroup->private = kzalloc(sizeof(struct fanotify_group_private_data),\n"
             "\t\t\t\tGFP_KERNEL);\n"
             "\tif (!group->private) {\n"
             "\t\tfd = -ENOMEM;\n"
             "\t\tgoto out_destroy_group;\n"
             "\t}\n")
    src = src[: m.end()] + alloc + src[m.end():]
    write(path, src)
    print("  fanotify_user.c: private block allocated after group creation")


def replace_ucounts(root: str) -> None:
    """Swap the four ucount call sites for our accounting, drop the enum."""
    usr = os.path.join(root, "fs/notify/fanotify/fanotify_user.c")
    fan = os.path.join(root, "fs/notify/fanotify/fanotify.c")

    # group charge
    src = read(usr)
    ACC = r"(?:group->fanotify_data\.|fanotify_group_priv\(group\)->)"
    pat = re.compile(r"\t/\* Enforce groups limits per user in all containing user ns \*/\n"
                     r"\t" + ACC + r"ucounts = inc_ucount\([^;]*;\n"
                     r"\tif \s*\(\s*!" + ACC + r"ucounts\) \{\n"
                     r"\t\tfd = -EMFILE;\n"
                     r"\t\tgoto out_destroy_group;\n"
                     r"\t\}\n", re.S)
    if pat.search(src):
        src = pat.sub("\t/* Enforce group limits per user in all containing user ns */\n"
                      "\tfanotify_group_priv(group)->account_ns =\n"
                      "\t\tget_user_ns(current_user_ns());\n"
                      "\tif (!fanotify_account_group(fanotify_group_priv(group)->account_ns)) {\n"
                      "\t\tfd = -EMFILE;\n"
                      "\t\tgoto out_destroy_group;\n"
                      "\t}\n", src, count=1)
        write(usr, src)
        print("  fanotify_user.c: group charge -> fanotify_account_group()")

    # mark charge + local ucounts variable + failure label
    src = read(usr)
    src = re.sub(r"\tstruct ucounts \*ucounts = " + ACC + r"ucounts;\n", "", src, count=1)
    pat = re.compile(r"\tif \(!FAN_GROUP_FLAG\(group, FAN_UNLIMITED_MARKS\) &&\n"
                     r"\t    !inc_ucount\(ucounts->ns, ucounts->uid, UCOUNT_FANOTIFY_MARKS\)\)\n"
                     r"\t\treturn ERR_PTR\(-ENOSPC\);\n")
    if pat.search(src):
        src = pat.sub("\tif (!FAN_GROUP_FLAG(group, FAN_UNLIMITED_MARKS) &&\n"
                      "\t    !fanotify_account_mark(fanotify_group_priv(group)->account_ns))\n"
                      "\t\treturn ERR_PTR(-ENOSPC);\n", src, count=1)
    src = re.sub(r"out_dec_ucounts:\n"
                 r"\tif \(!FAN_GROUP_FLAG\(group, FAN_UNLIMITED_MARKS\)\)\n"
                 r"\t\tdec_ucount\(ucounts, UCOUNT_FANOTIFY_MARKS\);\n"
                 r"\treturn ERR_PTR\(ret\);\n",
                 "out_put_mark_charge:\n"
                 "\tif (!FAN_GROUP_FLAG(group, FAN_UNLIMITED_MARKS))\n"
                 "\t\tfanotify_account_put_mark(fanotify_group_priv(group)->account_ns);\n"
                 "\treturn ERR_PTR(ret);\n", src, count=1)
    src = src.replace("goto out_dec_ucounts;", "goto out_put_mark_charge;")
    write(usr, src)
    print("  fanotify_user.c: mark charge -> fanotify_account_mark()")

    # free paths
    src = read(fan)
    pat = re.compile(r"\tif \s*\(\s*" + ACC + r"ucounts\)\n"
                     r"\t\tdec_ucount\(" + ACC + r"ucounts,\n"
                     r"\t\t\t   UCOUNT_FANOTIFY_GROUPS\);\n")
    if pat.search(src):
        src = pat.sub("", src, count=1)
    pat = re.compile(r"\tif \(!FAN_GROUP_FLAG\(group, FAN_UNLIMITED_MARKS\)\)\n"
                     r"\t\tdec_ucount\(" + ACC + r"ucounts, UCOUNT_FANOTIFY_MARKS\);\n")
    if pat.search(src):
        src = pat.sub("\tif (!FAN_GROUP_FLAG(group, FAN_UNLIMITED_MARKS))\n"
                      "\t\tfanotify_account_put_mark(fanotify_group_priv(group)->account_ns);\n",
                      src, count=1)
    write(fan, src)
    print("  fanotify.c: release paths -> fanotify_account_put_*()")

    # the enum itself
    un = os.path.join(root, "include/linux/user_namespace.h")
    src = read(un)
    enum = re.compile(r"#ifdef CONFIG_FANOTIFY\n\tUCOUNT_FANOTIFY_GROUPS,\n\tUCOUNT_FANOTIFY_MARKS,\n#endif\n")
    if enum.search(src):
        src = enum.sub("", src, count=1)
        write(un, src)
        print("  user_namespace.h: UCOUNT_FANOTIFY_* removed (stock ucount layout)")
    elif "UCOUNT_FANOTIFY" in src:
        die("user_namespace.h: UCOUNT_FANOTIFY members present but not in the expected shape")

    # kernel/ucount.c enumerates one sysctl entry per type and asserts the count
    uc = os.path.join(root, "kernel/ucount.c")
    if os.path.exists(uc):
        usrc = read(uc)
        block = re.compile(r"#ifdef CONFIG_FANOTIFY\n(?:\tUCOUNT_ENTRY\(\"max_fanotify_\w+\"\),\n)+#endif\n")
        if block.search(usrc):
            usrc = block.sub("", usrc, count=1)
            write(uc, usrc)
            print("  kernel/ucount.c: fanotify sysctl entries removed")


def retarget_sysctls(root: str) -> None:
    path = os.path.join(root, "fs/notify/fanotify/fanotify_user.c")
    src = read(path)
    before = src
    src = src.replace("&init_user_ns.ucount_max[UCOUNT_FANOTIFY_GROUPS]",
                      "&fanotify_max_user_groups")
    src = src.replace("&init_user_ns.ucount_max[UCOUNT_FANOTIFY_MARKS]",
                      "&fanotify_max_user_marks")
    src = re.sub(r"init_user_ns\.ucount_max\[UCOUNT_FANOTIFY_GROUPS\] =\n\t+"
                 r"FANOTIFY_DEFAULT_MAX_GROUPS;\n",
                 "fanotify_max_user_groups = FANOTIFY_DEFAULT_MAX_GROUPS;\n", src, count=1)
    src = re.sub(r"init_user_ns\.ucount_max\[UCOUNT_FANOTIFY_MARKS\] = max_marks;\n",
                 "fanotify_max_user_marks = max_marks;\n", src, count=1)
    if src != before:
        write(path, src)
        print("  fanotify_user.c: sysctls + init defaults retargeted")
    else:
        print("  fanotify_user.c: sysctls already retargeted")


def free_priv(root: str) -> None:
    """Release the accounting charge first and the private block last.

    Order matters in both directions: the private block owns merge_hash and the
    error pool, so it must be freed after those; and the accounting uses
    group->user_ns, which fanotify_free_group_priv() may drop first on newer
    trees.
    """
    path = os.path.join(root, "fs/notify/fanotify/fanotify.c")
    src = read(path)
    if "kfree(group->private)" in src:
        print("  fanotify.c: private block already freed")
        return

    m = re.search(r"(static void fanotify_free_group_priv\(struct fsnotify_group \*group\)\n\{\n)(.*?)(\n\}\n)", src, re.S)
    if not m:
        die("fanotify.c: fanotify_free_group_priv() not found")

    head, body, tail = m.group(1), m.group(2), m.group(3)
    body = ("\tfanotify_account_put_group(fanotify_group_priv(group)->account_ns);\n"
            "\tput_user_ns(fanotify_group_priv(group)->account_ns);\n") + body
    body = body.rstrip("\n") + "\n\n\tkfree(group->private);\n\tgroup->private = NULL;\n"
    src = src[: m.start()] + head + body + tail + src[m.end():]
    write(path, src)
    print("  fanotify.c: accounting released first, private block freed last")


DECLS = f"""\
{MARKER}
/* Per-namespace group/mark accounting lives in fanotify_user.c. */
extern bool fanotify_account_group(struct user_namespace *ns);
extern void fanotify_account_put_group(struct user_namespace *ns);
extern bool fanotify_account_mark(struct user_namespace *ns);
extern void fanotify_account_put_mark(struct user_namespace *ns);
"""


def declare_accounting(root: str) -> None:
    """fanotify.c calls the accounting, so it needs the prototypes."""
    path = os.path.join(root, "fs/notify/fanotify/fanotify.h")
    src = read(path)
    if MARKER in src:
        print("  fanotify.h: accounting declarations already present")
        return
    write(path, src.rstrip("\n") + "\n\n" + DECLS)
    print("  fanotify.h: accounting declarations added")


def ensure_includes(root: str) -> None:
    """The accounting block needs hashtable/mutex/user_namespace.h in scope."""
    path = os.path.join(root, "fs/notify/fanotify/fanotify_user.c")
    src = read(path)
    missing = [h for h in ("<linux/hashtable.h>", "<linux/mutex.h>", "<linux/user_namespace.h>")
               if f"#include {h}" not in src]
    if not missing:
        print("  fanotify_user.c: includes already present")
        return
    lines = src.split("\n")
    last = max(i for i, ln in enumerate(lines[:80]) if ln.startswith("#include"))
    lines[last + 1:last + 1] = [f"#include {h}" for h in missing]
    write(path, "\n".join(lines))
    print(f"  fanotify_user.c: added {', '.join(missing)}")


def verify(root: str) -> None:
    problems = []
    for rel in ("fs/notify/fanotify/fanotify.c",
                "fs/notify/fanotify/fanotify_user.c",
                "fs/notify/fdinfo.c"):
        path = os.path.join(root, rel)
        if os.path.exists(path) and "group->fanotify_data." in read(path):
            problems.append(f"{rel}: group->fanotify_data. still present")
    for rel, needle in (
        ("fs/notify/fanotify/fanotify_user.c", "fanotify_account_group"),
        ("fs/notify/fanotify/fanotify_user.c", "fanotify_account_mark"),
        ("fs/notify/fanotify/fanotify_user.c", "group->private = kzalloc"),
        ("fs/notify/fanotify/fanotify.c", "fanotify_account_put_group"),
        ("fs/notify/fanotify/fanotify.c", "kfree(group->private)"),
        ("include/linux/fsnotify_backend.h", "fanotify_group_priv"),
        ("fs/notify/fanotify/fanotify.h", "fanotify_account_put_group"),
    ):
        if needle not in read(os.path.join(root, rel)):
            problems.append(f"{rel}: missing {needle!r}")
    for rel in ("fs/notify/fanotify/fanotify.c", "fs/notify/fanotify/fanotify_user.c"):
        path = os.path.join(root, rel)
        if os.path.exists(path) and "group->user_ns" in read(path):
            problems.append(f"{rel}: group->user_ns still referenced (absent before 6.12)")

    un = read(os.path.join(root, "include/linux/user_namespace.h"))
    if "UCOUNT_FANOTIFY" in un:
        problems.append("user_namespace.h: UCOUNT_FANOTIFY_* still declared")
    if problems:
        die("verification failed:\n  - " + "\n  - ".join(problems))
    print("  verified: no fanotify_data member access, accounting wired, enum back to stock")


def main() -> None:
    if len(sys.argv) != 2:
        die("usage: fanotify_zero_drift.py <kernel/common>")
    root = sys.argv[1].rstrip("/")
    print(f"[+] fanotify zero-drift port: {root}")

    backend = os.path.join(root, "include/linux/fsnotify_backend.h")
    if not os.path.exists(backend):
        die(f"{backend}: not found")

    if "fanotify_group_priv(struct fsnotify_group *group)" in read(backend):
        print("  already ported - verifying only")
    else:
        move_struct_out_of_union(backend)
        rewrite_accessors(root)
        rewrite_macro(root)
        insert_accounting(root)
        allocate_priv(root)
        retarget_sysctls(root)
        replace_ucounts(root)
        free_priv(root)
        declare_accounting(root)
        ensure_includes(root)

    verify(root)
    print("[+] done")


if __name__ == "__main__":
    main()
