// SPDX-License-Identifier: GPL-2.0
/*
 * Side-table storage for CFS bandwidth, so struct cfs_rq and task_group keep
 * their stock layouts. See ds_bandwidth.h for why.
 */
#include <linux/sched.h>
#include <linux/xarray.h>
#include <linux/jump_label.h>
#include <linux/slab.h>
#include <linux/list.h>

#include "sched.h"
#include "ds_bandwidth.h"

DEFINE_XARRAY(ds_bw_cfs_rq_state);
DEFINE_XARRAY(ds_bw_tg_state);
DEFINE_STATIC_KEY_FALSE(ds_bw_active);
struct ds_cfs_rq_bw ds_bw_inactive;

void ds_bw_activate(void)
{
	static_branch_enable(&ds_bw_active);
}

void ds_bw_cfs_rq_alloc(struct cfs_rq *cfs_rq)
{
	struct ds_cfs_rq_bw *bw;

	if (!cfs_rq || xa_load(&ds_bw_cfs_rq_state, (unsigned long)cfs_rq))
		return;
	bw = kzalloc(sizeof(*bw), GFP_KERNEL);
	if (!bw)
		return;
	INIT_LIST_HEAD(&bw->throttled_list);
	if (xa_err(xa_store(&ds_bw_cfs_rq_state, (unsigned long)cfs_rq, bw,
			    GFP_KERNEL)))
		kfree(bw);
}

void ds_bw_cfs_rq_free(struct cfs_rq *cfs_rq)
{
	struct ds_cfs_rq_bw *bw;

	if (!cfs_rq)
		return;
	bw = xa_erase(&ds_bw_cfs_rq_state, (unsigned long)cfs_rq);
	kfree(bw);
}

void ds_bw_tg_free(struct task_group *tg)
{
	struct ds_cfs_bandwidth *b;

	b = xa_erase(&ds_bw_tg_state, (unsigned long)tg);
	kfree(b);
}
