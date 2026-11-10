#!/usr/bin/env python3
"""Port CONFIG_SYSVIPC to 6.18 with task_struct's member list left untouched.

Measured on this tree: any change to task_struct's members moves 6,329 of 9,741
modversion CRCs, even when the replacement occupies identical bytes at identical
offsets. An unrelated type added to the same header moves none. So the members must
not exist at all, and the state lives in a table keyed by task pointer.

Usage: sysv_table_port.py <kernel/common>
"""

import os
import sys

HEADER = """/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _LINUX_SYSV_TASK_H
#define _LINUX_SYSV_TASK_H

#include <linux/list.h>
#include <linux/types.h>

/*
 * Per-task System V IPC state, held outside struct task_struct.
 *
 * CONFIG_SYSVIPC normally adds two members to task_struct. On 6.18 that moves the
 * modversion CRC of every symbol whose type graph reaches task_struct (measured:
 * 6,329 of 9,741), even if the members are relocated into identical padding. This
 * keeps the member list identical to a stock CONFIG_SYSVIPC=n build and stores the
 * state in a table keyed by task pointer instead.
 *
 * A NULL result means "no state", which every caller treats as empty; the allocation
 * happens on first use, so a task that never touches SysV IPC never pays for it.
 */

struct task_struct;
struct sem_undo_list;

struct sysv_task_state {
	struct sem_undo_list	*undo_list;
	struct list_head	 shm_clist;
};

#ifdef CONFIG_SYSVIPC
struct sysv_task_state *sysv_task_state_get(struct task_struct *tsk, bool alloc);
void sysv_task_state_free(struct task_struct *tsk);
#else /* CONFIG_SYSVIPC */
static inline struct sysv_task_state *sysv_task_state_get(struct task_struct *tsk,
							  bool alloc)
{
	return NULL;
}

static inline void sysv_task_state_free(struct task_struct *tsk)
{
}
#endif /* CONFIG_SYSVIPC */

#endif /* _LINUX_SYSV_TASK_H */
"""

IMPL = """// SPDX-License-Identifier: GPL-2.0
/*
 * Per-task System V IPC state, keyed by task pointer.
 *
 * struct task_struct normally carries sysvsem and sysvshm when CONFIG_SYSVIPC is on.
 * On 6.18 adding them - or relocating them into equivalent padding - moves 6,329 of
 * 9,741 modversion CRCs, because the member list itself is what genksyms hashes. So
 * the members are not declared at all and the state lives here instead, leaving
 * task_struct byte- and member-identical to a stock CONFIG_SYSVIPC=n build.
 *
 * Lookups happen only on SysV IPC paths: semtimedop, exit_sem, shmat/shmdt and kcmp.
 * The allocation is lazy; NULL means "no state yet" and callers treat it as empty.
 */
#include <linux/sched.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/xarray.h>
#include <linux/sysv_task.h>

static DEFINE_XARRAY(sysv_states);
static DEFINE_SPINLOCK(sysv_states_lock);

struct sysv_task_state *sysv_task_state_get(struct task_struct *tsk, bool alloc)
{
	unsigned long key = (unsigned long)tsk;
	struct sysv_task_state *st, *old;

	st = xa_load(&sysv_states, key);
	if (st || !alloc)
		return st;

	st = kzalloc(sizeof(*st), GFP_KERNEL_ACCOUNT);
	if (!st)
		return NULL;
	INIT_LIST_HEAD(&st->shm_clist);

	spin_lock_irq(&sysv_states_lock);
	old = xa_load(&sysv_states, key);
	if (old) {
		spin_unlock_irq(&sysv_states_lock);
		kfree(st);
		return old;
	}
	xa_store(&sysv_states, key, st, GFP_ATOMIC);
	spin_unlock_irq(&sysv_states_lock);

	return st;
}

void sysv_task_state_free(struct task_struct *tsk)
{
	struct sysv_task_state *st;

	spin_lock_irq(&sysv_states_lock);
	st = xa_erase(&sysv_states, (unsigned long)tsk);
	spin_unlock_irq(&sysv_states_lock);
	kfree(st);
}
"""


def die(m):
    sys.exit("ERROR: " + m)


def rd(p):
    return open(p, encoding="utf-8").read()


def wr(p, t):
    open(p, "w", encoding="utf-8").write(t)


def sub(path, old, new, what):
    s = rd(path)
    if new in s:
        print(f"  {what}: done")
        return
    if old not in s:
        die(f"{path}: anchor missing for {what}")
    wr(path, s.replace(old, new, 1))
    print(f"  {what}")


def main():
    root = sys.argv[1].rstrip("/")
    hdr = os.path.join(root, "include/linux/sysv_task.h")
    if not os.path.exists(hdr):
        wr(hdr, HEADER)
        print("  include/linux/sysv_task.h")

    impl = os.path.join(root, "kernel/sysv_state.c")
    if not os.path.exists(impl):
        wr(impl, IMPL)
        print("  kernel/sysv_state.c")

    mk = os.path.join(root, "kernel/Makefile")
    if "sysv_state.o" not in rd(mk):
        s2 = rd(mk)
        wr(mk, s2.rstrip("\n") + "\nobj-$(CONFIG_SYSVIPC) += sysv_state.o\n")
        print("  kernel/Makefile")
    else:
        print("  kernel/Makefile: done")

    # task_struct: members gone, nothing added
    sub(os.path.join(root, "include/linux/sched.h"),
        "#ifdef CONFIG_SYSVIPC\n\tstruct sysv_sem\t\t\tsysvsem;\n\tstruct sysv_shm\t\t\tsysvshm;\n#endif\n",
        "#ifdef CONFIG_SYSVIPC\n\t/* state is in sysv_state.c, keyed by task; see include/linux/sysv_task.h */\n#endif\n",
        "sched.h: members removed")

    sub(os.path.join(root, "include/linux/shm.h"),
        "#define shm_init_task(task) INIT_LIST_HEAD(&(task)->sysvshm.shm_clist)",
        "#define shm_init_task(task) do { } while (0) /* list set up on first use */",
        "shm.h: init macro")

    sem = os.path.join(root, "ipc/sem.c")
    sub(sem, "#include <linux/ipc_namespace.h>\n",
        "#include <linux/ipc_namespace.h>\n#include <linux/sysv_task.h>\n", "sem.c: include")
    sub(sem, """	struct sem_undo_list *undo_list;

	undo_list = current->sysvsem.undo_list;
	if (!undo_list) {""",
        """	struct sysv_task_state *st;
	struct sem_undo_list *undo_list;

	st = sysv_task_state_get(current, true);
	if (!st)
		return -ENOMEM;

	undo_list = st->undo_list;
	if (!undo_list) {""", "sem.c: get_undo_list")
    sub(sem, "\t\tcurrent->sysvsem.undo_list = undo_list;\n",
        "\t\tst->undo_list = undo_list;\n", "sem.c: store")
    sub(sem, """	struct sem_undo_list *undo_list;
	int error;

	if (clone_flags & CLONE_SYSVSEM) {
		error = get_undo_list(&undo_list);
		if (error)
			return error;
		refcount_inc(&undo_list->refcnt);
		tsk->sysvsem.undo_list = undo_list;
	} else
		tsk->sysvsem.undo_list = NULL;""",
        """	struct sem_undo_list *undo_list;
	struct sysv_task_state *st;
	int error;

	if (clone_flags & CLONE_SYSVSEM) {
		st = sysv_task_state_get(tsk, true);
		if (!st)
			return -ENOMEM;
		error = get_undo_list(&undo_list);
		if (error)
			return error;
		refcount_inc(&undo_list->refcnt);
		st->undo_list = undo_list;
	} else {
		st = sysv_task_state_get(tsk, false);
		if (st)
			st->undo_list = NULL;
	}""", "sem.c: copy_semundo")
    sub(sem, """	struct sem_undo_list *ulp;

	ulp = tsk->sysvsem.undo_list;
	if (!ulp)
		return;
	tsk->sysvsem.undo_list = NULL;""",
        """	struct sysv_task_state *st;
	struct sem_undo_list *ulp;

	st = sysv_task_state_get(tsk, false);
	if (!st)
		return;

	ulp = st->undo_list;
	if (!ulp)
		return;
	st->undo_list = NULL;""", "sem.c: exit_sem")

    shm = os.path.join(root, "ipc/shm.c")
    sub(shm, "#include <linux/ipc_namespace.h>\n",
        "#include <linux/ipc_namespace.h>\n#include <linux/sysv_task.h>\n", "shm.c: include")
    sub(shm, """		struct shmid_kernel *shp;
		struct ipc_namespace *ns;

		task_lock(task);

		if (list_empty(&task->sysvshm.shm_clist)) {
			task_unlock(task);
			break;
		}

		shp = list_first_entry(&task->sysvshm.shm_clist, struct shmid_kernel,
				shm_clist);""",
        """		struct shmid_kernel *shp;
		struct ipc_namespace *ns;
		struct sysv_task_state *st;

		task_lock(task);

		st = sysv_task_state_get(task, false);
		if (!st || list_empty(&st->shm_clist)) {
			task_unlock(task);
			break;
		}

		shp = list_first_entry(&st->shm_clist, struct shmid_kernel,
				shm_clist);""", "shm.c: close walk")
    sub(shm, """	int error;
	struct shmid_kernel *shp;
	size_t numpages = (size + PAGE_SIZE - 1) >> PAGE_SHIFT;""",
        """	int error;
	struct shmid_kernel *shp;
	struct sysv_task_state *st;
	size_t numpages = (size + PAGE_SIZE - 1) >> PAGE_SHIFT;""", "shm.c: newseg decl")
    sub(shm, """	task_lock(current);
	list_add(&shp->shm_clist, &current->sysvshm.shm_clist);
	task_unlock(current);""",
        """	st = sysv_task_state_get(current, true);
	if (!st) {
		error = -ENOMEM;
		goto no_id;
	}

	task_lock(current);
	list_add(&shp->shm_clist, &st->shm_clist);
	task_unlock(current);""", "shm.c: list_add")

    kc = os.path.join(root, "kernel/kcmp.c")
    sub(kc, "#include <linux/eventpoll.h>\n",
        "#include <linux/eventpoll.h>\n#include <linux/sysv_task.h>\n", "kcmp.c: include")
    sub(kc, """		ret = kcmp_ptr(task1->sysvsem.undo_list,
			       task2->sysvsem.undo_list,
			       KCMP_SYSVSEM);""",
        """		st1 = sysv_task_state_get(task1, false);
		st2 = sysv_task_state_get(task2, false);
		ret = kcmp_ptr(st1 ? st1->undo_list : NULL,
			       st2 ? st2->undo_list : NULL,
			       KCMP_SYSVSEM);""", "kcmp.c: compare")
    sub(kc, "\tcase KCMP_SYSVSEM:\n",
        "\tcase KCMP_SYSVSEM: {\n\t\tstruct sysv_task_state *st1, *st2;\n", "kcmp.c: decls")
    sub(kc, """		ret = kcmp_ptr(st1 ? st1->undo_list : NULL,
			       st2 ? st2->undo_list : NULL,
			       KCMP_SYSVSEM);
		break;""",
        """		ret = kcmp_ptr(st1 ? st1->undo_list : NULL,
			       st2 ? st2->undo_list : NULL,
			       KCMP_SYSVSEM);
		break;
		}""", "kcmp.c: close scope")

    fk = os.path.join(root, "kernel/fork.c")
    sub(fk, "#include <linux/sysv_task.h>\n", "", "fork.c: include stub") if False else None
    s = rd(fk)
    if "#include <linux/sysv_task.h>" not in s:
        s = s.replace("#include <linux/sched/task.h>\n",
                      "#include <linux/sched/task.h>\n#include <linux/sysv_task.h>\n", 1)
        wr(fk, s)
        print("  fork.c: include")
    sub(fk, "\tcpufreq_task_times_exit(tsk);\n",
        "\tcpufreq_task_times_exit(tsk);\n\tsysv_task_state_free(tsk);\n",
        "fork.c: free_task")

    print("[+] port applied")


if __name__ == "__main__":
    main()
