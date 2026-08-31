# Install with Kernel Flasher

> [!NOTE]
> This method is more convenient when upgrading KernelSU and can be done without a computer. Make a backup first.

> [!CAUTION]
> Flashing a kernel can brick your device and will void your warranty. Make a full backup (boot partition at minimum) before proceeding.

## Prerequisites

- Device with unlocked bootloader running a GKI2 kernel 5.10+
- Root access already granted to the flashing app

## Steps

1. **Download the AnyKernel3 ZIP** that matches your kernel version (e.g., `6.1.157-android14`) from the latest [Releases](https://github.com/WildKernels/GKI_KernelSU_SUSFS/releases) page.
2. **Open the Kernel Flasher app**, grant necessary root permissions when prompted.
3. **Select the AnyKernel3 ZIP** you downloaded and flash. Do not interrupt the process.
4. **Reboot** when prompted and verify KernelSU manager shows the expected version.

> [!NOTE]
> Match by the full kernel version (e.g., `6.1.157-android14`) - your device's Android version and the `android14` in the kernel version are not necessarily the same.

This requires the flashing app to have root permissions. On first install from stock (no root yet), flash via recovery or fastboot instead, then use this method for subsequent upgrades.

## Supported flashing apps

- [Kernel Flasher](https://github.com/fatalcoder524/KernelFlasher) - recommended, actively maintained

Requires root to flash a kernel from within Android.

## After flashing

- Install / update the matching KernelSU manager APK (see release assets `manager-apk-*`).
- If using SUSFS, install the SUSFS module via the manager.
- Verify with `su` or manager app that root is working.

## Troubleshooting

- **Bootloop** - restore your boot backup via fastboot/recovery.
- **Wrong KMI** - re-flash with the correct KMI variant; KMI mismatch is the most common failure.
- **Manager shows old version** - ensure you flashed the intended variant and rebooted fully.

---

Related: [Installation Overview](installation.md) · [Patch boot.img Manually](magiskboot.md) · [Releases](https://github.com/WildKernels/GKI_KernelSU_SUSFS/releases)
