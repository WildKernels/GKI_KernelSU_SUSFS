/* SPDX-License-Identifier: GPL-2.0 */
/*
 * CFS bandwidth state, kept out of the scheduler's structs.
 *
 * CONFIG_CFS_BANDWIDTH adds ten fields to struct cfs_rq, which is embedded in
 * struct rq, and fills struct cfs_bandwidth, which is embedded in task_group.
 * Both types are in the GKI ABI graph (root_task_group is exported), so enabling
 * the option moves thousands of symbol CRCs - and even with the CRCs shadowed
 * back to stock the device does not boot, because vendor modules read rq fields
 * at offsets baked in when they were compiled (runs 44286900753, 44466030716).
 *
 * This header holds the same state in side tables keyed by the cfs_rq and
 * task_group pointers, so the bandwidth code itself can run unmodified while
 * every struct keeps its stock layout. The port script rewrites the field
 * accesses to these accessors and enables the code under DS_CFS_BANDWIDTH.
 *
 * Cost control: while no quota has ever been set, ds_bw_active is false and the
 * cfs_rq accessor returns a shared zeroed entry without a lookup, so the
 * scheduler's fast path is unchanged. The key is turned on when a quota is
 * configured, and never turned off - correctness first, and a device that has
 * used a container quota keeps paying the lookup.
 */
#ifndef _DS_BANDWIDTH_H
#define _DS_BANDWIDTH_H

#include <linux/xarray.h>
#include <linux/jump_label.h>
#include <linux/slab.h>
#include <linux/rcupdate.h>

struct ds_cfs_rq_bw {
	int			runtime_enabled;
	s64			runtime_remaining;
	u64			throttled_pelt_idle;
	u64			throttled_clock;
	u64			throttled_clock_pelt;
	u64			throttled_clock_pelt_time;
	int			throttled;
	int			throttle_count;
	struct list_head	throttled_list;
};

struct ds_cfs_bandwidth {
	raw_spinlock_t		lock;
	ktime_t			period;
	u64			quota;
	u64			runtime;
	u64			burst;
	u64			runtime_snap;
	s64			hierarchical_quota;

	u8			idle;
	u8			period_active;
	u8			slack_started;
	struct hrtimer		period_timer;
	struct hrtimer		slack_timer;
	struct list_head	throttled_cfs_rq;

	int			nr_periods;
	int			nr_throttled;
	int			nr_burst;
	u64			throttled_time;
	u64			burst_time;
};

extern struct xarray ds_bw_cfs_rq_state;
extern struct xarray ds_bw_tg_state;
extern struct static_key_false ds_bw_active;
extern struct ds_cfs_rq_bw ds_bw_inactive;

void ds_bw_cfs_rq_alloc(struct cfs_rq *cfs_rq);
void ds_bw_cfs_rq_free(struct cfs_rq *cfs_rq);
void ds_bw_tg_free(struct task_group *tg);
void ds_bw_activate(void);

/*
 * Fast path: no quota has ever been configured, so every runtime_enabled is 0
 * and the bandwidth code short-circuits exactly as it does with the option off.
 */
static inline struct ds_cfs_rq_bw *ds_cfs_rq_bw(struct cfs_rq *cfs_rq)
{
	struct ds_cfs_rq_bw *bw;

	if (!static_branch_unlikely(&ds_bw_active))
		return &ds_bw_inactive;
	rcu_read_lock();
	bw = xa_load(&ds_bw_cfs_rq_state, (unsigned long)cfs_rq);
	rcu_read_unlock();
	return bw ? bw : &ds_bw_inactive;
}

/*
 * First call comes from alloc_fair_sched_group() / sched_init(), in process
 * context, so the entry is allocated there; later calls are lookups only.
 */
static inline struct ds_cfs_bandwidth *ds_tg_bw(struct task_group *tg)
{
	struct ds_cfs_bandwidth *b;

	b = xa_load(&ds_bw_tg_state, (unsigned long)tg);
	if (b)
		return b;
	b = kzalloc(sizeof(*b), GFP_KERNEL);
	if (!b)
		return NULL;
	if (xa_err(xa_store(&ds_bw_tg_state, (unsigned long)tg, b, GFP_KERNEL))) {
		kfree(b);
		return xa_load(&ds_bw_tg_state, (unsigned long)tg);
	}
	return b;
}

#endif /* _DS_BANDWIDTH_H */
