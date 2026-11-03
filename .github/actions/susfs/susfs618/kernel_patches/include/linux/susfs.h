#ifndef KSU_SUSFS_H
#define KSU_SUSFS_H

#include <linux/version.h>
#include <linux/types.h>
#include <linux/utsname.h>
#include <linux/hashtable.h>
#include <linux/path.h>
#include <linux/susfs_def.h>
#include <linux/statfs.h>

#define SUSFS_VERSION "v2.3.0"
#if LINUX_VERSION_CODE < KERNEL_VERSION(5,0,0)
#define SUSFS_VARIANT "NON-GKI"
#else
#define SUSFS_VARIANT "GKI"
#endif

/*********/
/* MACRO */
/*********/
#define getname_safe(name) (name == NULL ? ERR_PTR(-EINVAL) : getname(name))
#define putname_safe(name) (IS_ERR(name) ? NULL : putname(name))

/********/
/* ENUM */
/********/
#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT
enum UID_SCHEME {
	UID_NON_APP_PROC = 0,
	UID_ROOT_PROC_EXCEPT_SU_PROC,
	UID_NON_SU_PROC,
	UID_UMOUNTED_APP_PROC,
	UID_UMOUNTED_PROC,
};
#endif // #ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT

/**********/
/* STRUCT */
/**********/
/* sus_path */
#ifdef CONFIG_KSU_SUSFS_SUS_PATH
struct st_susfs_sus_path {
	char                                    target_pathname[SUSFS_MAX_LEN_PATHNAME];
	int                                     err;
};

struct st_susfs_sus_path_list {
	struct list_head                        list;
	struct st_susfs_sus_path                info;
	char                                    target_pathname[SUSFS_MAX_LEN_PATHNAME];
};
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_PATH

/* sus_mount */
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
struct st_susfs_hide_sus_mnts_for_non_su_procs {
	bool                                    enabled;
	int                                     err;
};
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT

/* sus_kstat */
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
#define KSTAT_SPOOF_INO (1 << 0)
#define KSTAT_SPOOF_DEV (1 << 1)
#define KSTAT_SPOOF_NLINK (1 << 2)
#define KSTAT_SPOOF_SIZE (1 << 3)
#define KSTAT_SPOOF_ATIME_TV_SEC (1 << 4)
#define KSTAT_SPOOF_ATIME_TV_NSEC (1 << 5)
#define KSTAT_SPOOF_MTIME_TV_SEC (1 << 6)
#define KSTAT_SPOOF_MTIME_TV_NSEC (1 << 7)
#define KSTAT_SPOOF_CTIME_TV_SEC (1 << 8)
#define KSTAT_SPOOF_CTIME_TV_NSEC (1 << 9)
#define KSTAT_SPOOF_BLOCKS (1 << 10)
#define KSTAT_SPOOF_BLKSIZE (1 << 11)

struct st_susfs_sus_kstat {
	bool                                    is_statically;
	unsigned long                           target_ino;
	char                                    target_pathname[SUSFS_MAX_LEN_PATHNAME];
	unsigned long                           spoofed_ino;
	unsigned long                           spoofed_dev;
	unsigned int                            spoofed_nlink;
	long long                               spoofed_size;
	long                                    spoofed_atime_tv_sec;
	unsigned long                           spoofed_atime_tv_nsec;
	long                                    spoofed_mtime_tv_sec;
	unsigned long                           spoofed_mtime_tv_nsec;
	long                                    spoofed_ctime_tv_sec;
	unsigned long                           spoofed_ctime_tv_nsec;
	long long                               spoofed_blocks;
	long                                    spoofed_blksize;
	int                                     flags;
	int                                     err;
};

struct st_susfs_sus_kstat_hlist {
	struct hlist_node                       node;
	unsigned long                           target_ino;
	unsigned long                           target_dev;
	struct kstatfs                          spoofed_kstatfs;
	int                                     spoofed_mnt_id;
	bool                                    is_fuse;
	struct st_susfs_sus_kstat               info;
};
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_KSTAT

/* spoof_uname */
#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME
struct st_susfs_uname {
	char                                    release[__NEW_UTS_LEN+1];
	char                                    version[__NEW_UTS_LEN+1];
	int                                     err;
};
#endif // #ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME

/* enable_log */
#ifdef CONFIG_KSU_SUSFS_ENABLE_LOG
struct st_susfs_log {
	bool                                    enabled;
	int                                     err;
};
#endif // #ifdef CONFIG_KSU_SUSFS_ENABLE_LOG

/* spoof_cmdline_or_bootconfig */
#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
struct st_susfs_spoof_cmdline_or_bootconfig {
	char                                    fake_cmdline_or_bootconfig[SUSFS_FAKE_CMDLINE_OR_BOOTCONFIG_SIZE];
	int                                     err;
};
#endif // #ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG

/* open_redirect */
#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT
struct st_susfs_open_redirect {
	char                                    target_pathname[SUSFS_MAX_LEN_PATHNAME];
	char                                    redirected_pathname[SUSFS_MAX_LEN_PATHNAME];
	int                                     uid_scheme;
	int                                     err;
};

struct st_susfs_open_redirect_hlist {
	struct hlist_node                       node;
	unsigned long                           target_ino;
	unsigned long                           target_dev;
	unsigned long                           redirected_ino;
	unsigned long                           redirected_dev;
	int                                     spoofed_mnt_id;
	struct kstatfs                          spoofed_kstatfs;
	struct st_susfs_open_redirect           info;
	bool                                    reversed_lookup_only;
};
#endif // #ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT

/* sus_map */
#ifdef CONFIG_KSU_SUSFS_SUS_MAP
struct st_susfs_sus_map {
	char                                    target_pathname[SUSFS_MAX_LEN_PATHNAME];
	int                                     err;
};
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP

/* getpriority uid filter */
#ifdef CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER
#define SUSFS_APP_STR_BUF_SIZE 65535
struct st_susfs_priority_uid_filter {
	char                                    app_strings[SUSFS_APP_STR_BUF_SIZE];
	int                                     err;
};
#endif // #ifdef CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER

/* avc log spoofing */
struct st_susfs_avc_log_spoofing {
	bool                                    enabled;
	int                                     err;
};

/* get enabled features */
struct st_susfs_enabled_features {
	char                                    enabled_features[SUSFS_ENABLED_FEATURES_SIZE];
	int                                     err;
};

/* show variant */
struct st_susfs_variant {
	char                                    susfs_variant[16];
	int                                     err;
};

/* show version */
struct st_susfs_version {
	char                                    susfs_version[16];
	int                                     err;
};

/***********************/
/* FORWARD DECLARATION */
/***********************/
/* sus_path */
#ifdef CONFIG_KSU_SUSFS_SUS_PATH
void susfs_add_sus_path(void __user **user_info);
void susfs_add_sus_path_loop(void __user **user_info);
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_PATH

/* sus_mount */
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
void susfs_set_hide_sus_mnts_for_non_su_procs(void __user **user_info);
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MOUNT

/* sus_kstat */
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
void susfs_add_sus_kstat(void __user **user_info);
void susfs_update_sus_kstat(void __user **user_info);
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_KSTAT

/* spoof_uname */
#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME
void susfs_set_uname(void __user **user_info);
void susfs_spoof_uname(struct new_utsname* tmp);
#endif // #ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME

/* enable_log */
#ifdef CONFIG_KSU_SUSFS_ENABLE_LOG
void susfs_enable_log(void __user **user_info);
#endif // #ifdef CONFIG_KSU_SUSFS_ENABLE_LOG

/* spoof_cmdline_or_bootconfig */
#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
void susfs_set_cmdline_or_bootconfig(void __user **user_info);
#endif // #ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG

/* open_redirect */
#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT
void susfs_add_open_redirect(void __user **user_info);
#endif // #ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT

/* sus_map */
#ifdef CONFIG_KSU_SUSFS_SUS_MAP
void susfs_add_sus_map(void __user **user_info);
#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP

/* getpriority uid filter */
#ifdef CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER
void susfs_set_priority_uid_filter(void __user **user_info);
void susfs_parse_priority_app_strings(void);
#endif // #ifdef CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER

void susfs_set_avc_log_spoofing(void __user **user_info);

void susfs_get_enabled_features(void __user **user_info);
void susfs_show_variant(void __user **user_info);
void susfs_show_version(void __user **user_info);

void susfs_start_sdcard_monitor_fn(void);

/* susfs_init */
void susfs_init(void);

#endif
