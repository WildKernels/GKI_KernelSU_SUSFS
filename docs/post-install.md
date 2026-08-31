# Post-Install — Verify & Finish Setup

After flashing a WildKernels GKI kernel, do these checks to make sure everything is working.

## 1. Download matching manager — KernelSU / KernelSU-Next / ReSukiSU

- Download the `manager-apk-*` from the same [Releases](https://github.com/WildKernels/GKI_KernelSU_SUSFS/releases) page you got the kernel from.
- Install / update it over any existing manager.
- Open the manager — it should show the kernel version you just flashed (e.g. `6.1.x-androidXX-Wild`).
- Verify it reports "Working" / shows the correct version.

## 2. SUSFS

- In the manager, install the [sidex15/susfs4ksu-module](https://github.com/sidex15/susfs4ksu-module) (recommended module for SUSFS).
- Reboot after installing the module.

## 3. Meta Module (if mounting modules)

If you need to mount modules, install one of:
- [NoMount](https://github.com/maxsteeel/nomount) (Recommended) — Download the `NoMount-metamodule-*commit*.zip` from the same [Releases](https://github.com/WildKernels/GKI_KernelSU_SUSFS/releases) page you got the kernel from
- [Mountify](https://github.com/backslashxx/mountify) — you can always use the latest module if compatible with SUSFS used at time of Release

> [!NOTE]
> Only one is required if mounting modules. Compatibility with SUSFS shifts due to constant changes and it is not always compatible.

## 4. DroidSpaces

- Download the app here: [ravindu644/DroidSpaces-OSS](https://github.com/ravindu644/DroidSpaces-OSS)

## 5. Troubleshooting

- **General issues** — try restarting your device.
- **Bootloop** — restore a stock boot.img via fastboot/recovery.
- **Manager and kernel version do not match (e.g. 31000 != 32000)** — for best compatibility ensure both match. Install the latest kernel and manager linked in the release and reboot fully.
- **Root not working** — ensure you installed the manager matching the flashed flavor (KernelSU / KernelSU-Next / ReSukiSU).
- **Nuclear option** — delete all files and folders in the `/data/adb` folder. This will remove all modules and superuser data. If any files fail to delete or you get an error, reboot and try again, then do one final reboot to confirm no modules or leftover files remain.

---

Related: [Installation Overview](installation.md) · [Install with Kernel Flasher](kernelflasher.md) · [Patch boot.img Manually](magiskboot.md)
