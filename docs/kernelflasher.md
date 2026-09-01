# Install with Kernel Flasher

> [!NOTE]
> This method is more convenient when upgrading KernelSU and can be done without a computer. Make a backup first.

> [!CAUTION]
> Wild Kernels is not responsible for bricked devices or damage. By flashing, you assume all risk. Back up your data and understand the risks before flashing.

## Prerequisites

- [ ] Device with unlocked bootloader running a GKI2 kernel 5.10+
- [ ] Root access already granted to the flashing app

## Steps

1. **Download the AnyKernel3 ZIP** that matches your kernel version (e.g., `6.1.x-androidXX`) from the latest [Releases](https://github.com/WildKernels/GKI_KernelSU_SUSFS/releases) page.
2. **Open the Kernel Flasher app**, grant necessary root permissions when prompted.
3. **Select the AnyKernel3 ZIP** you downloaded and flash. Do not interrupt the process.
4. **Reboot** when prompted and verify KernelSU manager shows the expected version.

> [!NOTE]
> Match by the full kernel version (e.g., `6.1.x-androidXX`) — your device's Android version and the `androidXX` in the kernel version are not necessarily the same. For example, as of writing, a Google Pixel 8 is on `6.1.157-android14` while the system Android is 17.

> [!TIP]
> This requires the flashing app to have root permissions. On first install from stock (no root yet), flash via recovery or fastboot instead, then use this method for subsequent upgrades.

## Supported flashing apps

| App | Notes |
|-----|-------|
| [Kernel Flasher](https://github.com/fatalcoder524/KernelFlasher) | Recommended, actively maintained |

> [!WARNING]
> Requires root to flash a kernel from within Android.

## After flashing

See [Post-Install — Verify & Finish Setup](post-install.md) for manager install, SUSFS module, and verification.

## Troubleshooting

<details>
<summary>Common issues</summary>

- **Bootloop** — restore a stock boot.img via fastboot/recovery.
- **Manager and kernel version do not match (e.g. 31000 != 32000)** — for best compatibility ensure both match. Install the latest kernel and manager linked in the release and reboot fully.

</details>

---

Related: [Installation Overview](installation.md) · [Patch boot.img Manually](magiskboot.md)
