#!/usr/bin/env bash
# FinaSU kernel-side SUSFS integration (vendored from LingLuo17/AnyKernel3,
# scripts/finasu_compat/apply.sh @dev, GPL-3.0; local edits: KSU dir arg).
# FinaSU 内核侧 SUSFS 集成补丁应用 + 内联适配修复
#
# 移植自旧版 scripts/susfs_fixes/apply.sh 的 FinaSU 分支：
#   1) 用 patch --forward 应用上游 10_enable_susfs_for_ksu.patch，
#      允许部分 hunk 失败（FinaSU 结构漂移）；
#   2) 按补丁意图对漂移文件做内联修复（init.c / selinux_hide.c /
#      ksud_integration.c / setuid_hook.c / Kbuild 等）。
#
# 用法: apply.sh [KSU_DIR]（默认 KernelSU）
set -eo pipefail

KSU_DIR="${1:-KernelSU}"
KERNEL_ROOT="${KERNEL_ROOT:-$PWD}"
SUSFS4KSU="${SUSFS4KSU:-$KERNEL_ROOT/susfs4ksu}"
KSU_VARIANT="FinaSU"
# Kernel version/sublevel passed by the caller (e.g. "android12-5.10" "270").
# Used to gate per-sublevel compat fixes that the 10_enable patch gets wrong.
KSU_VERSION="${2:-}"
KSU_SUBLEVEL="${3:-}"

UPSTREAM_PATCH="$SUSFS4KSU/kernel_patches/KernelSU/10_enable_susfs_for_ksu.patch"
[ -f "$UPSTREAM_PATCH" ] || {
  echo "::error::未找到 susfs4ksu KSU 侧补丁: $UPSTREAM_PATCH" >&2
  exit 1
}
[ -d "$KERNEL_ROOT/$KSU_DIR/.git" ] || {
  echo "::error::$KSU_DIR 不是 git 仓库检出，无法应用补丁" >&2
  exit 1
}

echo "步骤 1/2: 应用 susfs4ksu 10_enable_susfs_for_ksu.patch（patch --forward，允许部分失败）..."
cp "$UPSTREAM_PATCH" "$KERNEL_ROOT/$KSU_DIR/10_enable_susfs_for_ksu.patch"
(cd "$KERNEL_ROOT/$KSU_DIR" && patch -p1 --forward <10_enable_susfs_for_ksu.patch) || true
rm -f "$KERNEL_ROOT/$KSU_DIR/10_enable_susfs_for_ksu.patch"

# 1.5) 5.10 preinit close_fd compat (FINASU_PREINIT_CLOSE_FD): the 10_enable
#   patch rewrites FinaSU's ksu_close_fd(fd) -> bare close_fd(fd) in
#   kernel/preinit/preinit.c (it applies cleanly, no reject). close_fd is a
#   public symbol only on 5.15+; on 5.10 it is undeclared (only __close_fd is
#   exported), so -Werror fails the build:
#     preinit.c:130:9: error: implicit declaration of function 'close_fd'
#   Restore the ksu_close_fd macro (ksyscall(close, fd)) for 5.10; leave 5.15+
#   on the patch's bare close_fd, which is the correct kernel-internal API.
FINASU_PREINIT="$KERNEL_ROOT/$KSU_DIR/kernel/preinit/preinit.c"
if [ -f "$FINASU_PREINIT" ] &&
   { [ "$KSU_VERSION" = "android12-5.10" ] || [ "$KSU_VERSION" = "android13-5.10" ]; }; then
  if grep -qE '^[[:space:]]*close_fd\(fd\);' "$FINASU_PREINIT"; then
    sed -i 's/^\([[:space:]]*\)close_fd(fd);/\1ksu_close_fd(fd);/' "$FINASU_PREINIT"
    echo "FinaSU preinit.c: restored ksu_close_fd(fd) for 5.10 (close_fd undeclared)"
  fi
fi

echo "步骤 2/2: FinaSU 内联适配修复..."
if [ "$KSU_VARIANT" == "FinaSU" ]; then
  FINASU_KSU="$KERNEL_ROOT/$KSU_DIR/kernel"
  FINASU_INIT="$FINASU_KSU/core/init.c"
  FINASU_KSU_H="$FINASU_KSU/include/ksu.h"
  FINASU_KSI="$FINASU_KSU/runtime/ksud_integration.c"
  if [ ! -f "$FINASU_INIT" ] || [ ! -f "$FINASU_KSU_H" ]; then
    echo "::error::未找到 FinaSU 内核源码文件 (core/init.c / include/ksu.h)" >&2
    exit 1
  fi

  # 0) 回退 selinux_hide.c，并恢复其依赖的基础模块进入编译列表
  if git -C "$KERNEL_ROOT/$KSU_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    git -C "$KERNEL_ROOT/$KSU_DIR" checkout -- kernel/feature/selinux_hide.c
    if ! git -C "$KERNEL_ROOT/$KSU_DIR" diff --quiet -- kernel/feature/selinux_hide.c; then
      echo "::error::FinaSU selinux_hide.c 未能回退为原始版本" >&2
      exit 1
    fi
  fi
  if ! grep -q 'hook/lsm_hook.o' "$FINASU_KSU/Kbuild"; then
    sed -i 's|^kernelsu-objs += hook/setuid_hook.o$|kernelsu-objs += hook/setuid_hook.o\nkernelsu-objs += hook/lsm_hook.o\nkernelsu-objs += infra/symbol_resolver.o\n\nifeq ($(CONFIG_ARM64),y)\nkernelsu-objs += hook/arm64/patch_memory.o\nelse ifeq ($(CONFIG_X86_64),y)\nkernelsu-objs += hook/x86_64/patch_memory.o\nelse ifeq ($(CONFIG_RISCV),y)\nkernelsu-objs += hook/riscv64/patch_memory.o\nendif|' "$FINASU_KSU/Kbuild"
  fi

  # 0c) 40c97e24 起 preinit 依赖 hook/<arch>/syscall_hook.o（ksu_syscall_table），
  #     而补丁/上面的恢复可能只保留 patch_memory —— 逐架构补回缺失项
  for ARCH in arm64 x86_64 riscv64; do
    if [ -f "$FINASU_KSU/hook/$ARCH/syscall_hook.c" ] &&
      ! grep -q "hook/$ARCH/syscall_hook.o" "$FINASU_KSU/Kbuild" &&
      grep -q "hook/$ARCH/patch_memory.o" "$FINASU_KSU/Kbuild"; then
      sed -i "s|^kernelsu-objs += hook/$ARCH/patch_memory.o\$|kernelsu-objs += hook/$ARCH/patch_memory.o\nkernelsu-objs += hook/$ARCH/syscall_hook.o|" "$FINASU_KSU/Kbuild"
    fi
  done

  # 0b) SUSFS 内核补丁在 security/selinux/*.c 中以 extern 引用了这些符号，需与 BakaSU 一致
  #     改为全局定义，否则 ThinLTO 链接阶段会报 undefined symbol。
  #     - 6 个通用符号（>=5.10 用到）：
  #       fake_state / fake_status / fake_status_initialize_key / initialize_fake_status /
  #       ksu_selinux_hide_enabled / ksu_selinux_hide_running
  #     - 3 个 6.6 才用到的函数（android15-6.6 主补丁在 security/selinux/* 中 extern 引用，
  #       5.15/6.1 用不到，所以之前只在 6.6 上暴露为链接失败）：
  #       security_context_to_sid_with_policy / security_sid_to_context_with_policy /
  #       security_compute_av_user_with_policy
  FINASU_SELINUX_HIDE="$FINASU_KSU/feature/selinux_hide.c"
  if grep -q '^static bool ksu_selinux_hide_enabled ' "$FINASU_SELINUX_HIDE"; then
    sed -i \
      -e 's|^static bool ksu_selinux_hide_enabled |bool ksu_selinux_hide_enabled |' \
      -e 's|^static bool ksu_selinux_hide_running |bool ksu_selinux_hide_running |' \
      -e 's|^static struct selinux_state fake_state;|struct selinux_state fake_state;|' \
      -e 's|^static DEFINE_STATIC_KEY_FALSE(fake_status_initialize_key);|DEFINE_STATIC_KEY_FALSE(fake_status_initialize_key);|' \
      -e 's|^static struct page \*fake_status = NULL;|struct page *fake_status = NULL;\nvoid initialize_fake_status(void);|' \
      -e 's|^static void initialize_fake_status()|void initialize_fake_status(void)|' \
      -e 's|^static int security_context_to_sid_with_policy|int security_context_to_sid_with_policy|' \
      -e 's|^static int security_sid_to_context_with_policy|int security_sid_to_context_with_policy|' \
      -e 's|^static void security_compute_av_user_with_policy|void security_compute_av_user_with_policy|' \
      -e 's|^static void __nocfi security_compute_av_user_with_policy|void __nocfi security_compute_av_user_with_policy|' \
      "$FINASU_SELINUX_HIDE"
  fi

  # 0c) SUSFS 主补丁已在内核侧接管 selinuxfs：security/selinux/selinuxfs.c 把
  #     write_op[] 换成它自己的 my_write_access/my_write_context，security/selinux/hooks.c
  #     注册了 my_setprocattr，并托管 sel_handle_status_ops 的 status 处理。
  #     KSU 侧 selinux_hide.c 若再安装同名运行时 hook（write_op patch / setprocattr LSM hook /
  #     status open hook），两套 hook 会互相覆盖；一旦 KSU 侧 patch 失败，ksu_selinux_hide_running
  #     保持 false，SUSFS 内核代码里 !ksu_selinux_hide_running 的分支就会跳过伪装，
  #     表现为「隐藏 SELinux 失效」。这里按 SUSFS 设计，让 selinux_hide.c 只提供共享符号，
  #     不再安装运行时 hook。
  # selinux_hide 形态检测（在 0c 之前，此时文件已回退为上游原版）：
  #   新形态（preview1+）无 fake_state，0c 不能再注入 fake_state.initialized/policy，校验也跳过 fake_state 项
  NEW_MODEL=0
  if [ -f "$FINASU_SELINUX_HIDE" ] && ! grep -q 'fake_state' "$FINASU_SELINUX_HIDE"; then
    NEW_MODEL=1
  fi
  echo "FinaSU selinux_hide 形态: $([ "$NEW_MODEL" = 1 ] && echo 新 || echo 旧)"

  if ! grep -q 'FINASU_SUSFS_OWNS_SELINUXFS' "$FINASU_SELINUX_HIDE"; then
    python3 - "$FINASU_SELINUX_HIDE" "${NEW_MODEL:-0}" <<'PYEOF'
import sys

path = sys.argv[1]
new_model = (sys.argv[2] == "1")
src = open(path, encoding="utf-8").read()

# enable(): 在安装 write_op/status/setprocattr hook 之前直接返回；
# 旧形态另需保留 <6.6 的 fake_state 设置，新形态没有 fake_state（统一用 backup_sepolicy）
enable_anchor = '    selinux_write_op = find_kernel_symbol_exact("write_op");'
assert src.count(enable_anchor) == 1, "selinux_hide enable anchor not unique"
enable_block = (
    "#ifdef CONFIG_KSU_SUSFS\n"
    "    /* FINASU_SUSFS_OWNS_SELINUXFS: SUSFS 已接管 write_op/status/setprocattr */\n"
)
if not new_model:
    enable_block += (
        "#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 6, 0)\n"
        "    fake_state.initialized = true;\n"
        "    fake_state.policy = backup_sepolicy;\n"
        "#endif\n"
    )
enable_block += (
    "    return 0;\n"
    "#endif\n"
)
src = src.replace(enable_anchor, enable_block + enable_anchor, 1)

# unhook(): 没有安装过就不要还原
unhook_anchor = "static void ksu_selinux_hide_unhook()\n{\n"
assert src.count(unhook_anchor) == 1, "selinux_hide unhook anchor not unique"
src = src.replace(unhook_anchor, unhook_anchor + "#ifdef CONFIG_KSU_SUSFS\n    return;\n#endif\n", 1)

# init(): 不再 hook status open（SUSFS 负责）
init_anchor = "    hook_selinux_status_open();\n}"
assert src.count(init_anchor) == 1, "selinux_hide init anchor not unique"
src = src.replace(init_anchor, "#ifndef CONFIG_KSU_SUSFS\n    hook_selinux_status_open();\n#endif\n}", 1)

open(path, "w", encoding="utf-8").write(src)
print("selinux_hide.c: 已按 SUSFS 归属跳过 KSU 侧运行时 hook")
PYEOF
    grep -n 'FINASU_SUSFS_OWNS_SELINUXFS' "$FINASU_SELINUX_HIDE"
  fi

  # 0d) 保持 seccomp「过滤模式」（与 BakaSU 一致）：simonpunk 的 SUSFS KSU 补丁把
  #     setuid_hook.c 里的 ksu_seccomp_allow_cache(__NR_reboot) 改成了无条件 disable_seccomp()，
  #     于是管理器首页 Seccomp 状态显示“未开启”（0）。BakaSU 的做法是 >=5.10 保留过滤模式、
  #     仅把 reboot 加入 seccomp 白名单；这里改回 BakaSU 的逻辑。
  if [ -f "$FINASU_KSU/hook/setuid_hook.c" ] &&
    ! grep -q 'FINASU_SECCOMP_KEEP_FILTER' "$FINASU_KSU/hook/setuid_hook.c" &&
    grep -q '^        disable_seccomp();$' "$FINASU_KSU/hook/setuid_hook.c"; then
    python3 - "$FINASU_KSU/hook/setuid_hook.c" <<'PYEOF'
import sys

path = sys.argv[1]
src = open(path, encoding="utf-8").read()
needle = "        disable_seccomp();\n"
count = src.count(needle)
if count == 0:
    print("setuid_hook.c: 未发现无条件 disable_seccomp()，跳过")
    sys.exit(0)
repl = (
    "#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0) /* FINASU_SECCOMP_KEEP_FILTER */\n"
    "        if (current->seccomp.mode == SECCOMP_MODE_FILTER && current->seccomp.filter) {\n"
    "            spin_lock_irq(&current->sighand->siglock);\n"
    "            ksu_seccomp_allow_cache(current->seccomp.filter, __NR_reboot);\n"
    "            spin_unlock_irq(&current->sighand->siglock);\n"
    "        }\n"
    "#else\n"
    "        disable_seccomp();\n"
    "#endif\n"
)
src = src.replace(needle, repl)
open(path, "w", encoding="utf-8").write(src)
print("setuid_hook.c: 已将 %d 处 disable_seccomp() 改回 BakaSU 的 seccomp 白名单/过滤模式" % count)
PYEOF
    grep -n 'FINASU_SECCOMP_KEEP_FILTER\|ksu_seccomp_allow_cache(current->seccomp.filter' "$FINASU_KSU/hook/setuid_hook.c"
  fi

  # 0e) 补齐 ksud_integration.c 的 exec 钩子新签名
  #     simonpunk 的补丁把 exec 钩子改成 fd 版：ksud.h 的声明、sucompat.c 的
  #     ksu_handle_execveat() 调用都已是新签名，但 ksud_integration.c 里改写该函数的 hunk
  #     因 FinaSU 多了一行 ksu_feature_apply_forced() 而失败，于是定义仍是旧的
  #     void(const char*, struct user_arg_ptr*) → 「conflicting types for
  #     'ksu_handle_execveat_ksud'」。这里按补丁本意改写为 fd 版并保留 ksu_feature_apply_forced()。
  #     （旧的 ksu_execve_hook_ksud 定义已被补丁删除，其调用点 hook/syscall_event_bridge.c
  #      也已被补丁移出编译列表，所以不再需要。）
  if [ -f "$FINASU_KSI" ] && grep -q '^void ksu_handle_execveat_ksud(const char \*path, struct user_arg_ptr \*argv)' "$FINASU_KSI"; then
    python3 - "$FINASU_KSI" <<'PYEOF'
import os
import sys

path = sys.argv[1]
src = open(path, encoding="utf-8").read()

old_sig = "void ksu_handle_execveat_ksud(const char *path, struct user_arg_ptr *argv)\n"
if old_sig not in src:
    print("ksud_integration.c: 未找到旧版 ksu_handle_execveat_ksud，跳过")
    sys.exit(0)

# ksu_feature_apply_forced() 是新形态（preview1 起）才有的函数；旧形态源码里
# 引用它会变成隐式声明并在 -Werror 下编译失败，所以按符号存在性决定是否插入。
root = os.path.dirname(os.path.dirname(path))
has_forced = False
for dirpath, _dirs, files in os.walk(root):
    for f in files:
        if f == "ksud_integration.c" or not f.endswith((".c", ".h")):
            continue
        try:
            with open(os.path.join(dirpath, f), encoding="utf-8", errors="ignore") as fh:
                if "ksu_feature_apply_forced" in fh.read():
                    has_forced = True
                    break
        except OSError:
            pass
    if has_forced:
        break
forced_call = "                ksu_feature_apply_forced();\n" if has_forced else ""
print("ksud_integration.c: ksu_feature_apply_forced 存在=%s，%s该调用" % (has_forced, "保留" if has_forced else "跳过"))

start = src.index(old_sig)
end = src.index("\n}\n", start) + len("\n}\n")

new_func = (
    "extern int ksu_handle_execveat_init(struct filename *filename, struct user_arg_ptr *argv_user, struct user_arg_ptr *envp_user);\n"
    "\n"
    "// IMPORTANT NOTE: the call from execve_handler_pre WON'T provided correct value for envp and flags in GKI version\n"
    "int ksu_handle_execveat_ksud(int *fd, struct filename **filename_ptr,\n"
    "                             struct user_arg_ptr *argv,\n"
    "                             struct user_arg_ptr *envp, int *flags)\n"
    "{\n"
    "    struct filename *filename;\n"
    "    static const char app_process[] = \"/system/bin/app_process\";\n"
    "\n"
    "    /* This applies to versions Android 10+ */\n"
    "    static const char system_bin_init[] = \"/system/bin/init\";\n"
    "\n"
    "    if (!filename_ptr)\n"
    "        return 0;\n"
    "\n"
    "    filename = *filename_ptr;\n"
    "    if (IS_ERR(filename)) {\n"
    "        return 0;\n"
    "    }\n"
    "\n"
    "    if (static_branch_unlikely(&is_init_second_stage_not_executed)) {\n"
    "        // https://cs.android.com/android/platform/superproject/+/android-16.0.0_r2:system/core/init/main.cpp;l=77\n"
    "        if (unlikely(!memcmp(filename->name, system_bin_init, sizeof(system_bin_init) - 1) && argv)) {\n"
    "            char buf[16];\n"
    "            if (check_argv(*argv, 1, \"second_stage\", buf, sizeof(buf))) {\n"
    "                pr_info(\"/system/bin/init second_stage executed\\n\");\n"
    "                ksu_selinux_hide_handle_second_stage();\n"
    "                apply_kernelsu_rules();\n"
    "                cache_sid();\n"
    "                setup_ksu_cred();\n"
    + forced_call +
    "                static_branch_disable(&is_init_second_stage_not_executed);\n"
    "            }\n"
    "        }\n"
    "    }\n"
    "\n"
    "    if (static_branch_unlikely(&is_first_zygote)) {\n"
    "        if (unlikely(!memcmp(filename->name, app_process, sizeof(app_process) - 1) && argv)) {\n"
    "            char buf[16];\n"
    "            if (check_argv(*argv, 1, \"-Xzygote\", buf, sizeof(buf))) {\n"
    "                pr_info(\"exec zygote, /data prepared, second_stage: %d\\n\", !static_key_enabled(&is_init_second_stage_not_executed));\n"
    "                on_post_fs_data();\n"
    "                static_branch_disable(&is_first_zygote);\n"
    "            }\n"
    "        }\n"
    "    }\n"
    "\n"
    "    return 0;\n"
    "}\n"
)

src = src[:start] + new_func + src[end:]
open(path, "w", encoding="utf-8").write(src)
print("ksud_integration.c: 已按补丁本意把 ksu_handle_execveat_ksud 改写为 fd 版签名")
PYEOF
    grep -n '^int ksu_handle_execveat_ksud(int \*fd' "$FINASU_KSI"
  fi

  # 1) 移除已不参与编译的模块的调用（仅剩 syscall hook / syscall hook manager）
  sed -i \
    -e '/^[[:space:]]*ksu_syscall_hook_init();$/d' \
    -e '/^[[:space:]]*ksu_syscall_hook_manager_init();$/d' \
    -e '/^[[:space:]]*ksu_syscall_hook_manager_exit();$/d' \
    "$FINASU_INIT"

  # 1b) 补回 lsm hook 退出调用（补丁删除了它，而该模块已恢复）
  if ! grep -q 'ksu_lsm_hook_exit();' "$FINASU_INIT"; then
    sed -i 's|^[[:space:]]*ksu_selinux_hide_exit();$|    ksu_lsm_hook_exit();\n    ksu_selinux_hide_exit();|' "$FINASU_INIT"
  fi

  # 3) ksu_app_profile_init 已被补丁从 app_profile.c/h 整体删除，去掉残留调用
  if ! grep -q 'void __init ksu_app_profile_init(' "$FINASU_KSU/policy/app_profile.c"; then
    sed -i '/^[[:space:]]*ksu_app_profile_init();$/d' "$FINASU_INIT"
  fi

  # 0e2) 补丁 hunk（@@ -26 区块）在新版 FinaSU 上 reject 时，四个 static key 定义丢失，
  #      而 ksud_integration/sucompat 的调用点还在 → 编译期 undeclared identifier。
  if [ -f "$FINASU_KSI" ]; then
    for KEY in ksu_is_init_rc_hook_enabled ksu_is_input_hook_enabled is_init_second_stage_not_executed is_first_zygote; do
      if ! grep -q "DEFINE_STATIC_KEY_TRUE($KEY)" "$FINASU_KSI" &&
        ! grep -rq "DEFINE_STATIC_KEY_TRUE($KEY)" "$FINASU_KSU" --include="*.c" --include="*.h" &&
        grep -q "$KEY" "$FINASU_KSI"; then
        sed -i "s|^#include \"hook/syscall_event_bridge.h\"$|#include \"hook/syscall_event_bridge.h\"\n#include \"linux/jump_label.h\"\n\nDEFINE_STATIC_KEY_TRUE($KEY);|" "$FINASU_KSI"
      fi
    done
    # 跳转标签定义存在但 jump_label 头缺失时补上（上游补丁的定义 hunk 不带 include）
    if grep -q 'DEFINE_STATIC_KEY_TRUE' "$FINASU_KSI" &&
       ! grep -q 'jump_label' "$FINASU_KSI"; then
      sed -i 's|^#include "hook/syscall_event_bridge.h"$|#include "hook/syscall_event_bridge.h"\n#include "linux/jump_label.h"|' "$FINASU_KSI"
    fi
  fi

  # 2) 恢复 ksu_late_loaded / ksu_bundled（补丁从 ksu.h 与 init.c 删除，
  #    但 FinaSU 的 dispatch / selinux_hide / ksud_integration 仍在使用）
  if ! grep -q 'extern bool ksu_late_loaded;' "$FINASU_KSU_H"; then
    sed -i 's|^extern bool ksu_no_custom_rc;$|extern bool ksu_no_custom_rc;\nextern bool ksu_late_loaded;\nextern bool ksu_bundled;|' "$FINASU_KSU_H"
  fi
  if ! grep -q '^bool ksu_late_loaded;' "$FINASU_INIT"; then
    sed -i 's|^struct cred \*ksu_cred;$|struct cred *ksu_cred;\n\nbool ksu_late_loaded;\n\n#ifdef MODULE\nbool ksu_bundled = false;\nmodule_param_named(bundled, ksu_bundled, bool, 0);\n#endif|' "$FINASU_INIT"
  fi

  # 4a) 补齐新架构初始化函数的头文件声明
  if ! grep -q '#include "feature/sucompat.h"' "$FINASU_INIT"; then
    sed -i 's|^#include "feature/avc_spoof.h"$|#include "feature/avc_spoof.h"\n#include "feature/sucompat.h"\n#include "hook/setuid_hook.h"|' "$FINASU_INIT"
  fi

  # 4a2) 补回 lsm_hook 头文件（补丁删除了该 include，而调用已恢复）
  if ! grep -q '#include "hook/lsm_hook.h"' "$FINASU_INIT"; then
    sed -i 's|^#include "hook/setuid_hook.h"$|#include "hook/setuid_hook.h"\n#include "hook/lsm_hook.h"|' "$FINASU_INIT"
  fi

  # 4a3) sucompat.c：40c97e24 起 userspace_stack_buffer 移入 include/util.h，
  #      补丁/适配层重写的 include 块可能丢掉该 include，而 ksud_user_path 等仍调用它
  FINASU_SUCOMPAT="$FINASU_KSU/feature/sucompat.c"
  if [ -f "$FINASU_SUCOMPAT" ] && grep -q 'userspace_stack_buffer(' "$FINASU_SUCOMPAT" &&
    ! grep -q '#include "util.h"' "$FINASU_SUCOMPAT" && grep -q 'userspace_stack_buffer' "$FINASU_KSU/include/util.h" 2>/dev/null; then
    sed -i 's|^#include "feature/sucompat.h"$|#include "feature/sucompat.h"\n#include "util.h"|' "$FINASU_SUCOMPAT"
  fi

  # 4b) SUSFS 初始化（补丁已在 init.c 顶部加入 susfs.h 头文件）
  if ! grep -q 'susfs_init();' "$FINASU_INIT"; then
    sed -i 's|^[[:space:]]*ksu_feature_init();$|#ifdef CONFIG_KSU_SUSFS\n    susfs_init();\n#endif // #ifdef CONFIG_KSU_SUSFS\n    ksu_feature_init();|' "$FINASU_INIT"
  fi

  # 4c) 原先由 hook/syscall_hook_manager.c 代调用的初始化，改为 init.c 直接调用
  if ! grep -q 'ksu_sucompat_init();' "$FINASU_INIT"; then
    sed -i 's|^[[:space:]]*ksu_supercalls_init();$|    ksu_supercalls_init();\n\n    ksu_sucompat_init();\n\n    ksu_setuid_hook_init();|' "$FINASU_INIT"
  fi

  # 5) 部分应用的补丁会残留少量 unused 代码（如 selinux_hide.c），
  #    GKI 的 -Werror 下放行该告警类别，避免遗留代码阻断编译。
  #    必须逐个用 $(call cc-option, ...) 探测：老内核（如 5.10）的 clang 不认识
  #    unused-but-set-variable，而 KBUILD 默认带 -Werror=unknown-warning-option，
  #    直接写 -Wno-error=unused-but-set-variable 会被当作未知告警选项 → 编译失败：
  #      drivers/kernelsu/core/init.o: unknown warning option '-Werror=unused-but-set-variable'
  #    cc-option 探测后，不支持的告警会被自动丢弃（5.15/6.6 的较新 clang 仍会保留）。
  if ! grep -q 'Wno-error=unused-variable' "$FINASU_KSU/Kbuild"; then
    cat >>"$FINASU_KSU/Kbuild" <<'KSU_KBUILD_EOF'

# FinaSU: SUSFS 补丁部分应用后的残留代码允许 unused 类告警。
# 用 cc-option 探测，避免把编译器不认识的告警选项在 -Werror=unknown-warning-option 下变成硬错误。
ccflags-y += $(call cc-option,-Wno-error=unused-variable) \
             $(call cc-option,-Wno-error=unused-function) \
             $(call cc-option,-Wno-error=unused-but-set-variable) \
             $(call cc-option,-Wno-error=unused-const-variable)
KSU_KBUILD_EOF
  fi

  # selinux_hide 形态检测：新形态（preview1+ 无 fake_state）需跳过 fake_state 校验
  NEW_MODEL=0
  if [ -f "$FINASU_SELINUX_HIDE" ] && ! grep -q 'fake_state' "$FINASU_SELINUX_HIDE"; then
    NEW_MODEL=1
  fi

  # 结果校验，防止上游代码结构变化后静默失效
  if ! grep -q 'susfs_init();' "$FINASU_INIT" ||
    ! grep -q 'ksu_sucompat_init();' "$FINASU_INIT" ||
    ! grep -q 'ksu_setuid_hook_init();' "$FINASU_INIT" ||
    ! grep -q 'ksu_init_symbol_resolver();' "$FINASU_INIT" ||
    ! grep -q 'ksu_lsm_hook_init();' "$FINASU_INIT" ||
    ! grep -q 'ksu_lsm_hook_exit();' "$FINASU_INIT" ||
    ! grep -q '#include "hook/lsm_hook.h"' "$FINASU_INIT" ||
    ! grep -q '^bool ksu_late_loaded;' "$FINASU_INIT" ||
    ! { ! grep -q 'userspace_stack_buffer(' "$FINASU_KSU/feature/sucompat.c" 2>/dev/null ||
      grep -q '#include "util.h"' "$FINASU_KSU/feature/sucompat.c" 2>/dev/null ||
      ! grep -q 'userspace_stack_buffer' "$FINASU_KSU/include/util.h" 2>/dev/null; } ||
    ! grep -q 'extern bool ksu_late_loaded;' "$FINASU_KSU_H" ||
    ! grep -q 'hook/lsm_hook.o' "$FINASU_KSU/Kbuild" ||
    ! grep -q 'infra/symbol_resolver.o' "$FINASU_KSU/Kbuild" ||
    ! grep -q '^bool ksu_selinux_hide_enabled ' "$FINASU_SELINUX_HIDE" ||
    ! grep -q '^bool ksu_selinux_hide_running ' "$FINASU_SELINUX_HIDE" ||
    ! { [ "${NEW_MODEL:-0}" = 1 ] || grep -q '^struct selinux_state fake_state;' "$FINASU_SELINUX_HIDE"; } ||
    ! grep -q '^DEFINE_STATIC_KEY_FALSE(fake_status_initialize_key);' "$FINASU_SELINUX_HIDE" ||
    ! grep -q '^struct page \*fake_status = NULL;' "$FINASU_SELINUX_HIDE" ||
    ! grep -q '^void initialize_fake_status(void)$' "$FINASU_SELINUX_HIDE" ||
    ! grep -q '^int security_context_to_sid_with_policy' "$FINASU_SELINUX_HIDE" ||
    ! grep -q '^int security_sid_to_context_with_policy' "$FINASU_SELINUX_HIDE" ||
    ! grep -q '^void security_compute_av_user_with_policy' "$FINASU_SELINUX_HIDE" ||
    ! grep -q '^int ksu_handle_execveat_ksud(int \*fd, struct filename \*\*filename_ptr,' "$FINASU_KSI"; then
    echo "::error::FinaSU 适配修复失败，代码结构可能已变化" >&2
    exit 1
  fi
  if grep -qE '^static (int|void) (__nocfi )?security_(context_to_sid_with_policy|sid_to_context_with_policy|compute_av_user_with_policy)' "$FINASU_SELINUX_HIDE"; then
    echo "::error::FinaSU selinux_hide.c 的 security_*_with_policy 仍未全局化（6.6 会链接失败）" >&2
    exit 1
  fi
  if grep -qE 'ksu_syscall_hook_init\(\)|ksu_syscall_hook_manager_(init|exit)\(\)' "$FINASU_INIT"; then
    echo "::error::FinaSU init.c 仍存在指向已移除模块的调用" >&2
    exit 1
  fi
fi

echo "FinaSU SUSFS 内核侧集成补丁应用完成"
