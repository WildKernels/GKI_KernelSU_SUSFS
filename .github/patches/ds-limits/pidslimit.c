// SPDX-License-Identifier: GPL-2.0-only
/*
 * The pids controller for DroidSpaces, without CONFIG_CGROUP_PIDS.
 *
 * Enabling the real one registers a subsystem: CGROUP_SUBSYS_COUNT grows, which
 * resizes fixed arrays inside struct cgroup and struct css_set
 * (include/linux/cgroup-defs.h), and prebuilt vendor modules then read stock
 * offsets against bigger structs. Measured on android14-6.1-2026-06: 3241 of
 * 8865 exported symbol CRCs moved (job 134742656292), and with the CRCs forced
 * back to stock via __GENKSYMS__ the device still did not boot (run 44290228394)
 * - matching CRCs does not make the layout match.
 *
 * This reproduces the controller's behaviour and drops only its registration:
 *   - state per cgroup in an xarray keyed by the cgroup pointer
 *   - atomic counters charged up the hierarchy, like pids_charge()
 *   - can_fork charges, checks, and rolls back on refusal, like pids_can_fork(),
 *     so two racing forks cannot both slip past the limit
 *   - cancel_fork and exit uncharge; migration moves the charge
 *   - pids.max / current / peak / events as cgroup base files
 *   - pids.events is pollable via kernfs_notify() on the file's node
 *
 * No struct, no symbol, no CRC change. The one thing that cannot be reproduced
 * without registering a subsystem is a cgroup v1 pids hierarchy; v2 - what
 * Android and DroidSpaces use - is complete.
 */
#include <linux/cgroup.h>
#include <linux/atomic.h>
#include <linux/errno.h>
#include <linux/kstrtox.h>
#include <linux/kernfs.h>
#include <linux/rcupdate.h>
#include <linux/sched.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/string.h>
#include <linux/xarray.h>

#include "cgroup-internal.h"

struct ds_pids {
	s64		max;		/* <= 0: unlimited */
	atomic64_t	counter;
	atomic64_t	peak;
	atomic64_t	events;
};

static DEFINE_XARRAY(ds_pids_state);
static DEFINE_SPINLOCK(ds_pids_lock);

static struct ds_pids *ds_pids_get(struct cgroup *cgrp)
{
	return xa_load(&ds_pids_state, (unsigned long)cgrp);
}

/* Called from cgroup_create(), so the charge paths never have to allocate. */
int ds_pids_alloc(struct cgroup *cgrp)
{
	struct ds_pids *p;
	int ret = 0;

	if (ds_pids_get(cgrp))
		return 0;
	p = kzalloc(sizeof(*p), GFP_KERNEL);
	if (!p)
		return -ENOMEM;
	p->max = 0;
	spin_lock(&ds_pids_lock);
	if (xa_insert(&ds_pids_state, (unsigned long)cgrp, p, GFP_NOWAIT)) {
		kfree(p);
		ret = -EEXIST;
	}
	spin_unlock(&ds_pids_lock);
	return ret == -EEXIST ? 0 : ret;
}

/* Called when the cgroup is destroyed, so state cannot outlive it. */
void ds_pids_free(struct cgroup *cgrp)
{
	struct ds_pids *p;

	spin_lock(&ds_pids_lock);
	p = xa_erase(&ds_pids_state, (unsigned long)cgrp);
	spin_unlock(&ds_pids_lock);
	kfree(p);
}

/* Atomic context: fork, exit and migrate all call this under css_set_lock. */
static void ds_pids_charge(struct cgroup *cgrp, int n)
{
	struct cgroup *c;

	rcu_read_lock();
	for (c = cgrp; c; c = cgroup_parent(c)) {
		struct ds_pids *p = ds_pids_get(c);
		s64 val, peak;

		if (!p)
			continue;
		val = atomic64_add_return(n, &p->counter);
		if (n <= 0)
			continue;
		peak = atomic64_read(&p->peak);
		while (val > peak) {
			s64 old = atomic64_cmpxchg(&p->peak, peak, val);

			if (old == peak)
				break;
			peak = old;
		}
	}
	rcu_read_unlock();
}

static void ds_pids_notify_events(struct cgroup *cgrp)
{
	struct kernfs_node *kn;

	kn = kernfs_find_and_get_ns(cgrp->kn, "pids.events", NULL);
	if (kn) {
		kernfs_notify(kn);
		kernfs_put(kn);
	}
}

/*
 * Charge first, then check - the same order as pids_can_fork(). On refusal the
 * charge is rolled back, the event is counted and pollers are woken.
 */
int ds_pids_can_fork(struct task_struct *task)
{
	struct cgroup *c, *base = task_dfl_cgroup(task);
	int ret = 0;

	ds_pids_charge(base, 1);

	rcu_read_lock();
	for (c = base; c; c = cgroup_parent(c)) {
		struct ds_pids *p = ds_pids_get(c);

		if (!p || p->max <= 0)
			continue;
		if (atomic64_read(&p->counter) > p->max) {
			atomic64_inc(&p->events);
			ds_pids_notify_events(c);
			ret = -EAGAIN;
			break;
		}
	}
	rcu_read_unlock();

	if (ret)
		ds_pids_charge(base, -1);
	return ret;
}

void ds_pids_cancel_fork(struct task_struct *task)
{
	ds_pids_charge(task_dfl_cgroup(task), -1);
}

void ds_pids_exit(struct task_struct *task)
{
	ds_pids_charge(task_dfl_cgroup(task), -1);
}

/* Migration moves the charge, as pids_can_attach() / pids_attach() do. */
void ds_pids_migrate(struct task_struct *task, struct cgroup *dst)
{
	ds_pids_charge(task_dfl_cgroup(task), -1);
	ds_pids_charge(dst, 1);
}

static bool ds_pids_within(struct cgroup *cgrp, struct cgroup *ancestor)
{
	for (; cgrp; cgrp = cgroup_parent(cgrp))
		if (cgrp == ancestor)
			return true;
	return false;
}

/*
 * Refuse a migration that would put a destination over its limit, before any
 * task moves - the same place pids_can_attach() runs. Only tasks arriving from
 * outside an ancestor's subtree count against it; a move inside the subtree is
 * already in that ancestor's counter.
 */
int ds_pids_migrate_check(struct cgroup_taskset *tset)
{
	struct xarray pending;
	struct css_set *cset;
	struct task_struct *task;
	unsigned long idx;
	void *entry;
	int ret = 0;

	xa_init(&pending);
	list_for_each_entry(cset, &tset->src_csets, mg_node) {
		list_for_each_entry(task, &cset->mg_tasks, cg_list) {
			struct cgroup *src = task_dfl_cgroup(task);
			struct cgroup *dst = cset->mg_dst_cset->dfl_cgrp;
			struct cgroup *c;

			for (c = dst; c; c = cgroup_parent(c)) {
				unsigned long n;

				if (ds_pids_within(src, c))
					continue;
				n = (unsigned long)xa_load(&pending, (unsigned long)c);
				if (xa_err(xa_store(&pending, (unsigned long)c,
						    (void *)(n + 1), GFP_KERNEL))) {
					ret = -ENOMEM;
					goto out;
				}
			}
		}
	}

	xa_for_each(&pending, idx, entry) {
		struct cgroup *c = (struct cgroup *)idx;
		struct ds_pids *p = ds_pids_get(c);
		s64 arriving = (s64)(unsigned long)entry;

		if (!p || p->max <= 0)
			continue;
		if (atomic64_read(&p->counter) + arriving > p->max) {
			ret = -EAGAIN;
			break;
		}
	}
out:
	xa_destroy(&pending);
	return ret;
}

int ds_pids_max_show(struct seq_file *seq, void *v)
{
	struct ds_pids *p = ds_pids_get(seq_css(seq)->cgroup);

	if (!p || p->max <= 0)
		seq_puts(seq, "max\n");
	else
		seq_printf(seq, "%lld\n", p->max);
	return 0;
}

ssize_t ds_pids_max_write(struct kernfs_open_file *of, char *buf,
			  size_t nbytes, loff_t off)
{
	struct cgroup *cgrp = cgroup_kn_lock_live(of->kn, false);
	struct ds_pids *p;
	s64 max;
	ssize_t ret;

	if (!cgrp)
		return -ENODEV;

	buf = strstrip(buf);
	if (!strcmp(buf, "max"))
		max = 0;
	else if (kstrtoll(buf, 0, &max) || max < 0)
		max = -1;

	if (max < 0) {
		ret = -EINVAL;
		goto out;
	}

	p = ds_pids_get(cgrp);
	if (!p) {
		if (ds_pids_alloc(cgrp)) {
			ret = -ENOMEM;
			goto out;
		}
		p = ds_pids_get(cgrp);
	}
	p->max = max;
	ret = nbytes;
out:
	cgroup_kn_unlock(of->kn);
	return ret;
}

int ds_pids_current_show(struct seq_file *seq, void *v)
{
	struct ds_pids *p = ds_pids_get(seq_css(seq)->cgroup);

	seq_printf(seq, "%lld\n", p ? atomic64_read(&p->counter) : 0LL);
	return 0;
}

int ds_pids_peak_show(struct seq_file *seq, void *v)
{
	struct ds_pids *p = ds_pids_get(seq_css(seq)->cgroup);

	seq_printf(seq, "%lld\n", p ? atomic64_read(&p->peak) : 0LL);
	return 0;
}

int ds_pids_events_show(struct seq_file *seq, void *v)
{
	struct ds_pids *p = ds_pids_get(seq_css(seq)->cgroup);

	seq_printf(seq, "max %lld\n", p ? atomic64_read(&p->events) : 0LL);
	return 0;
}
