# Post-Install — Verify & Finish Setup

After flashing a WildKernels GKI kernel, do these checks to make sure everything is working.

## 1. Download matching manager — KernelSU / KernelSU-Next / ReSukiSU

- Download the `manager-apk-*` from the same [Releases](https://github.com/WildKernels/GKI_KernelSU_SUSFS/releases) page you got the kernel from.
- Install / update it over any existing manager.
- Open the manager — it should show the kernel version you just flashed (e.g. `6.1.x-androidXX-Wild`).

## 2. SUSFS

- In the manager, install the [sidex15/susfs4ksu-module](https://github.com/sidex15/susfs4ksu-module) (recommended module for SUSFS).
- Reboot after installing the module.

## 3. Verify root

- Open the manager and check it reports "Working" / shows the correct version.

## 4. Troubleshooting

- **Bootloop** — restore a stock boot.img via fastboot/recovery.
- **Manager and kernel version do not match (e.g. 31000 != 32000)** — for best compatibility ensure both match. Install the latest kernel and manager linked in the release and reboot fully.
- **Root not working** — ensure you installed the manager matching the flashed flavor (KernelSU / KernelSU-Next / ReSukiSU).

---

Related: [Installation Overview](installation.md) · [Install with Kernel Flasher](kernelflasher.md) · [Install with PixelFlasher](pixelflasher.md) · [Patch boot.img Manually](magiskboot.md)
