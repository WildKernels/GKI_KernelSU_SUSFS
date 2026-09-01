# Kernel Features - Documentation Index

Per-feature documentation for the GKI2 kernels built from this repository.

*Last updated: 2026-08-30*

<details>
<summary><b> Table of Contents</b></summary>

- [ Root Implementations](#-root-implementations)
- [ Root Hiding](#-root-hiding)
- [ Meta Module](#-meta-module)
- [ Security](#-security)
- [ Networking](#-networking)
- [ Debugging, Tracing & BPF](#-debugging-tracing--bpf)
- [ Performance](#-performance)
- [ Container Runtime](#-container-runtime)

</details>

---

## Root Implementations

Kernel-based su and root access management for Android.

| Root Flavor | Description | Source |
|-------------|-------------|--------|
| KernelSU | Original implementation by [tiann](https://github.com/tiann) — the foundation from which all other variants are derived. | [tiann/KernelSU](https://github.com/tiann/KernelSU) |
| KernelSU-Next | Created by [rifsxd](https://github.com/rifsxd). SUSFS-integrated builds sourced from pershoot. | [KernelSU-Next/KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next) · [pershoot/KernelSU-Next](https://github.com/pershoot/KernelSU-Next) |
| ReSukiSU | Fork of SukiSU, also has its own SUSFS-integrated branch. | [ReSukiSU/ReSukiSU](https://github.com/ReSukiSU/ReSukiSU) |

---

## Root Hiding

| Feature | Description | Source |
|---------|-------------|--------|
| susfs4ksu | Root-hiding add-on for KernelSU using kernel patches and a userspace module. Recommended module: [sidex15/susfs4ksu-module](https://github.com/sidex15/susfs4ksu-module). | [simonpunk/susfs4ksu](https://gitlab.com/simonpunk/susfs4ksu) |
| Ptrace Leak Fix | Fixes ptrace info leak on kernels older than 5.16. Internal to root hiding. | [patch](https://github.com/WildKernels/kernel_patches/blob/main/gki_ptrace.patch) |
| Unicode Fix | Prevents path traversal via non-printable Unicode (experimental). Internal to root hiding. | [patch 6.1-](https://github.com/WildKernels/kernel_patches/blob/main/common/unicode_bypass_fix_6.1-.patch) · [patch 6.1+](https://github.com/WildKernels/kernel_patches/blob/main/common/unicode_bypass_fix_6.1+.patch) |

---

## Meta Module

| Module | Description | Source |
|--------|-------------|--------|
| NoMount | Metamodule providing mount-related functionality alongside root implementations. | [maxsteeel/nomount](https://github.com/maxsteeel/nomount) |
| Mountify | Globally mounted modules via OverlayFS. | [backslashxx/mountify](https://github.com/backslashxx/mountify) |

> [!NOTE]
> Only one is required if mounting modules.

<details>
<summary>Which one should I use?</summary>

- **NoMount** — recommended, bundled as `nomount-metamodule` in CI.
- **Mountify** — alternative OverlayFS approach, not bundled — install latest compatible module manually.

</details>

---

## Security

| Feature | Description | Source |
|---------|-------------|--------|
| Baseband Guard | Lightweight LSM blocking unauthorized writes to critical partitions and device nodes. | [vc-teahouse/Baseband-guard](https://github.com/vc-teahouse/Baseband-guard) |

---

## Networking

| Feature | Description | Source |
|---------|-------------|--------|
| TCP Congestion Control | BBRv1, BBRv3, CUBIC, BIC, Westwood, HTCP | `CONFIG_TCP_CONG_BBR` / `CONFIG_TCP_CONG_CUBIC` etc |
| WireGuard | Built-in VPN support | `CONFIG_WIREGUARD` |
| IP Set / IPv6 NAT | Advanced firewall capabilities | `CONFIG_IP_SET` / `CONFIG_IP6_NF_NAT` |
| Conntrack / connmark | Connection marking for packet classification | `CONFIG_NF_CONNTRACK` / `CONFIG_NET_ACT_CONNMARK` |
| CIFS | SMB/CIFS network filesystem | `CONFIG_CIFS` |
| TTL Target | Network packet manipulation | `CONFIG_IP_NF_TARGET_TTL` / `CONFIG_IP6_NF_TARGET_HL` |

---

## Debugging, Tracing & BPF

| Feature | Description | Source |
|---------|-------------|--------|
| BTF / eBPF / FUSE-BPF | BPF Type Format, extended BPF, FUSE-BPF interaction | `CONFIG_DEBUG_INFO_BTF` / `CONFIG_BPF_SYSCALL` / `CONFIG_FUSE_BPF` |

---

## Performance

| Feature | Description | Source |
|---------|-------------|--------|
| NTSync | High-performance synchronization primitives compatible with Windows NT kernel API. | [WildKernels/kernel_patches](https://github.com/WildKernels/kernel_patches/tree/main/common/ntsync) |
| Performance Tuning | Kernel configuration and tuning options | [WildKernels/kernel_patches](https://github.com/WildKernels/kernel_patches/tree/main/common) |

---

## Container Runtime

| Feature | Description | Source |
|---------|-------------|--------|
| DroidSpaces-OSS | LXC-inspired container runtime for Android/Linux | [ravindu644/Droidspaces-OSS](https://github.com/ravindu644/Droidspaces-OSS) |

---

> [!TIP]
> **Installation** — see [Installation Guide](installation.md).
