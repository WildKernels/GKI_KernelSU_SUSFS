<div align="center">

# 🔥 Wild Kernels for Android

[![KernelSU](https://img.shields.io/badge/KernelSU-Supported-green)](https://kernelsu.org/)
[![SUSFS](https://img.shields.io/badge/SUSFS-Integrated-orange)](https://gitlab.com/simonpunk/susfs4ksu)

</div>

## ⚠️ Your warranty is no longer valid!

I am **not responsible** for bricked devices, damaged hardware, or any issues that arise from using this kernel.

**Please** do thorough research and fully understand the features included in this kernel before flashing it!

By flashing this kernel, **YOU** are choosing to make these modifications. If something goes wrong, **do not blame me**!

---

### 🚨 Proceed at your own risk!

---

## 🤔 Do I need this? / А нужно ли мне это?

### English
Before flashing, weigh the benefits against the complexity to see if the built-in mode is right for you.

#### Pros:
*   🚀 **Zero Modular Overhead:** The protection logic is built directly into the kernel source, eliminating routing latency and execution delays.
*   🛡️ **Absolute Stealth:** Fully invulnerable to system call (syscall) timing attacks. Leaves no trace of external kernel modules (LKM/KPM) in the system.
*   💎 **Monolithic Stability:** Operates as a permanent part of the kernel code, eliminating runtime sync errors or hook drops.

#### Cons:
*   ⚙️ **Installation Complexity:** Requires backing up and flashing a custom GKI kernel rather than just installing a simple Magisk/KernelSU LKM module.
*   🔄 **Maintenance & Updates:** Upgrading your Android system or kernel requires downloading a new custom GKI build.
*   📲 **Modern Tooling Prerequisite:** May require transitioning from older root solutions (like Magisk) to modern kernel-based managers (like KernelSU, KernelSU-Next) since GKI kernels are built around them.

### Русский
Перед установкой оцените преимущества и недостатки встроенного режима, чтобы понять, подходит ли он вам.

#### Плюсы:
*   🚀 **Нулевой оверхед:** Логика защиты работает напрямую как часть ядра, полностью исключая задержки маршрутизации вызовов и накладные расходы на выполнение.
*   🛡️ **Абсолютная скрытность:** Полная неуязвимость к timing-атакам на системные вызовы (syscall). Не оставляет никаких следов загруженных модулей ядра (LKM/KPM).
*   💎 **Монолитная стабильность:** Работает как постоянная часть кода ядра, исключая рантайм-ошибки синхронизации или падение хуков.

#### Минусы:
*   ⚙️ **Сложность установки:** Требует обязательного резервного копирования и прошивки кастомного GKI ядра вместо простой установки модуля.
*   🔄 **Сложность обновления:** Для обновления системы или ядра вам потребуется скачивать новую сборку кастомного GKI ядра.
*   📲 **Переход на новое ПО:** Может потребоваться отказаться от устаревших рут-решений (таких как Magisk) в пользу современных менеджеров на базе ядра (KernelSU, KernelSU-Next), так как GKI ядра собираются вокруг них.

---

## 📋 Installation Guide / Инструкция по установке

### English
1. **Uninstall the Kernel Module (LKM):** If you currently have the standard `vpnhide` kernel module (LKM) installed, uninstall it first.
2. **Install the Bridge Module:** Flash the `vpnhide-bridge.zip` Magisk/KernelSU module (this bridges framework-level hooks to the built-in driver).
3. **Backup Your Current Kernel:** **Mandatory!** Make a backup of your current kernel (`boot` and `init_boot` image) so you can easily restore it via `fastboot` in case of a bootloop or kernel panic.
4. **Choose the Kernel Version:** Select a kernel version from the releases page that is as close as possible to your current kernel version. **Do not choose a kernel version older than your current one.**
5. **Flash the Kernel:** Flash the custom GKI kernel using **Kernel Flasher** or **KernelSU / KernelSU-Next** manager.
6. **Reboot:** Reboot your device.
7. **Verify:** If everything boots fine, open the VPNHide Next app. The native protection card should display `built-in` mode. You now have a GKI kernel with all **Wild Kernels** (KernelSU-Next + SUSFS) and **VPNHide Next** features built-in.
8. **SUSFS Settings:** In the KernelSU manager, open the `SUSFS-FOR-KERNELSU` module. Under the `kernel uname` category, make sure to check/enable **"spoof on boot"** and **"set stock kernel build date"** options for proper spoofing.

### Русский
1. **Удалите модуль ядра (LKM):** Если у вас установлен обычный внешний модуль ядра `vpnhide` (LKM), сначала полностью удалите его.
2. **Установите bridge-модуль:** Установите Magisk/KernelSU модуль `vpnhide-bridge.zip` (он осуществляет связь между хуками фреймворка и встроенным драйвером ядра).
3. **Сделайте бэкап ядра:** **Обязательно!** Сделайте резервную копию текущего ядра (`boot` и `init_boot` образ) для возможности восстановления через `fastboot` в крайнем случае.
4. **Выберите версию ядра:** Выберите сборку ядра на странице релизов, которая максимально близка к вашей текущей версии ядра. **Ни в коем случае не выбирайте версию старше (ниже по версии), чем ваша текущая.**
5. **Прошейте ядро:** Прошейте кастомное GKI ядро через **Kernel Flasher** или менеджер **KernelSU / KernelSU-Next**.
6. **Перезагрузите устройство.**
7. **Проверьте статус:** Если запуск прошёл успешно, откройте приложение VPNHide Next. На карточке нативной защиты должен отображаться режим `built-in`. Теперь у вас установлено ядро со всеми фичами **Wild Kernels** (KernelSU-Next + SUSFS) и встроенной защитой **VPNHide Next**.
8. **Настройки SUSFS:** В менеджере KernelSU откройте модуль `SUSFS-FOR-KERNELSU`. В категории `kernel uname` обязательно отметьте галочками пункты **"spoof on boot"** и **"set stock kernel build date"** для корректной подмены.
---

## 🏗️ Integrated Kernel Branch

This branch provides custom Android GKI kernels with integrated **KernelSU-Next**, **SUSFS**, and **VPNHide Next** built-in monolithic protection.

---

## 🔗 Additional Resources

- 🩹 [Kernel Patches](https://github.com/WildKernels/kernel_patches)
- 📜 [Old Build Scripts](https://github.com/TheWildJames/kernel_build_scripts)
- ⚡ [Kernel Flasher](https://github.com/fatalcoder524/KernelFlasher)

---

## ✨ Features

- 🔐 **KernelSU / KernelSU-Next**: A root solution for Android GKI devices that works in kernel mode and grants root permission to userspace applications directly in kernel space.
- 🛡️ **SUSFS**: An addon root hiding kernel patches and userspace module for KernelSU.
- 🛡️ **VPNHide Next**: Built-in monolithic kernel-level VPN hiding solution with zero modular overhead and absolute stealth against system call timing attacks.

---

## 🏆 Credits

- 🔐 **KernelSU**: Developed by [tiann](https://github.com/tiann/KernelSU)
- 🚀 **KernelSU-Next**: Developed by [rifsxd](https://github.com/KernelSU-Next/KernelSU-Next)
- ✨ **Magic-KSU**: Developed by [5ec1cff](https://github.com/5ec1cff/KernelSU)
- 🛡️ **SUSFS**: Developed by [simonpunk](https://gitlab.com/simonpunk/susfs4ksu.git)
- 🛡️ **Baseband-guard (BBG)**: Developed by [vc-teahouse](https://github.com/vc-teahouse/Baseband-guard)
- 📦 **SUSFS Module**: Developed by [sidex15](https://github.com/sidex15)
- 🛡️ **VPNHide Next**: Monolithic in-built kernel integration developed by [soranerai](https://github.com/soranerai)
- 🔧 **Device Boot Fix**: [Boot fix commit](https://github.com/Anything-at-25-00/android_kernel_common_android12-5.10/commit/2476d262b597fe8af82cfb7aaf96676f51c6b4ed) for fixing some devices not booting

🙏 Special thanks to the open-source community for their contributions!

---

## 💬 Support

If you encounter any issues or need help, feel free to:
- 🐛 Open an issue in this repository
- 💬 Reach out to me directly

---

## ⚠️ Disclaimer

Flashing this kernel will void your warranty, and there is always a risk of bricking your device. Please make sure to:
- 💾 Back up your data
- 🧠 Understand the risks before proceeding

**🚨 Proceed at your own risk!**

---

<div align="center">

## 📱 Connect With Us

[![Telegram](https://img.shields.io/badge/Telegram-TheWildJames-blue?logo=telegram)](https://t.me/TheWildJames)
[![Telegram Group](https://img.shields.io/badge/Telegram-WildKernelsTG-blue?logo=telegram)](https://t.me/WildKernelsTG)

</div>

---

## 🌟 Special Thanks

**These amazing people help make this project possible! ❤️**

| Contributor | Contribution |
|-------------|-------------|
| 🛡️ [simonpunk](https://gitlab.com/simonpunk/susfs4ksu.git) | Created SUSFS! |
| 📦 [sidex15](https://github.com/sidex15) | Created module! |
| 🩹 [backslashxx](https://github.com/backslashxx) | Helped with patches! |
| 🔧 [Teemo](https://github.com/liqideqq) | Helped with patches! |
| 💝 [幕落](https://github.com/MuLuo688) | Donation! |
| 🛡️ [vc-teahouse](https://github.com/vc-teahouse) | Created Baseband-guard (BBG)! |

*If you have contributed and are not listed here, please remind me!* 🙏

---

## 💝 Donations

Any and all donations are appreciated!

- PayPal: [bauhd@outlook.com](mailto:bauhd@outlook.com)
- Card: <https://buy.stripe.com/5kQ28sdi08Nr0Xc2fU5os00>
- LTC: MVaN1ToSuks2cdK9mB3M8EHCfzQSyEMf6h
- BTC: 3BBXAMS4ZuCZwfbTXxWGczxHF4isymeyxG
- ETH: 0x2b9C846c84d58717e784458406235C09a834274e
- Patreon: <https://patreon.com/WildKernels>
