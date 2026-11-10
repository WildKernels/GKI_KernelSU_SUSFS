#!/usr/bin/env python3
"""Prototype: pids.max/pids.current without a cgroup_subsys_id entry.

The real pids controller cannot be enabled on GKI without moving the ABI: it adds an
enumerator to enum cgroup_subsys_id, and genksyms folds the enumerator set into the CRC
of every exported prototype that names the type (~3,202 symbols). This prototype
sidesteps the enum entirely:

  * pids.max / pids.current are cgroup CORE files, added to the file-static
    cgroup_base_files[] array - not exported, not in any type CRC
  * the limit lives in a side table keyed by struct cgroup *, so struct cgroup keeps
    its exact layout (adding a field there would move CRCs of exported functions taking
    struct cgroup *)
  * enforcement is in cgroup_can_fork(): clone inherits the parent's cgroup, so counting
    the parent's cgroup is the right question; over the limit returns -EAGAIN, which is
    what a real pids controller returns

Counting is done on demand with css_task_iter rather than with maintained counters, so
there is no migration bookkeeping to get wrong. That is O(tasks) per fork and only runs
when a limit is set for that cgroup.

Usage: kernel-cgroup-pids-side.py /path/to/kernel-X-lts
Idempotent; exits non-zero if an anchor is missing.
"""

import re
import sys
from pathlib import Path

TARGET = "kernel/cgroup/cgroup.c"
MARKER = "pids_side_max"

CODE = r'''/*
 * pids.max / pids.current without a cgroup_subsys_id entry.
 *
 * The stock pids controller cannot be enabled on this tree without moving the ABI: it
 * adds an enumerator to enum cgroup_subsys_id and genksyms folds the enumerator set into
 * the CRC of every exported prototype naming that type. So the limit is kept in a side
 * table keyed by struct cgroup * (struct cgroup itself is untouched - adding a field
 * would move CRCs of exported functions that take it) and the files are cgroup core
 * files, which live in a file-static array and are not part of any type CRC.
 */
struct pids_side_limit {
	struct list_head node;
	struct cgroup *cgrp;
	long max;			/* -1 == "max" */
};

static LIST_HEAD(pids_side_limits);
static DEFINE_MUTEX(pids_side_lock);

static struct pids_side_limit *pids_side_find(struct cgroup *cgrp)
{
	struct pids_side_limit *l;

	list_for_each_entry(l, &pids_side_limits, node)
		if (l->cgrp == cgrp)
			return l;
	return NULL;
}

static long pids_side_max_of(struct cgroup *cgrp)
{
	struct pids_side_limit *l;
	long ret = -1;

	mutex_lock(&pids_side_lock);
	l = pids_side_find(cgrp);
	if (l)
		ret = l->max;
	mutex_unlock(&pids_side_lock);
	return ret;
}

/* tasks in this cgroup only - hierarchy is handled by the caller walking ancestors */
static long pids_side_count(struct cgroup *cgrp)
{
	struct css_task_iter it;
	struct task_struct *task;
	long n = 0;

	css_task_iter_start(&cgrp->self, 0, &it);
	while ((task = css_task_iter_next(&it)))
		n++;
	css_task_iter_end(&it);
	return n;
}

static int pids_side_max_show(struct seq_file *sf, void *v)
{
	struct cgroup *cgrp = of_css(sf->private)->cgroup;

	seq_printf(sf, "%ld\n", pids_side_max_of(cgrp));
	return 0;
}

static int pids_side_current_show(struct seq_file *sf, void *v)
{
	struct cgroup *cgrp = of_css(sf->private)->cgroup;

	seq_printf(sf, "%ld\n", pids_side_count(cgrp));
	return 0;
}

static ssize_t pids_side_max_write(struct kernfs_open_file *of, char *buf,
				   size_t nbytes, loff_t off)
{
	struct cgroup *cgrp = cgroup_kn_lock_live(of->kn, false);
	struct pids_side_limit *l;
	long max;

	if (!cgrp)
		return -ENODEV;

	buf = strstrip(buf);
	if (!strcmp(buf, "max")) {
		max = -1;
	} else if (kstrtol(buf, 10, &max) || max < 0) {
		cgroup_kn_unlock(of->kn);
		return -EINVAL;
	}

	mutex_lock(&pids_side_lock);
	l = pids_side_find(cgrp);
	if (max < 0) {
		if (l) {
			list_del(&l->node);
			kfree(l);
		}
	} else if (l) {
		l->max = max;
	} else {
		l = kzalloc(sizeof(*l), GFP_KERNEL);
		if (!l) {
			mutex_unlock(&pids_side_lock);
			cgroup_kn_unlock(of->kn);
			return -ENOMEM;
		}
		l->cgrp = cgrp;
		l->max = max;
		list_add(&l->node, &pids_side_limits);
	}
	mutex_unlock(&pids_side_lock);

	cgroup_kn_unlock(of->kn);
	return nbytes;
}

/* called from cgroup_can_fork(): the child will land in the parent's cgroup */
static int pids_side_can_fork(void)
{
	struct cgroup_subsys_state *css;
	struct cgroup *cgrp;
	long max;

	/*
	 * Process context - no rcu_read_lock(): pids_side_max_of() takes a mutex and
	 * pids_side_count() may sleep. A pids limit binds the whole subtree, so walk
	 * the css parents (struct cgroup has no parent pointer of its own).
	 */
	cgrp = task_dfl_cgroup(current);
	for (css = &cgrp->self; css; css = css->parent) {
		cgrp = css->cgroup;
		max = pids_side_max_of(cgrp);
		if (max >= 0 && pids_side_count(cgrp) >= max)
			return -EAGAIN;
	}

	return 0;
}

'''


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def patch(tree: Path) -> str:
    f = tree / "common" / TARGET if (tree / "common" / TARGET).is_file() else tree / TARGET
    if not f.is_file():
        die(f"{f}: not found")
    src = f.read_text()
    if MARKER in src:
        return "already ported"

    # 1. the helper block, immediately above the array that references it
    anchor = re.search(r"(?m)^static struct cftype cgroup_base_files\[\] = \{\n", src)
    if not anchor:
        die(f"{TARGET}: cgroup_base_files[] definition not found")
    src = src[:anchor.start()] + CODE + src[anchor.start():]

    # 2. the two files, at the head of the core file array
    m = re.search(r"(?m)^static struct cftype cgroup_base_files\[\] = \{\n", src)
    if not m:
        die(f"{TARGET}: cgroup_base_files[] not found")
    entries = ('\t{\n\t\t.name = "pids.max",\n\t\t.seq_show = pids_side_max_show,\n'
               '\t\t.write = pids_side_max_write,\n\t},\n'
               '\t{\n\t\t.name = "pids.current",\n\t\t.seq_show = pids_side_current_show,\n\t},\n')
    src = src[:m.end()] + entries + src[m.end():]

    # 2a. runc enables a controller by writing it to cgroup.subtree_control, which
    #     validates the token against the subsys array - without this, "+pids" fails
    #     with -ENOENT even though cgroup.controllers advertises it.
    m = re.search(r"(?m)^\t\tif \(tok\[0\] == '\\0'\)\n\t\t\tcontinue;\n", src)
    if not m:
        die(f"{TARGET}: subtree_control token loop not recognised")
    skip = ('\t\t/* pids is a core file here, not a subsys: accept and ignore the token */\n'
            '\t\tif (tok[0] == \'+\' || tok[0] == \'-\') {\n'
            '\t\t\tif (!strcmp(tok + 1, "pids"))\n'
            '\t\t\t\tcontinue;\n'
            '\t\t}\n')
    src = src[:m.end()] + skip + src[m.end():]

    # 2b. advertise it in cgroup.controllers, without which runc refuses to use it
    m = re.search(r"(?m)^\tcgroup_print_ss_mask\(seq, cgroup_control\(cgrp\)\);\n", src)
    if not m:
        die(f"{TARGET}: cgroup_controllers_show() body not recognised")
    src = src[:m.end()] + '\tseq_puts(seq, "pids\\n");\n' + src[m.end():]

    # 3. enforce in the fork path
    m = re.search(r"(?m)^int cgroup_can_fork\(struct task_struct \*child[^\n]*\n\{\n", src)
    if not m:
        die(f"{TARGET}: cgroup_can_fork() opening brace not found")
    check = ("\tint __pids_ret = pids_side_can_fork();\n\n"
             "\tif (__pids_ret)\n\t\treturn __pids_ret;\n\n")
    src = src[:m.end()] + check + src[m.end():]

    f.write_text(src)
    return "patched"


def main():
    if len(sys.argv) < 2:
        die("usage: kernel-cgroup-pids-side.py /path/to/kernel-X-lts")
    for t in sys.argv[1:]:
        print(f"{Path(t).name:16s} {patch(Path(t))}")


if __name__ == "__main__":
    main()
