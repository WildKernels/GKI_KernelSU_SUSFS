<div align="center">

# Wild Kernels for Android

[![KernelSU](https://img.shields.io/badge/KernelSU-Supported-green)](https://kernelsu.org/)
[![susfs4ksu](https://img.shields.io/badge/susfs4ksu-Integrated-orange)](https://gitlab.com/simonpunk/susfs4ksu)

</div>

## Your warranty is no longer valid!

I am **not responsible** for bricked devices, damaged hardware, or any issues that arise from using this kernel.

**Please** do thorough research and fully understand the features included in this kernel before flashing it!

By flashing this kernel, **YOU** are choosing to make these modifications. If something goes wrong, **do not blame me**!

---

### Proceed at your own risk!

---

## Available Devices

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

## Support

If you encounter any issues or need help, feel free to:
- Open an issue in this repository
- Reach out to me directly

---

## Disclaimer

Flashing this kernel will void your warranty, and there is always a risk of bricking your device. Please make sure to:
- Back up your data
- Understand the risks before proceeding

**Proceed at your own risk!**

---

<div align="center">

## Connect With Us

[![Telegram](https://img.shields.io/badge/Telegram-TheWildJames-blue?logo=telegram)](https://t.me/TheWildJames)
[![Telegram Group](https://img.shields.io/badge/Telegram-WildKernelsTG-blue?logo=telegram)](https://t.me/WildKernelsTG)

</div>

---

## Special Thanks

**These amazing people help make this project possible!**

<!-- ORG_CONTRIBUTORS_START -->
<p align="center">
  <a href="https://github.com/TheWildJames" title="TheWildJames (8378 contributions across org)">
    <img src="https://github.com/TheWildJames.png?size=80" width="50" height="50" alt="TheWildJames" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/jimsterino98" title="jimsterino98 (1002 contributions across org)">
    <img src="https://github.com/jimsterino98.png?size=80" width="50" height="50" alt="jimsterino98" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/osm0sis" title="osm0sis (467 contributions across org)">
    <img src="https://github.com/osm0sis.png?size=80" width="50" height="50" alt="osm0sis" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/fatalcoder524" title="fatalcoder524 (445 contributions across org)">
    <img src="https://github.com/fatalcoder524.png?size=80" width="50" height="50" alt="fatalcoder524" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/luigimak" title="luigimak (59 contributions across org)">
    <img src="https://github.com/luigimak.png?size=80" width="50" height="50" alt="luigimak" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/zqxr4" title="zqxr4 (40 contributions across org)">
    <img src="https://github.com/zqxr4.png?size=80" width="50" height="50" alt="zqxr4" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/MiRinChan" title="MiRinChan (37 contributions across org)">
    <img src="https://github.com/MiRinChan.png?size=80" width="50" height="50" alt="MiRinChan" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/ahmed-alnassif" title="ahmed-alnassif (23 contributions across org)">
    <img src="https://github.com/ahmed-alnassif.png?size=80" width="50" height="50" alt="ahmed-alnassif" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/nathanchance" title="nathanchance (14 contributions across org)">
    <img src="https://github.com/nathanchance.png?size=80" width="50" height="50" alt="nathanchance" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/dathtd119" title="dathtd119 (11 contributions across org)">
    <img src="https://github.com/dathtd119.png?size=80" width="50" height="50" alt="dathtd119" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/koush" title="koush (10 contributions across org)">
    <img src="https://github.com/koush.png?size=80" width="50" height="50" alt="koush" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/liqideqq" title="liqideqq (10 contributions across org)">
    <img src="https://github.com/liqideqq.png?size=80" width="50" height="50" alt="liqideqq" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/engstk" title="engstk (9 contributions across org)">
    <img src="https://github.com/engstk.png?size=80" width="50" height="50" alt="engstk" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/Bouteillepleine" title="Bouteillepleine (7 contributions across org)">
    <img src="https://github.com/Bouteillepleine.png?size=80" width="50" height="50" alt="Bouteillepleine" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/ukriu" title="ukriu (7 contributions across org)">
    <img src="https://github.com/ukriu.png?size=80" width="50" height="50" alt="ukriu" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/capntrips" title="capntrips (6 contributions across org)">
    <img src="https://github.com/capntrips.png?size=80" width="50" height="50" alt="capntrips" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/ReeViiS69" title="ReeViiS69 (6 contributions across org)">
    <img src="https://github.com/ReeViiS69.png?size=80" width="50" height="50" alt="ReeViiS69" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/TheSillyOk" title="TheSillyOk (6 contributions across org)">
    <img src="https://github.com/TheSillyOk.png?size=80" width="50" height="50" alt="TheSillyOk" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/axxx007xxxz" title="axxx007xxxz (5 contributions across org)">
    <img src="https://github.com/axxx007xxxz.png?size=80" width="50" height="50" alt="axxx007xxxz" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/poqdavid" title="poqdavid (5 contributions across org)">
    <img src="https://github.com/poqdavid.png?size=80" width="50" height="50" alt="poqdavid" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/Fede2782" title="Fede2782 (4 contributions across org)">
    <img src="https://github.com/Fede2782.png?size=80" width="50" height="50" alt="Fede2782" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/brunoanc" title="brunoanc (3 contributions across org)">
    <img src="https://github.com/brunoanc.png?size=80" width="50" height="50" alt="brunoanc" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/FixeQD" title="FixeQD (3 contributions across org)">
    <img src="https://github.com/FixeQD.png?size=80" width="50" height="50" alt="FixeQD" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/soranerai" title="soranerai (3 contributions across org)">
    <img src="https://github.com/soranerai.png?size=80" width="50" height="50" alt="soranerai" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/dereference23" title="dereference23 (2 contributions across org)">
    <img src="https://github.com/dereference23.png?size=80" width="50" height="50" alt="dereference23" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/nullptr-t-oss" title="nullptr-t-oss (2 contributions across org)">
    <img src="https://github.com/nullptr-t-oss.png?size=80" width="50" height="50" alt="nullptr-t-oss" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/sakfi" title="sakfi (2 contributions across org)">
    <img src="https://github.com/sakfi.png?size=80" width="50" height="50" alt="sakfi" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/wloot" title="wloot (2 contributions across org)">
    <img src="https://github.com/wloot.png?size=80" width="50" height="50" alt="wloot" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/Zackptg5" title="Zackptg5 (2 contributions across org)">
    <img src="https://github.com/Zackptg5.png?size=80" width="50" height="50" alt="Zackptg5" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/airend" title="airend (1 contributions across org)">
    <img src="https://github.com/airend.png?size=80" width="50" height="50" alt="airend" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/arter97" title="arter97 (1 contributions across org)">
    <img src="https://github.com/arter97.png?size=80" width="50" height="50" alt="arter97" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/Avocadosheep" title="Avocadosheep (1 contributions across org)">
    <img src="https://github.com/Avocadosheep.png?size=80" width="50" height="50" alt="Avocadosheep" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/backslashxx" title="backslashxx (1 contributions across org)">
    <img src="https://github.com/backslashxx.png?size=80" width="50" height="50" alt="backslashxx" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/Dawid2849" title="Dawid2849 (1 contributions across org)">
    <img src="https://github.com/Dawid2849.png?size=80" width="50" height="50" alt="Dawid2849" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/DespairFactor" title="DespairFactor (1 contributions across org)">
    <img src="https://github.com/DespairFactor.png?size=80" width="50" height="50" alt="DespairFactor" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/djkcyl" title="djkcyl (1 contributions across org)">
    <img src="https://github.com/djkcyl.png?size=80" width="50" height="50" alt="djkcyl" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/DroidThug" title="DroidThug (1 contributions across org)">
    <img src="https://github.com/DroidThug.png?size=80" width="50" height="50" alt="DroidThug" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/fernandobouchet" title="fernandobouchet (1 contributions across org)">
    <img src="https://github.com/fernandobouchet.png?size=80" width="50" height="50" alt="fernandobouchet" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/googlebleh" title="googlebleh (1 contributions across org)">
    <img src="https://github.com/googlebleh.png?size=80" width="50" height="50" alt="googlebleh" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/hdigger" title="hdigger (1 contributions across org)">
    <img src="https://github.com/hdigger.png?size=80" width="50" height="50" alt="hdigger" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/huangdihd" title="huangdihd (1 contributions across org)">
    <img src="https://github.com/huangdihd.png?size=80" width="50" height="50" alt="huangdihd" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/Myself5" title="Myself5 (1 contributions across org)">
    <img src="https://github.com/Myself5.png?size=80" width="50" height="50" alt="Myself5" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/notmarek" title="notmarek (1 contributions across org)">
    <img src="https://github.com/notmarek.png?size=80" width="50" height="50" alt="notmarek" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/pratikkabra143" title="pratikkabra143 (1 contributions across org)">
    <img src="https://github.com/pratikkabra143.png?size=80" width="50" height="50" alt="pratikkabra143" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/ShirkNeko" title="ShirkNeko (1 contributions across org)">
    <img src="https://github.com/ShirkNeko.png?size=80" width="50" height="50" alt="ShirkNeko" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/SSS1981-op" title="SSS1981-op (1 contributions across org)">
    <img src="https://github.com/SSS1981-op.png?size=80" width="50" height="50" alt="SSS1981-op" style="border-radius:50%;" />
  </a>
  <a href="https://github.com/Tomoms" title="Tomoms (1 contributions across org)">
    <img src="https://github.com/Tomoms.png?size=80" width="50" height="50" alt="Tomoms" style="border-radius:50%;" />
  </a>
</p>
<p align="center"><sub>Total contributors: <b>47</b> across WildKernels org &middot; updated 2026-08-30</sub></p>
<p align="center"><sub>@TheWildJames, @jimsterino98, @osm0sis, @fatalcoder524, @luigimak, @zqxr4, @MiRinChan, @ahmed-alnassif, @nathanchance, @dathtd119, @koush, @liqideqq, @engstk, @Bouteillepleine, @ukriu, @capntrips, @ReeViiS69, @TheSillyOk, @axxx007xxxz, @poqdavid, @Fede2782, @brunoanc, @FixeQD, @soranerai, @dereference23, @nullptr-t-oss, @sakfi, @wloot, @Zackptg5, @airend, @arter97, @Avocadosheep, @backslashxx, @Dawid2849, @DespairFactor, @djkcyl, @DroidThug, @fernandobouchet, @googlebleh, @hdigger, @huangdihd, @Myself5, @notmarek, @pratikkabra143, @ShirkNeko, @SSS1981-op, @Tomoms</sub></p>
<!-- ORG_CONTRIBUTORS_END -->

| Contributor | Contribution |
|-------------|-------------|
| [simonpunk](https://gitlab.com/simonpunk/susfs4ksu.git) | Created SUSFS! |
| [sidex15](https://github.com/sidex15) | Created module! |

*If you have contributed and are not listed here, please remind me!* 

---

## Donations

Any and all donations are appreciated!

- PayPal: [bauhd@outlook.com](mailto:bauhd@outlook.com)
- Card: <https://buy.stripe.com/5kQ28sdi08Nr0Xc2fU5os00>
- LTC: MVaN1ToSuks2cdK9mB3M8EHCfzQSyEMf6h
- BTC: 3BBXAMS4ZuCZwfbTXxWGczxHF4isymeyxG
- ETH: 0x2b9C846c84d58717e784458406235C09a834274e
- Patreon: <https://patreon.com/WildKernels>
