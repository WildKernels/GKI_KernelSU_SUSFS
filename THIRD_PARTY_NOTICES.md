# Third-Party Notices — GKI_KernelSU_SUSFS

This file lists Linux GKI and all code cloned at build and shipped in boot.img/AnyKernel3.zip.
Each keeps its own license. Not vendored — fetched in CI via `.github/actions/*` (pins per release).

| Component | Upstream | License | Used at |
|-----------|----------|---------|---------|
| Kernel Source | [kernel/common](https://android.googlesource.com/kernel/common) | GPL-2.0 | `download-kernel` |
| KernelSU | [tiann/KernelSU](https://github.com/tiann/KernelSU) | GPL-3.0 | `root-setup` (kernelsu) |
| KernelSU-Next | [KernelSU-Next/KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next) | GPL-3.0 | `root-setup` (next) |
| ReSukiSU | [ReSukiSU/ReSukiSU](https://github.com/ReSukiSU/ReSukiSU) | GPL-3.0 | `root-setup` (resukisu) |
| KSU-Next SUSFS | [pershoot/KernelSU-Next](https://github.com/pershoot/KernelSU-Next) `dev-susfs` | GPL-3.0 | `root-setup` + `susfs` |
| susfs4ksu | [simonpunk/susfs4ksu](https://gitlab.com/simonpunk/susfs4ksu) | GPL-3.0+ | `susfs` (`susfs_commit`) |
| NoMount | [maxsteeel/nomount](https://github.com/maxsteeel/nomount) | GPL-3.0 | `nomount-metamodule` |
| kernel_patches | [WildKernels/kernel_patches](https://github.com/WildKernels/kernel_patches) | GPL-2.0 | `setup-build-environment` |
| Baseband Guard | [vc-teahouse/Baseband-guard](https://github.com/vc-teahouse/Baseband-guard) | GPL-2.0 | `bbg` (`kernel_patches/common/bbg`) |
| AnyKernel3 | [WildKernels/AnyKernel3](https://github.com/WildKernels/AnyKernel3) | BSD | `setup-build-environment` → `AnyKernel3.zip` |
| magiskboot | [topjohnwu/Magisk](https://github.com/topjohnwu/Magisk) via AnyKernel3 | GPL-3.0 | `AnyKernel3/tools` (binaries only) |
| DroidSpaces | [ravindu644/Droidspaces-OSS](https://github.com/ravindu644/Droidspaces-OSS) | GPL-3.0 | `droidspaces` |

---

If we have used your code and not credited you correctly, or have listed the wrong license, please let us know — open an issue or reach out and we'll fix it promptly. No omission is intentional; we want to credit everyone properly.
