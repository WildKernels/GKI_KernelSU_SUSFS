// SPDX-License-Identifier: GPL-2.0-only
/*
 * pids.max / pids.current for DroidSpaces containers, without registering a
 * cgroup subsystem.
 *
 * Registering CONFIG_CGROUP_PIDS adds a SUBSYS(pids) entry, and that increments
 * CGROUP_SUBSYS_COUNT - the constant that sizes fixed arrays inside struct
 * cgroup and struct css_set (include/linux/cgroup-defs.h:218/258/447/464).
 * Both structs then grow, and prebuilt vendor modules that inline cgroup
 * helpers read fields at the wrong offsets.
 *
 * Measured on android14-6.1-2026-06: enabling the option moved 3241 of 8865
 * exported symbol CRCs (job 134742656292), and with the CRCs forced back to
 * stock via __GENKSYMS__ the device still did not boot (run 44290228394) -
 * matching CRCs does not make the layout match.
 *
 * So the limit lives here instead: state in an xarray keyed by the cgroup
 * pointer, the files declared in cgroup_base_files[] (cgroup files are per
 * cgroup, not per controller, so pids.max appears exactly where DroidSpaces
 * looks for it), and enforcement in the fork path. Nothing in struct cgroup,
 * struct css_set or any other ABI-visible type changes.
 */
#include <linux/cgroup.h>
#include <linux/errno.h>
#include <linux/kstrtox.h>
#include <linux/kernfs.h>
#include <linux/slab.h>
#include <linux/string.h>
#include <linux/xarray.h>

#include "cgroup-internal.h"

struct ds_pids_limit {
	s64 max;		/* <= 0 means unlimited */
};

static DEFINE_XARRAY(ds_pids_limits);

static struct ds_pids_limit *ds_pids_limit_get(struct cgroup *cgrp)
{
	return xa_load(&ds_pids_limits, (unsigned long)cgrp);
}

static int ds_pids_limit_set(struct cgroup *cgrp, s64 max)
{
	struct ds_pids_limit *lim;

	if (max <= 0) {
		lim = ds_pids_limit_get(cgrp);
		if (lim) {
			xa_erase(&ds_pids_limits, (unsigned long)cgrp);
			kfree(lim);
		}
		return 0;
	}

	lim = ds_pids_limit_get(cgrp);
	if (lim) {
		lim->max = max;
		return 0;
	}

	lim = kzalloc(sizeof(*lim), GFP_KERNEL);
	if (!lim)
		return -ENOMEM;
	lim->max = max;
	if (xa_insert(&ds_pids_limits, (unsigned long)cgrp, lim, GFP_KERNEL)) {
		kfree(lim);
		return -EEXIST;
	}
	return 0;
}

/* Called when the cgroup is destroyed, so the xarray entry cannot outlive it. */
void ds_pids_limit_free(struct cgroup *cgrp)
{
	struct ds_pids_limit *lim = ds_pids_limit_get(cgrp);

	if (lim) {
		xa_erase(&ds_pids_limits, (unsigned long)cgrp);
		kfree(lim);
	}
}

/* Tasks in this cgroup and everything below it. */
static int ds_pids_current(struct cgroup *cgrp)
{
	struct css_task_iter it;
	struct task_struct *task;
	int n = 0;

	css_task_iter_start(&cgrp->self, 0, &it);
	while ((task = css_task_iter_next(&it)))
		n++;
	css_task_iter_end(&it);
	return n;
}

/*
 * Checked on fork: a task may not be created if its cgroup - or any ancestor -
 * is already at its limit. Called from copy_process() after cgroup_can_fork(),
 * so the failing child never becomes visible.
 */
int ds_pids_limit_check(struct task_struct *task)
{
	struct cgroup *cgrp = task_dfl_cgroup(task);

	for (; cgrp; cgrp = cgroup_parent(cgrp)) {
		struct ds_pids_limit *lim = ds_pids_limit_get(cgrp);

		if (!lim || lim->max <= 0)
			continue;
		if (ds_pids_current(cgrp) >= lim->max)
			return -EAGAIN;
	}
	return 0;
}

int ds_pids_max_show(struct seq_file *seq, void *v)
{
	struct cgroup *cgrp = seq_css(seq)->cgroup;
	struct ds_pids_limit *lim = ds_pids_limit_get(cgrp);

	if (!lim || lim->max <= 0)
		seq_puts(seq, "max\n");
	else
		seq_printf(seq, "%lld\n", lim->max);
	return 0;
}

ssize_t ds_pids_max_write(struct kernfs_open_file *of, char *buf,
			  size_t nbytes, loff_t off)
{
	struct cgroup *cgrp = cgroup_kn_lock_live(of->kn, false);
	ssize_t ret;
	s64 max;

	if (!cgrp)
		return -ENODEV;

	buf = strstrip(buf);
	if (!strcmp(buf, "max"))
		max = 0;
	else if (kstrtoll(buf, 0, &max) || max < 0)
		max = -1;

	if (max < 0)
		ret = -EINVAL;
	else if (ds_pids_limit_set(cgrp, max))
		ret = -ENOMEM;
	else
		ret = nbytes;

	cgroup_kn_unlock(of->kn);
	return ret;
}

int ds_pids_current_show(struct seq_file *seq, void *v)
{
	seq_printf(seq, "%d\n", ds_pids_current(seq_css(seq)->cgroup));
	return 0;
}
