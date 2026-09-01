# Installation

> [!CAUTION]
> Wild Kernels is not responsible for bricked devices or damage. By flashing, you assume all risk. Back up your data and understand the risks before flashing.

## Choose your method

| Method | When to use | Requires root | Guide |
|--------|-------------|---------------|-------|
| **Kernel Flasher** | Upgrading with root already available, no PC needed | Yes | [kernelflasher.md](kernelflasher.md) |
| **magiskboot** | When you want to flash a pre-patched `boot.img` directly (no pre-rooted setup required) | No | [magiskboot.md](magiskboot.md) |

## Prerequisites

- [ ] GKI 2.0 device with an unlocked bootloader
- [ ] Full backup (at minimal the `boot` partition or have a stock unmodified `boot.img`)
- [ ] Correct AnyKernel3 ZIP for your kernel version from [Releases](https://github.com/WildKernels/GKI_KernelSU_SUSFS/releases)

### Supported versions

Only GKI 2.0 is supported — check marks show builds provided by this project:

| Pre-GKI | GKI 1.0 | GKI 2.0 |
|---------|---------|---------|
| 3.10.x | 5.4.x | 5.10.x-android12 ✓ |
| 3.18.x | | 5.10.x-android13 ✓ |
| 4.4.x | | 5.15.x-android13 ✓ |
| 4.9.x | | 5.15.x-android14 ✓ |
| 4.14.x | | 6.1.x-android14 ✓ |
| 4.19.x | | 6.6.x-android15 ✓ |
| | | 6.12.x-android16 ✓ |

For Pre-GKI or GKI 1.0 kernels, contact [@TheWildJames](https://t.me/TheWildJames) to discuss possiblities.

> [!IMPORTANT]
> Match by the full kernel version (e.g., `6.1.x-androidXX`) — your device's Android version and the `androidXX` in the kernel version are not necessarily the same. For example, as of writing, a Google Pixel 8 is on `6.1.157-android14` while the system Android is 17.

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
