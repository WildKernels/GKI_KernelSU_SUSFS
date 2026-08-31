# Post-Install — Verify & Finish Setup

After flashing a WildKernels GKI kernel, do these checks to make sure everything is working.

## 1. Download matching manager — KernelSU / KernelSU-Next / ReSukiSU

- Download the `manager-apk-*` from the same [Releases](https://github.com/WildKernels/GKI_KernelSU_SUSFS/releases) page you got the kernel from.
- Install / update it over any existing manager.
- Open the manager — it should show the kernel version you just flashed (e.g. `6.1.157-android14-Wild`).

## 2. SUSFS (if you flashed a SUSFS build)

- In the manager, install the [sidex15/susfs4ksu-module](https://github.com/sidex15/susfs4ksu-module) (recommended module for SUSFS).
- Reboot after installing the module if prompted.

## 3. Verify root

- Open the manager and check it reports "Working" / shows the correct version.
- Or via ADB/shell: `su` should grant root, `uname -r` should show the new kernel version.

## 4. Troubleshooting

- **Bootloop** — restore your boot backup via fastboot (`fastboot flash boot boot.img`) or recovery.
- **Wrong KMI / won't boot** — you flashed the wrong `androidXX` KMI variant. Re-flash the correct one matching `uname -r` / your running KMI.
- **Manager shows old version** — you flashed the wrong variant or didn't reboot fully. Re-flash the intended ZIP and reboot.
- **Root not working** — ensure you installed the manager matching the flashed flavor (KernelSU / KernelSU-Next / ReSukiSU).

---

Related: [Installation Overview](installation.md) · [Install with Kernel Flasher](kernelflasher.md) · [Install with PixelFlasher](pixelflasher.md) · [Patch boot.img Manually](magiskboot.md)
