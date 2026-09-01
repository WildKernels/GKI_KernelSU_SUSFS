# Third-Party Notices — GKI_KernelSU_SUSFS

This file lists only code cloned/patched at build and shipped in boot.img/AnyKernel3.zip.
Each component keeps its own license. Used at = where in my code it is cloned/applied (not vendored — fetched in CI via .github/actions/* with pinned commits per release).

| Component | Upstream / link | License | Used at (where in my code) |
|-----------|-----------------|---------|-----------------------------|
| KernelSU | https://github.com/tiann/KernelSU | GPL-3.0 | `.github/actions/root-setup` (flavor `kernelsu`, pinned `root_commit`) → `kernel/drivers/kernelsu` |
| KernelSU-Next | https://github.com/KernelSU-Next/KernelSU-Next | GPL-3.0 | `.github/actions/root-setup` (flavor `next`, pinned `root_commit`) → `kernel/drivers/kernelsu` |
| ReSukiSU | https://github.com/ReSukiSU/ReSukiSU | GPL-3.0 | `.github/actions/root-setup` (flavor `resukisu`, pinned `root_commit`) → `kernel/drivers/kernelsu` |
| KernelSU-Next SUSFS fork (pershoot) | https://github.com/pershoot/KernelSU-Next (branch `dev-susfs`) | GPL-3.0 | `.github/actions/root-setup` + `.github/actions/susfs` when building Next+SUSFS (same path as above) |
| susfs4ksu | https://gitlab.com/simonpunk/susfs4ksu | GPL-3.0-or-later | `.github/actions/susfs-setup` + `.github/actions/susfs` (clones `gki-<version>` branch, pinned `susfs_commit`) → patches under `kernel/` |
| NoMount | https://github.com/maxsteeel/nomount | GPL-3.0 | `.github/actions/nomount-metamodule` (pinned `nomount_commit`) → built metamodule `NoMount-*.zip` |
| kernel_patches (ptrace fix, unicode fix, NTSync, perf, bbg, etc) | https://github.com/WildKernels/kernel_patches | GPL-2.0 (patches to GPL-2.0 kernel; includes ack to https://github.com/backslashxx/msm8953-kernel for maphide) | `.github/actions/setup-build-environment` (pinned `kernel_patches_commit`) → `kernel_patches/` + applied via `.github/actions/{ptrace,unicode-fix,ntsync,performance,bbg,networking,btf}` |
| Baseband Guard (inside kernel_patches) | https://github.com/vc-teahouse/Baseband-guard | GPL-2.0 | `kernel_patches/common/bbg/` → applied via `.github/actions/bbg` |
| AnyKernel3 | https://github.com/WildKernels/AnyKernel3 (fork of https://github.com/osm0sis/AnyKernel3, branch `gki-2.0`) | BSD-3-like (AnyKernel license, Copyright 2019 Chris Renshaw) | `.github/actions/setup-build-environment` (pinned `anykernel3_commit`) → `AnyKernel3/` → shipped as `AnyKernel3.zip` |
| AnyKernel3 — magiskboot / magiskpolicy binaries | https://github.com/topjohnwu/Magisk (via AnyKernel3) | GPL-3.0 | `AnyKernel3/tools/` / `AnyKernel3/bin/` (included binaries only; note in AnyKernel3/LICENSE: "Included Binary Licenses: magiskboot, magiskpolicy (Magisk): GPLv3+") |
| DroidSpaces-OSS | https://github.com/ravindu644/Droidspaces-OSS | GPL-3.0 | `.github/actions/droidspaces` (pinned `droidspaces_commit`) → patches `kernel/common/ipc/*` + Kconfig |

Notes not shipped in the binary (so not in this table): `sidex15/susfs4ksu-module` (AGPL-3.0, user installs post-flash, see docs/post-install.md), `backslashxx/mountify` (Unlicense, docs only), `5ec1cff/KernelSU` / Sultan / boot-fix (other repos), doc attribution `kernelsu.org` (see `docs/installation.md`).

Source per release: see release body for pinned commits (root_commit, susfs_commit, kernel_patches_commit, anykernel3_commit, nomount_commit, droidspaces_commit) + KERNEL_SOURCE_COMMIT from .github/actions/download-kernel.
