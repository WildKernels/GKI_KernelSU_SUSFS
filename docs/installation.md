# Installation

> [!CAUTION]
> Flashing a kernel can brick your device and will void your warranty. Make a full backup (boot partition at minimum) before proceeding.

## Choose your method

| Method | When to use | Requires root | Guide |
|--------|-------------|---------------|-------|
| **Kernel Flasher** | Upgrading with root already available, no PC needed | Yes | [kernelflasher.md](kernelflasher.md) |
| **magiskboot** | When you want to flash a pre-patched `boot.img` directly (no pre-rooted setup required) | No | [magiskboot.md](magiskboot.md) |

> [!TIP]
> Not sure? **Kernel Flasher** is easiest if you already have root. Otherwise use **magiskboot** from a PC.

## Prerequisites

- [ ] Unlocked bootloader, GKI 2.0 device (5.10+)
- [ ] Full backup (at least `boot` partition)
- [ ] Correct AnyKernel3 ZIP for your kernel version from [Releases](https://github.com/WildKernels/GKI_KernelSU_SUSFS/releases)

### Supported versions

Only GKI 2.0 is supported — check marks show builds provided by this project:

| Pre-GKI | GKI 1.0 | GKI 2.0 |
|---------|---------|---------|
| 3.10 x | 5.4 x | 5.10 ✓ |
| 3.18 x | | 5.15 ✓ |
| 4.4 x | | 6.1 ✓ |
| 4.9 x | | 6.6 ✓ |
| 4.14 x | | 6.12 ✓ |
| 4.19 x | | |

For Pre-GKI or GKI 1.0 kernels, contact [@TheWildJames](https://t.me/TheWildJames) to discuss availability.

## After flashing

See [Post-Install — Verify & Finish Setup](post-install.md) for manager install, SUSFS module, and verification steps.

---

## Other methods

<details>
<summary>Alternative flashing tools</summary>

- [PixelFlasher](https://github.com/badabing2005/PixelFlasher)
- [Franco Kernel Manager](https://play.google.com/store/apps/details?id=com.franco.kernel&hl=en_CA&pli=1)

</details>

---

> [!NOTE]
> Portions of this documentation are adapted from the official [KernelSU documentation](https://kernelsu.org/).

See also: [Kernel Features Documentation](features.md)
