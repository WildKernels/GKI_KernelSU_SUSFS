// SPDX-License-Identifier: GPL-2.0
/*
 * cpu.max for DroidSpaces containers, without CONFIG_CFS_BANDWIDTH.
 *
 * Why not the real thing. CFS_BANDWIDTH adds runtime_enabled, runtime_remaining,
 * the throttled clocks, throttle_count and throttled_list to struct cfs_rq, which
 * is embedded in struct rq. That shifts every member after it, and vendor modules
 * subscribed to the android vendor-hook tracepoints read rq fields at offsets
 * baked in when they were compiled. Shadowing the CRCs back to stock made the ABI
 * gate pass and the device still failed to boot (runs 44286900753, 44466030716).
 *
 * So the quota is enforced from outside the scheduler instead:
 *   - state per cgroup in a list, no struct anywhere is touched
 *   - a delayed work samples the cgroup's summed se.sum_exec_runtime every tick
 *   - when the quota for the period is spent, the cgroup's tasks are frozen;
 *     they are thawed when the next period starts
 *
 * Externally this is the same contract as cpu.max: a container may consume
 * quota microseconds of CPU per period microseconds, and no more. The difference
 * is granularity (one sample interval, 5 ms by default, against the scheduler's
 * own slice) and that a task in uninterruptible sleep is frozen when it next
 * becomes freezable rather than descheduled immediately.
 *
 * Files, matching what DroidSpaces and systemd write and read:
 *   cpu.max    "<quota> <period>" or "max <period>"
 * cpu.stat is left alone: cgroup_base_files[] already provides it in 6.1.
 * plus /proc/sys/kernel/sched_cfs_bandwidth_slice_us, which DroidSpaces probes to
 * decide whether CPU limits are supported at all.
 */
#include <linux/cgroup.h>
#include <linux/freezer.h>
#include <linux/jiffies.h>
#include <linux/ktime.h>
#include <linux/list.h>
#include <linux/mutex.h>
#include <linux/sched.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/string.h>
#include <linux/sysctl.h>
#include <linux/workqueue.h>

#include "cgroup-internal.h"

#define DS_CPU_DEFAULT_PERIOD_US	100000LL
#define DS_CPU_TICK_MS			5

struct ds_cpuquota {
	struct cgroup	*cgrp;
	s64		quota_us;	/* <= 0: unlimited */
	s64		period_us;
	u64		used_ns;
	u64		last_sum_ns;
	u64		period_start_ns;
	u64		nr_periods;
	u64		nr_throttled;
	u64		throttled_ns;
	u64		throttle_start_ns;
	bool		throttled;
	struct list_head node;
};

static LIST_HEAD(ds_cpuquotas);
static DEFINE_MUTEX(ds_cpuquota_lock);
static void ds_cpuquota_workfn(struct work_struct *work);
static DECLARE_DELAYED_WORK(ds_cpuquota_work, ds_cpuquota_workfn);

/* DroidSpaces probes this sysctl; upstream's default slice is 5 ms. */
static int ds_sched_cfs_bandwidth_slice_us = 5000;

static struct ctl_table ds_cpuquota_sysctls[] = {
	{
		.procname	= "sched_cfs_bandwidth_slice_us",
		.data		= &ds_sched_cfs_bandwidth_slice_us,
		.maxlen		= sizeof(int),
		.mode		= 0644,
		.proc_handler	= proc_dointvec_minmax,
		.extra1		= SYSCTL_ONE,
	},
	{ }
};

static u64 ds_cpu_sum_runtime(struct cgroup *cgrp)
{
	struct css_task_iter it;
	struct task_struct *task;
	u64 sum = 0;

	css_task_iter_start(&cgrp->self, 0, &it);
	while ((task = css_task_iter_next(&it)))
		sum += task->se.sum_exec_runtime;
	css_task_iter_end(&it);
	return sum;
}

static void ds_cpu_freeze(struct cgroup *cgrp, bool freeze)
{
	struct css_task_iter it;
	struct task_struct *task;

	css_task_iter_start(&cgrp->self, 0, &it);
	while ((task = css_task_iter_next(&it))) {
		if (freeze)
			freeze_task(task);
		else
			__thaw_task(task);
	}
	css_task_iter_end(&it);
}

static struct ds_cpuquota *ds_cpuquota_get(struct cgroup *cgrp)
{
	struct ds_cpuquota *q;

	list_for_each_entry(q, &ds_cpuquotas, node)
		if (q->cgrp == cgrp)
			return q;
	return NULL;
}

/* Caller holds ds_cpuquota_lock. */
static struct ds_cpuquota *ds_cpuquota_create(struct cgroup *cgrp)
{
	struct ds_cpuquota *q = ds_cpuquota_get(cgrp);

	if (q)
		return q;
	q = kzalloc(sizeof(*q), GFP_KERNEL);
	if (!q)
		return NULL;
	q->cgrp = cgrp;
	q->quota_us = 0;
	q->period_us = DS_CPU_DEFAULT_PERIOD_US;
	q->period_start_ns = ktime_get_ns();
	q->last_sum_ns = ds_cpu_sum_runtime(cgrp);
	list_add_tail(&q->node, &ds_cpuquotas);
	return q;
}

void ds_cpuquota_free(struct cgroup *cgrp)
{
	struct ds_cpuquota *q;

	mutex_lock(&ds_cpuquota_lock);
	q = ds_cpuquota_get(cgrp);
	if (q) {
		if (q->throttled)
			ds_cpu_freeze(cgrp, false);
		list_del(&q->node);
		kfree(q);
	}
	mutex_unlock(&ds_cpuquota_lock);
}

static void ds_cpuquota_workfn(struct work_struct *work)
{
	struct ds_cpuquota *q;
	u64 now = ktime_get_ns();
	bool active = false;

	mutex_lock(&ds_cpuquota_lock);
	list_for_each_entry(q, &ds_cpuquotas, node) {
		u64 sum, delta, period_ns;

		if (q->quota_us <= 0) {
			if (q->throttled) {
				ds_cpu_freeze(q->cgrp, false);
				q->throttled = false;
			}
			continue;
		}
		active = true;
		period_ns = (u64)q->period_us * NSEC_PER_USEC;

		sum = ds_cpu_sum_runtime(q->cgrp);
		delta = sum - q->last_sum_ns;
		q->last_sum_ns = sum;

		if (now - q->period_start_ns >= period_ns) {
			if (q->throttled) {
				q->throttled_ns += now - q->throttle_start_ns;
				ds_cpu_freeze(q->cgrp, false);
				q->throttled = false;
			}
			q->used_ns = 0;
			q->period_start_ns = now;
			q->nr_periods++;
		}

		q->used_ns += delta;

		if (!q->throttled &&
		    q->used_ns >= (u64)q->quota_us * NSEC_PER_USEC) {
			ds_cpu_freeze(q->cgrp, true);
			q->throttled = true;
			q->throttle_start_ns = now;
			q->nr_throttled++;
		}
	}
	mutex_unlock(&ds_cpuquota_lock);

	if (active)
		schedule_delayed_work(&ds_cpuquota_work,
				      msecs_to_jiffies(DS_CPU_TICK_MS));
}

int ds_cpu_max_show(struct seq_file *seq, void *v)
{
	struct cgroup *cgrp = seq_css(seq)->cgroup;
	struct ds_cpuquota *q;
	s64 quota = 0, period = DS_CPU_DEFAULT_PERIOD_US;

	mutex_lock(&ds_cpuquota_lock);
	q = ds_cpuquota_get(cgrp);
	if (q) {
		quota = q->quota_us;
		period = q->period_us;
	}
	mutex_unlock(&ds_cpuquota_lock);

	if (quota <= 0)
		seq_printf(seq, "max %lld\n", period);
	else
		seq_printf(seq, "%lld %lld\n", quota, period);
	return 0;
}

ssize_t ds_cpu_max_write(struct kernfs_open_file *of, char *buf,
			 size_t nbytes, loff_t off)
{
	struct cgroup *cgrp = cgroup_kn_lock_live(of->kn, false);
	struct ds_cpuquota *q;
	char *quota_str, *period_str;
	s64 quota = 0, period = DS_CPU_DEFAULT_PERIOD_US;
	ssize_t ret;

	if (!cgrp)
		return -ENODEV;

	buf = strstrip(buf);
	quota_str = strsep(&buf, " ");
	if (!quota_str || !*quota_str) {
		ret = -EINVAL;
		goto out;
	}
	if (strcmp(quota_str, "max")) {
		if (kstrtoll(quota_str, 0, &quota) || quota <= 0) {
			ret = -EINVAL;
			goto out;
		}
	}
	period_str = buf ? strstrip(buf) : NULL;
	if (period_str && *period_str) {
		if (kstrtoll(period_str, 0, &period) ||
		    period < 1000 || period > 1000000) {
			ret = -EINVAL;
			goto out;
		}
	}

	mutex_lock(&ds_cpuquota_lock);
	q = ds_cpuquota_create(cgrp);
	if (!q) {
		mutex_unlock(&ds_cpuquota_lock);
		ret = -ENOMEM;
		goto out;
	}
	q->quota_us = quota;
	q->period_us = period;
	q->used_ns = 0;
	q->period_start_ns = ktime_get_ns();
	q->last_sum_ns = ds_cpu_sum_runtime(cgrp);
	if (q->throttled) {
		ds_cpu_freeze(cgrp, false);
		q->throttled = false;
	}
	mutex_unlock(&ds_cpuquota_lock);

	if (quota > 0)
		schedule_delayed_work(&ds_cpuquota_work, 0);
	ret = nbytes;
out:
	cgroup_kn_unlock(of->kn);
	return ret;
}

static int __init ds_cpuquota_init(void)
{
	register_sysctl_init("kernel", ds_cpuquota_sysctls);
	return 0;
}
late_initcall(ds_cpuquota_init);
