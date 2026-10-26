# Post-Install — Verify & Finish Setup

After flashing a Wild Kernels GKI kernel, do these checks in order.

## 1. Download matching manager — KernelSU / KernelSU-Next / BakaSU / FinaSU / Suki-SU Ultra / KowSU

- [ ] Download the `manager-apk-*` from the same [Releases](https://github.com/WildKernels/GKI_KernelSU_SUSFS/releases) page you got the kernel from.
- [ ] Install / update it over any existing manager.
- [ ] Open the manager — it should show the kernel version you just flashed (e.g. `6.1.x-androidXX-Wild`) and report "Working".

## 2. SUSFS

- [ ] In the manager, install the [sidex15/susfs4ksu-module](https://github.com/sidex15/susfs4ksu-module).
- [ ] Reboot.

## 3. Meta Module (if mounting modules)

If you need to mount modules, install one:

- [ ] [NoMount](https://github.com/maxsteeel/nomount) (Recommended) — `NoMount-metamodule-*commit*.zip` from [Releases](https://github.com/WildKernels/GKI_KernelSU_SUSFS/releases)
- [ ] [Mountify](https://github.com/backslashxx/mountify) — latest compatible module

> [!NOTE]
> Only one is required. Compatibility with SUSFS shifts with updates.

## 4. DroidSpaces

- [ ] Download the app: [ravindu644/Droidspaces-OSS](https://github.com/ravindu644/Droidspaces-OSS)

## 5. Troubleshooting

<details>
<summary><b> Common issues</b></summary>

- **General issues** — try restarting your device.
- **Bootloop** — restore a stock boot.img via fastboot/recovery.
- **Manager and kernel version do not match (e.g. 31000 != 32000)** — install the latest kernel and manager from the release and reboot.
- **Root not working** — ensure the manager matches the flashed flavor (KernelSU / KernelSU-Next / ReSukiSU / FinaSU).

</details>

<details>
<summary><b> Nuclear option</b></summary>

Uninstall all modules and reboot, then delete all files and folders in `/data/adb`. Reboot again.

> [!CAUTION]
> This wipes all KernelSU/Magisk module data — only use if nothing else works.

</details>
