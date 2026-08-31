<div align="center">

# Wild Kernels for Android

[![KernelSU](https://img.shields.io/badge/KernelSU-Supported-green)](https://kernelsu.org/)
[![susfs4ksu](https://img.shields.io/badge/susfs4ksu-Integrated-orange)](https://gitlab.com/simonpunk/susfs4ksu)

</div>

> [!CAUTION]
> Wild Kernels is **not responsible** for bricked devices, damaged hardware, or any issues that arise from using Wild Kernels.
>
> **Please** do thorough research and fully understand the features included in Wild Kernels before flashing!
>
> By flashing Wild Kernels, **YOU** are choosing to make these modifications. If something goes wrong, **do not blame Wild Kernels**!
>
> Please make sure to:
> - Back up your data
> - Understand the risks involved
>
> **Proceed at your own risk!**

---

## Our Projects

| Device | Repository |
|--------|------------|
| **Generic** | [GKI_KernelSU_SUSFS](https://github.com/WildKernels/GKI_KernelSU_SUSFS) |
| **Pixel** | [Sultan_KernelSU_SUSFS](https://github.com/WildKernels/Sultan_KernelSU_SUSFS) |
| **Samsung** | [Samsung_KernelSU_SUSFS](https://github.com/WildKernels/Samsung_KernelSU_SUSFS) |
| **OnePlus** | [OnePlus_KernelSU_SUSFS](https://github.com/WildKernels/OnePlus_KernelSU_SUSFS) |

---

## Features

- KernelSU / KernelSU-Next / ReSukiSU - root implementations
- susfs4ksu - root hiding (incl. Ptrace Leak Fix, Unicode Fix)
- NoMount / Mountify - mount metamodules
- Baseband Guard - partition protection
- Networking - WireGuard, BBR, IPSet, CIFS
- TMPFS - xattr / POSIX ACLs
- BPF - BTF / eBPF / FUSE-BPF
- Performance - incl. NTSync
- DroidSpaces - container runtime

Full documentation: [docs/features.md](docs/features.md)

---

## Installation

See **[Installation Guide](docs/installation.md)**.

---

## Credits

- **KernelSU**: Developed by [tiann](https://github.com/tiann/KernelSU)
- **KernelSU-Next**: Developed by [rifsxd](https://github.com/KernelSU-Next/KernelSU-Next)
- **KernelSU-Next SUSFS Fork**: Developed by [pershoot](https://github.com/pershoot/KernelSU-Next) (`dev-susfs` branch used for SUSFS builds)
- **ReSukiSU**: Developed by [ReSukiSU](https://github.com/ReSukiSU/ReSukiSU)
- **Magic-KSU**: Developed by [5ec1cff](https://github.com/5ec1cff/KernelSU)
- **SUSFS**: Developed by [simonpunk](https://gitlab.com/simonpunk/susfs4ksu)
- **SUSFS Module**: Developed by [sidex15](https://github.com/sidex15)
- **NoMount**: Developed by [maxsteeel](https://github.com/maxsteeel/nomount)
- **DroidSpaces-OSS**: Developed by [ravindu644](https://github.com/ravindu644/Droidspaces-OSS)
- **Baseband-guard (BBG)**: Developed by [vc-teahouse](https://github.com/vc-teahouse/Baseband-guard)
- **Kernel Patches**: Maintained by [WildKernels/kernel_patches](https://github.com/WildKernels/kernel_patches)
- **AnyKernel3**: Maintained by [WildKernels/AnyKernel3](https://github.com/WildKernels/AnyKernel3)
- **Sultan Kernels (Pixel)**: Developed by [kerneltoast](https://github.com/kerneltoast)
- **Device Boot Fix**: [Boot fix commit](https://github.com/Anything-at-25-00/android_kernel_common_android12-5.10/commit/2476d262b597fe8af82cfb7aaf96676f51c6b4ed) for fixing some devices not booting

Special thanks to the open-source community for their contributions!

---

## Community

<div align="center">

[![Telegram Group](https://img.shields.io/badge/Telegram-%40WildKernelsTG-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/WildKernelsTG)
[![Telegram DM](https://img.shields.io/badge/Telegram-%40TheWildJames-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/TheWildJames)

</div>

Need help? Open an issue in this repository or reach out on Telegram.

> **Note:** Please ask in the [WildKernelsTG group](https://t.me/WildKernelsTG) first for general issues. DMs to [@TheWildJames](https://t.me/TheWildJames) are always open — use for priority / very important, or if you just want to talk and learn.

---

## Special Thanks

**These amazing people help make this project possible!**

[![Contributors](https://contrib.rocks/image?repo=WildKernels/GKI_KernelSU_SUSFS)](https://github.com/WildKernels/GKI_KernelSU_SUSFS/graphs/contributors)

Have an idea or improvement in mind? Contributions are always welcome — feel free to open a pull request or share your thoughts!

---

## Donations

> **Kind note:** A donation is truly just a gift — not a payment for support, features, or priority. It doesn't unlock anything extra on our side and doesn't change how we help you; everyone gets the same community support whether you donate or not. Think of it as a kind “thank you” to help keep development going — not a transaction. If you do choose to give, we're genuinely grateful, but please never feel obligated.

- PayPal: [bauhd@outlook.com](mailto:bauhd@outlook.com)
- Card: <https://buy.stripe.com/5kQ28sdi08Nr0Xc2fU5os00>
- LTC: MVaN1ToSuks2cdK9mB3M8EHCfzQSyEMf6h
- BTC: 3BBXAMS4ZuCZwfbTXxWGczxHF4isymeyxG
- ETH: 0x2b9C846c84d58717e784458406235C09a834274e
- Patreon: <https://patreon.com/WildKernels>
