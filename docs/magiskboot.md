# Patch boot.img Manually (magiskboot)

> [!CAUTION]
> Wild Kernels is not responsible for bricked devices or damage. By flashing, you assume all risk. Back up your data and understand the risks before flashing.

> [!TIP]
> It's always recommended to use `magiskboot` to patch images — use the [official build](https://github.com/topjohnwu/Magisk/releases), which runs on Android devices and Linux.

**Platforms:** [Android](#-android) · [Linux](#-linux)

## Preparation

1. Get your device's stock `boot.img`.
2. Download the AnyKernel3 ZIP file that matches your kernel version (e.g., `6.1.x-androidXX`).
3. Unpack the AnyKernel3 package and get the `Image` file, which is the kernel file of KernelSU.

> [!NOTE]
> Match by the full kernel version (e.g., `6.1.x-androidXX`) — your device's Android version and the `androidXX` in the kernel version are not necessarily the same. For example, as of writing, a Google Pixel 8 is on `6.1.157-android14` while the system Android is 17.

---

<details>
<summary><b> Android</b> — via adb + <code>libmagiskboot.so</code></summary>

Folder structure on device (`/data/local/tmp/`):

```
/data/local/tmp/
├── magiskboot
├── boot.img
└── Image
```

1. Download latest Magisk from [GitHub Releases](https://github.com/topjohnwu/Magisk/releases).
2. Rename `Magisk-*(version).apk` to `Magisk-*.zip` and unzip it.
3. Push `libmagiskboot.so` to your device by ADB:
  ```sh
  adb push Magisk-*/lib/arm64-v8a/libmagiskboot.so /data/local/tmp/magiskboot
  ```
4. Push stock `boot.img` and `Image` from AnyKernel3 to your device:
  ```sh
  adb push boot.img /data/local/tmp/
  adb push Image /data/local/tmp/
  ```
5. Enter ADB shell and make it executable:
  ```sh
  adb shell
  cd /data/local/tmp/
  chmod +x magiskboot
  ```
6. Unpack `boot.img`:
  ```sh
  ./magiskboot unpack boot.img
  ```
  You will get a `kernel` file — this is your stock kernel.

7. Replace the kernel with the KernelSU `Image`:
  ```sh
  mv -f Image kernel
  ```
8. Repack the boot image:
  ```sh
  ./magiskboot repack boot.img
  ```
  You will get a `new-boot.img` file.

9. To temporarily test you can run `fastboot boot new-boot.img`.

10. Flash it by fastboot:
  ```sh
  fastboot flash boot new-boot.img
  ```

</details>

<details>
<summary><b> Linux</b> — official magiskboot</summary>

Folder structure on PC:

```
.
├── magiskboot
├── boot.img
└── Image
```

Official `magiskboot` can run in Linux normally — use the [official build](https://github.com/topjohnwu/Magisk/releases).

1. Prepare stock `boot.img` and `Image` in your PC.
2. Make it executable:
  ```sh
  chmod +x magiskboot
  ```
3. Unpack `boot.img`:
  ```sh
  ./magiskboot unpack boot.img
  ```
  You will get a `kernel` file — this is your stock kernel.

4. Replace the kernel:
  ```sh
  mv -f Image kernel
  ```
5. Repack:
  ```sh
  ./magiskboot repack boot.img
  ```
  You will get a `new-boot.img` file.

6. To temporarily test you can run `fastboot boot new-boot.img`.

7. Flash it by fastboot:
  ```sh
  fastboot flash boot new-boot.img
  ```

</details>

---

Related: [Installation Overview](installation.md) · [Install with Kernel Flasher](kernelflasher.md)
