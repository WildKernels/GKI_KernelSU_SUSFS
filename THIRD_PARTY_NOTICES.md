# Third-Party Notices — GKI_KernelSU_SUSFS

> [!NOTE]
> This file lists third-party code fetched during CI and included in the build's output zip(s). None of it is vendored in this repo — each dependency is pulled fresh at build time and retains its own original license.

| Component | Upstream | License |
|-----------|----------|---------|
| Kernel Source | [kernel/common](https://android.googlesource.com/kernel/common) | GPL-2.0 |
| KernelSU | [tiann/KernelSU](https://github.com/tiann/KernelSU) | GPL-3.0 |
| KernelSU-Next | [KernelSU-Next/KernelSU-Next](https://github.com/KernelSU-Next/KernelSU-Next) | GPL-3.0 |
| ReSukiSU | [ReSukiSU/ReSukiSU](https://github.com/ReSukiSU/ReSukiSU) | GPL-3.0 |
| KSU-Next SUSFS | [pershoot/KernelSU-Next](https://github.com/pershoot/KernelSU-Next) | GPL-3.0 |
| susfs4ksu | [simonpunk/susfs4ksu](https://gitlab.com/simonpunk/susfs4ksu) | GPL-3.0+ |
| NoMount | [maxsteeel/nomount](https://github.com/maxsteeel/nomount) | GPL-3.0 |
| kernel_patches | [WildKernels/kernel_patches](https://github.com/WildKernels/kernel_patches) | GPL-2.0 |
| Baseband Guard | [vc-teahouse/Baseband-guard](https://github.com/vc-teahouse/Baseband-guard) | GPL-2.0 |
| AnyKernel3 | [WildKernels/AnyKernel3](https://github.com/WildKernels/AnyKernel3) | BSD |
| magiskboot | [topjohnwu/Magisk](https://github.com/topjohnwu/Magisk) via AnyKernel3 | GPL-3.0 |
| DroidSpaces | [ravindu644/Droidspaces-OSS](https://github.com/ravindu644/Droidspaces-OSS) | GPL-3.0 |

<details>
<summary> About magiskboot binaries</summary>

`magiskboot` / `magiskpolicy` are prebuilt binaries bundled inside `AnyKernel3/tools/`. Source at [topjohnwu/Magisk](https://github.com/topjohnwu/Magisk) (GPL-3.0). They are not separate clones — shipped only via AnyKernel3.

</details>

> [!IMPORTANT]
> If we have used your code and not credited you correctly, or have listed the wrong license, please let us know — open an issue or reach out and we'll fix it promptly. No omission is intentional; we want to credit everyone properly.
