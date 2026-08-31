# Third-Party Notices — GKI_KernelSU_SUSFS (and all WildKernels kernel builds)

This repository builds a Linux kernel (GPL-2.0-only) with additional components
that retain their own licenses. The **kernel source files** (from Google's
`kernel/common` GKI) are licensed under **GPL-2.0-only**. Files added by the
root/hiding/mount projects below are licensed under the terms noted.
The **combined binary** you flash is a derivative of all of them — distribution
must satisfy *both* GPL-2.0 (kernel) and the applicable GPL-3.0/AGPL/Unlicense
terms for the embedded components. Source for every component is referenced
below and pinned by commit in `.github/workflows/` (`verified` mode) and/or
releases.

> This file is the canonical attribution required by those licenses and by
> GitHub's licensing guidance. Keep it with any redistribution.

## Kernel base

| Component | Upstream | License | Notes |
|-----------|----------|---------|-------|
| Linux GKI (`kernel/common`, android12-5.10 through android16-6.12) | Google / Linux kernel | **GPL-2.0-only** (`GPL-2.0`) | Fetched by `kernels/sync_kernel.sh`. `COPYING` in kernel tree is GPL-2.0. |

## Root implementations (pick one per build)

| Component | Upstream | License | Notes |
|-----------|----------|---------|-------|
| KernelSU | [tiann/KernelSU](https://github.com/tiann/KernelSU) | GPL-3.0 | Original by tiann. `LICENSE` = GPL-3.0 in that repo. |
| KernelSU-Next | [KernelSU-Next/KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next) | GPL-3.0 | By rifsxd. |
| KernelSU-Next SUSFS fork | [pershoot/KernelSU-Next](https://github.com/pershoot/KernelSU-Next) (`dev-susfs`) | GPL-3.0 | SUSFS-integrated tip used for SUSFS builds. |
| ReSukiSU | [ReSukiSU/ReSukiSU](https://github.com/ReSukiSU/ReSukiSU) | GPL-3.0 | Fork of SukiSU. |
| Magic-KSU | [5ec1cff/KernelSU](https://github.com/5ec1cff/KernelSU) | GPL-3.0 | Credited in README. |

Source for the selected flavor is checked out in-CI from the exact commit
recorded in the workflow dispatch (`ksu_branch`/`root_commit`) and embedded
under `KernelSU/` at build time.

## Root hiding

| Component | Upstream | License | Notes |
|-----------|----------|---------|-------|
| susfs4ksu (kernel patches + `ksu_module_susfs` + `ksu_susfs`) | [simonpunk/susfs4ksu](https://gitlab.com/simonpunk/susfs4ksu) | **GPL-3.0-or-later** (`GPL-3.0+`) | GitLab `GET /projects/simonpunk%2Fsusfs4ksu` → `license.key=gpl-3.0+`. `LICENSE` = GPL-3.0 in every `gki-*` branch. |
| susfs4ksu-module (userspace) | [sidex15/susfs4ksu-module](https://github.com/sidex15/susfs4ksu-module) | **AGPL-3.0** | Recommended module. If redistributed, AGPL §13 source offer applies; linking to upstream satisfies it when unmodified. |
| Ptrace Leak Fix | [WildKernels/kernel_patches/gki_ptrace.patch](https://github.com/WildKernels/kernel_patches/blob/main/gki_ptrace.patch) | GPL-2.0 | Internal to hiding. |
| Unicode Fix | [WildKernels/kernel_patches/common/unicode_bypass_fix_*.patch](https://github.com/WildKernels/kernel_patches/tree/main/common) | GPL-2.0 | Internal to hiding. |

## Mount / metamodule

| Component | Upstream | License | Notes |
|-----------|----------|---------|-------|
| NoMount | [maxsteeel/nomount](https://github.com/maxsteeel/nomount) | GPL-3.0 | Metamodule. |
| Mountify | [backslashxx/mountify](https://github.com/backslashxx/mountify) | **Unlicense** (public domain) | OverlayFS global mount. No conditions; attribution here is courtesy. |

## Security

| Component | Upstream | License | Notes |
|-----------|----------|---------|-------|
| Baseband Guard (BBG) | [vc-teahouse/Baseband-guard](https://github.com/vc-teahouse/Baseband-guard) | GPL-2.0 | LSM under `kernel_patches/common/bbg`. |

## Container / performance / networking

| Component | Upstream | License | Notes |
|-----------|----------|---------|-------|
| DroidSpaces-OSS | [ravindu644/Droidspaces-OSS](https://github.com/ravindu644/Droidspaces-OSS) | GPL-3.0 | Container runtime. |
| NTSync, BBRv3, perf tuning, bbg, BPF, etc | [WildKernels/kernel_patches](https://github.com/WildKernels/kernel_patches) | GPL-2.0 (kernel patches) + ack to [backslashxx maphide patches](https://github.com/backslashxx/msm8953-kernel) | Patches are derivative of GPL-2.0 kernel; same license. |
| Sultan kernel base (Pixel) | [kerneltoast](https://github.com/kerneltoast) | GPL-2.0 | Used by `Sultan_KernelSU_SUSFS`. |
| Device boot fix | [Anything-at-25-00 commit 2476d26](https://github.com/Anything-at-25-00/android_kernel_common_android12-5.10/commit/2476d262b597fe8af82cfb7aaf96676f51c6b4ed) | GPL-2.0 | One-off cherry-pick. |

## Flash tooling

| Component | Upstream | License | Notes |
|-----------|----------|---------|-------|
| AnyKernel3 | [osm0sis/AnyKernel3](https://github.com/osm0sis/AnyKernel3) (fork [WildKernels/AnyKernel3](https://github.com/WildKernels/AnyKernel3)) | **BSD-3-like (AnyKernel license)** — see `AnyKernel3/LICENSE` | Copyright © 2019 Chris Renshaw (osm0sis). Keep his `LICENSE` verbatim. Conditions: retain copyright + disclaimer, no endorsement. |
| └ bundled `magiskboot` / `magiskpolicy` | [topjohnwu/Magisk](https://github.com/topjohnwu/Magisk) via AnyKernel3 | GPL-3.0 | Included binaries are GPL-3.0 even though AK3 scripts are BSD-like. Source via Magisk repo. |

## Documentation

| Component | Upstream | License | Notes |
|-----------|----------|---------|-------|
| Installation guide portions | [kernelsu.org](https://kernelsu.org/) | Docs are CC/MIT-ish; attributed in `docs/installation.md` | Note in that file: "Portions of this documentation are adapted from the official KernelSU documentation (kernelsu.org)." |

---

## License texts

- `LICENSE` at this repo's root is **GPL-2.0** (the kernel's license). It covers all kernel files and WildKernels' own patches.
- Each component above remains under its own license file in its upstream repo (linked). For convenience, the canonical texts are:
  - GPL-2.0: https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt — also at `templates/LICENSE.GPL-2.0`
  - GPL-3.0: https://www.gnu.org/licenses/gpl-3.0.txt
  - GPL-3.0+: same as GPL-3.0 with "or later" clause (SUSFS)
  - AGPL-3.0: https://www.gnu.org/licenses/agpl-3.0.txt (susfs module)
  - Unlicense: https://unlicense.org/ (mountify)
  - AnyKernel BSD-like: verbatim in `WildKernels/AnyKernel3/LICENSE`

### Required notices (verbatim excerpts)

**AnyKernel3 (BSD-like):**
> Copyright (c) 2019 Chris Renshaw (osm0sis @ xda-developers). Redistributions must retain the above copyright notice, this list of conditions and the following disclaimer. Neither the name of the copyright holder nor contributors may be used to endorse derived products without permission.

**Unlicense (mountify):**
> This is free and unencumbered software released into the public domain.

**GPL family:** see full texts above. GPL-3.0/AGPL-3.0 require providing Corresponding Source with any binary distribution — this repo does so via public workflow pins + release artifacts + upstream links. For AGPL module, network use may trigger source offer.

---

## Source availability (how to comply)

Every release's workflow log lists the exact commits used (`verified` pins in `.github/workflows/*.yml`). To reproduce:
1. This repo's commit + `kernels/sync_kernel.sh` revision → GKI base
2. `root_flavor`/`root_commit`/`susfs_commit`/`anykernel3_commit`/`nomount_commit`/`kernel_patches_commit`/`droidspaces_commit` inputs → each component
3. Kernel patches: `WildKernels/kernel_patches` at the pinned commit
4. AnyKernel3: `WildKernels/AnyKernel3` at the pinned commit
5. SUSFS: `simonpunk/susfs4ksu` (GitLab) at the pinned branch+commit + `sidex15/susfs4ksu-module`

If you redistribute the built `boot.img`/`AnyKernel3.zip`, you must also make this source available (linking to these repos/commits satisfies GPL when unmodified; serve a snapshot if you modify them).

---

*Last updated: 2026-08-31. Not legal advice — review with counsel if needed.*
