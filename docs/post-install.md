# Post-Install — Verify & Finish Setup

After flashing a Wild Kernels GKI kernel, do these checks to make sure everything is working.

> [!TIP]
> Follow in order — each step depends on the previous one.

## 1. Download matching manager — KernelSU / KernelSU-Next / ReSukiSU

- [ ] Download the `manager-apk-*` from the same [Releases](https://github.com/WildKernels/GKI_KernelSU_SUSFS/releases) page you got the kernel from.
- [ ] Install / update it over any existing manager.
- [ ] Open the manager — it should show the kernel version you just flashed (e.g. `6.1.x-androidXX-Wild`).
- [ ] Verify it reports "Working" / shows the correct version.

## 2. SUSFS

- [ ] In the manager, install the [sidex15/susfs4ksu-module](https://github.com/sidex15/susfs4ksu-module) (recommended module for SUSFS).
- [ ] Reboot after installing the module.

## 3. Meta Module (if mounting modules)

If you need to mount modules, install one of:

- [ ] [NoMount](https://github.com/maxsteeel/nomount) (Recommended) — Download the `NoMount-metamodule-*commit*.zip` from the same [Releases](https://github.com/WildKernels/GKI_KernelSU_SUSFS/releases) page you got the kernel from
- [ ] [Mountify](https://github.com/backslashxx/mountify) — you can always use the latest module if compatible with SUSFS used at time of Release

> [!NOTE]
> Only one is required if mounting modules. Compatibility with SUSFS shifts due to constant changes and it is not always compatible.

## 4. DroidSpaces

- [ ] Download the app here: [ravindu644/Droidspaces-OSS](https://github.com/ravindu644/Droidspaces-OSS)

## 5. Troubleshooting

<details>
<summary><b> Common issues</b></summary>

- **General issues** — try restarting your device.
- **Bootloop** — restore a stock boot.img via fastboot/recovery.
- **Manager and kernel version do not match (e.g. 31000 != 32000)** — for best compatibility ensure both match. Install the latest kernel and manager linked in the release and reboot fully.
- **Root not working** — ensure you installed the manager matching the flashed flavor (KernelSU / KernelSU-Next / ReSukiSU).

</details>

<details>
<summary><b> Nuclear option</b></summary>

Uninstall all modules and reboot, then delete all files and folders in the `/data/adb` folder. Reboot again and confirm no leftover files remain.

> [!CAUTION]
> This wipes all KernelSU/Magisk module data — only use if nothing else works.

</details>

---

Related: [Installation Overview](installation.md) · [Install with Kernel Flasher](kernelflasher.md) · [Patch boot.img Manually](magiskboot.md)
