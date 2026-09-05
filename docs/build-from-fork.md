# Build a Kernel in Your Fork

This guide shows how to fork the repository, build one specific GKI kernel with GitHub Actions, and download the result. You do not need a local Linux build environment for the normal workflow.

> [!CAUTION]
> A successful build does not guarantee that a kernel will boot on a particular device. Confirm the device's GKI/KMI family, keep the stock `boot.img`, and have a tested recovery method before flashing. See the [Installation Guide](installation.md) before using an artifact.

## 1. Fork the Repository

1. Open [WildKernels/GKI_KernelSU_SUSFS](https://github.com/WildKernels/GKI_KernelSU_SUSFS).
2. Select **Fork**, choose your account, and create the fork.
3. Open the **Actions** tab in your fork.
4. If GitHub says workflows are disabled, select **I understand my workflows, go ahead and enable them**.

Normal kernel builds use the repository's built-in `GITHUB_TOKEN`. You do not need to create a personal access token or repository secret.

If a build reports that the token cannot create releases or update Actions data, open **Settings → Actions → General → Workflow permissions** in your fork and allow **Read and write permissions**. Organization policy can prevent a repository from granting those permissions.

> [!NOTE]
> Forking this repository copies the build orchestration. Kernel sources, root implementations, SUSFS, patches, AnyKernel3, managers, and other components are still fetched from their configured upstream repositories.

## 2. Identify the Correct Kernel Family

Choose the kernel from the device's stock kernel/KMI branch—not only from the Android userspace version shown in Settings. For example, a phone running Android 15 may still use an `android14-6.1` kernel branch.

You can start by checking the running kernel:

```bash
adb shell uname -r
```

If the output does not identify the Android common-kernel generation, check the device's stock firmware information or OEM kernel sources before building.

The workflow currently exposes these families:

| Workflow selection | Android common-kernel generation | Linux series |
|---|---:|---:|
| `5.10.x-android12` | Android 12 | 5.10 |
| `5.10.x-android13` | Android 13 | 5.10 |
| `5.15.x-android13` | Android 13 | 5.15 |
| `5.15.x-android14` | Android 14 | 5.15 |
| `6.1.x-android14` | Android 14 | 6.1 |
| `6.6.x-android15` | Android 15 | 6.6 |
| `6.12.x-android16` | Android 16 | 6.12 |

The **OS patch level** field accepts one of the following:

- A patch date present in the selected family's config, such as `2025-01`.
- A numeric Linux sublevel present in that config, such as `118`. A sublevel can occur under more than one patch date, in which case every matching row is built.
- `lts`, which builds the current tip of that family's configured LTS branch.
- `All`, which builds every configured row for the selected family.

The matrix files under [`.github/config/`](../.github/config/) are the source of truth for available dates and sublevels. To guarantee one matrix row, select a unique patch date or `lts`; if you use a numeric sublevel, check the config first to confirm it occurs only once.

> [!WARNING]
> Do not leave **Kernel Version**, **OS patch level**, and **Root Flavor** set to `All` for a first test. Those defaults fan out across every exposed family, every matching matrix row, and all three root implementations, potentially creating hundreds of kernel jobs.

## 3. Run One Build in the GitHub UI

1. Open **Actions** in your fork.
2. Select **Build Kernels**.
3. Select **Run workflow**.
4. Choose the branch containing your desired changes, normally `main`.
5. Set a specific **Kernel Version**, **OS patch level**, and **Root Flavor**.
6. Select **Run workflow**.

Recommended settings for a first build:

| Input | Recommended value | Reason |
|---|---|---|
| Release Type | `Action` | Runs the build without creating a numbered `rN` release. It still replaces the fork's `nightly` prerelease. |
| Use cache | `false` for the first build | Avoids creating cache releases while testing the fork. Enable it later to speed up repeat builds. |
| Kernel Version | One exact family | Prevents an all-family fan-out. |
| OS patch level | One unique date or `lts` | Selects one matrix row. A numeric sublevel can match multiple dates. |
| Kernel Branding | Your short brand name | Changes the kernel's local version string. |
| Commit mode | `verified` | Uses the project's verified component pins where pins are supported. |
| Root Flavor | One implementation | Produces one kernel instead of KernelSU-Next, KernelSU, and ReSukiSU builds. |
| Feature toggles | Keep the defaults initially | Establishes a known baseline before customizing features. |
| Test release notes | `false` | `true` skips the kernel builds and only previews release notes. |

There is no rootless build option. Choose one of `KernelSU-Next`, `KernelSU`, or `ReSukiSU`. Install the matching manager after flashing; see [Post-install Setup](post-install.md).

### Example: Current Android 15 / Linux 6.6 LTS

Use:

| Input | Value |
|---|---|
| Kernel Version | `6.6.x-android15` |
| OS patch level | `lts` |
| Commit mode | `verified` |
| Root Flavor | `KernelSU` |

The workflow syncs `common-android15-6.6-lts` and reads the actual numeric `SUBLEVEL` from the synced kernel Makefile. Because that branch moves, a later LTS build can produce a newer sublevel.

### Example: Android 14 / Linux 6.1.118

Use:

| Input | Value |
|---|---|
| Kernel Version | `6.1.x-android14` |
| OS patch level | `118` or `2025-01` |
| Commit mode | `verified` |
| Root Flavor | `KernelSU` |

Both selectors resolve to the configured `2025-01` row. The expected artifact prefix is:

```text
6.1.118-android14-2025-01-KernelSU
```

## 4. Run the Same Build with GitHub CLI

Install and authenticate [GitHub CLI](https://cli.github.com/), then replace `YOUR_USERNAME` with the owner of the fork.

Android 15 / Linux 6.6 LTS:

```bash
gh workflow run main.yml \
  -R YOUR_USERNAME/GKI_KernelSU_SUSFS \
  --ref main \
  -f release_type=Action \
  -f kernel_build_version=6.6.x-android15 \
  -f os_patch_level=lts \
  -f brand_name=MyKernel \
  -f commit_mode=verified \
  -f root_flavor=KernelSU \
  -f use_cache=false
```

Android 14 / Linux 6.1.118:

```bash
gh workflow run main.yml \
  -R YOUR_USERNAME/GKI_KernelSU_SUSFS \
  --ref main \
  -f release_type=Action \
  -f kernel_build_version=6.1.x-android14 \
  -f os_patch_level=118 \
  -f brand_name=MyKernel \
  -f commit_mode=verified \
  -f root_flavor=KernelSU \
  -f use_cache=false
```

Find and watch the run:

```bash
gh run list \
  -R YOUR_USERNAME/GKI_KernelSU_SUSFS \
  --workflow main.yml \
  --limit 10

gh run watch \
  -R YOUR_USERNAME/GKI_KernelSU_SUSFS \
  RUN_ID \
  --exit-status
```

## 5. Understand Source Modes and Side Effects

### Commit mode

- `verified` is the recommended normal mode. It uses verified commits for components that the workflow pins.
- `latest` resolves supported components from their current branch tips when the run starts.
- `update` builds latest component tips and can edit, commit, and push verified pins back to the selected branch. Use it only when deliberately maintaining those pins. In the current workflow, the promotion job is skipped when **Kernel Version** selects only one family; it is intended for the all-family maintenance path, not the single-kernel path in this guide.

Even `verified` is not a complete lockfile: the Android kernel branch, KernelSU-Next, some patch/helper repositories, managers, and other components can still be fetched from moving upstream tips. Keep the workflow run URL and the matching `BuildInfo` artifact for provenance.

### Release type

- `Action` builds Actions artifacts and replaces the fork's `nightly` prerelease/tag with a link to that run. Use this mode for the single-family builds in this guide.
- `Pre-Release` creates the next numbered `rN` prerelease and uploads release assets when the workflow runs the all-family path.
- `Release` creates the next numbered `rN` stable release and uploads release assets when the workflow runs the all-family path.

> [!IMPORTANT]
> In the current workflow, selecting one exact kernel family causes the numbered release job to be skipped because the other family jobs are skipped. Do not select `Pre-Release` or `Release` for a single-family run; use `Action`. Running all families solely to create a numbered release is expensive and is not recommended for an initial fork build.

### Build cache

This project stores compiler caches in specially named GitHub Releases rather than using `actions/cache`. A missing cache on the first run is normal. With **Use cache** enabled, the workflow can create or update cache tags and releases in your fork. The separate **Clear Cache** workflow permanently deletes those cache releases after its confirmation input is supplied.

## 6. Download the Result

From the web UI:

1. Open the completed workflow run.
2. Scroll to **Artifacts**.
3. Download the artifact ending in `-AnyKernel3` for the selected root flavor.
4. Download the matching `-BuildInfo` artifact and keep it with the kernel.
5. Download the manager APK for the same root flavor and any required module artifacts.

Common artifacts include:

- `*-AnyKernel3` — kernel package contents.
- `*-BuildInfo` — source and artifact provenance, including checksums.
- Manager APK artifacts — install the manager matching the selected root flavor.
- `NoMount-Metamodule` — optional mount metamodule when applicable.

To download with GitHub CLI:

```bash
gh run download \
  -R YOUR_USERNAME/GKI_KernelSU_SUSFS \
  RUN_ID \
  -p '*-AnyKernel3' \
  -p '*-BuildInfo' \
  -p '*.apk' \
  -p 'NoMount-Metamodule' \
  -D ./artifacts
```

`gh run download` extracts each artifact into a directory. Before flashing, create the AnyKernel3 ZIP with `anykernel.sh` and the other package files at the archive root—not inside an extra parent directory.

Follow the [Installation Guide](installation.md), then complete the [Post-install Setup](post-install.md). Kernel Flasher requires existing root; for an unrooted first installation, see the [manual `magiskboot` method](magiskboot.md).

## 7. Customize Safely

For input-only changes such as branding, root flavor, or most feature toggles, you do not need to edit the repository. Select the values when dispatching the workflow.

> [!WARNING]
> Keep **SUSFS** and **NoMount** enabled for now. Disabling SUSFS leaves its commit unavailable to the required metadata validation. Disabling NoMount still passes its resolved commit into the kernel build but skips the corresponding metamodule artifact. Either choice causes a later metadata step to fail, so these toggles do not currently produce a supported SUSFS-free or NoMount-free build.

For source or workflow changes, keep your fork's `main` branch synchronized and work on a separate branch:

```bash
git clone https://github.com/YOUR_USERNAME/GKI_KernelSU_SUSFS.git
cd GKI_KernelSU_SUSFS
git remote add upstream https://github.com/WildKernels/GKI_KernelSU_SUSFS.git
git switch -c my-kernel
# Make and commit your changes, then:
git push -u origin my-kernel
```

Run the workflow with `my-kernel` selected in the web UI or change `--ref main` to `--ref my-kernel` in the CLI examples.

To update an unchanged fork `main` later:

```bash
git fetch upstream
git switch main
git merge --ff-only upstream/main
git push origin main
```

If your fork's `main` contains custom commits, `--ff-only` will stop instead of rewriting them. Merge or rebase those changes deliberately; do not force-push without understanding what will be replaced.

## Troubleshooting

### The Run workflow button is missing

Enable workflows from the fork's **Actions** tab and confirm `main.yml` exists on the fork's default branch. You also need write access to the fork.

### No target matches the patch level

Open the selected family's JSON file under [`.github/config/`](../.github/config/) and use an exact `date` or `sublevel` value. Not every family provides every sublevel, and `lts` only works where an LTS row is configured.

### The workflow creates more jobs than expected

Cancel the run and check all three selectors. Use one **Kernel Version**, one **OS patch level**, and one **Root Flavor** rather than `All`.

### Release or cache steps fail with a permission error

Check **Settings → Actions → General → Workflow permissions** and the organization policy applied to the fork. Normal builds do not require a custom token.

### The kernel builds but does not boot

Do not retry by changing random feature switches. Restore the stock boot image, verify the exact kernel/KMI family, and collect the information requested by the project's issue templates. Generic GKI compatibility is broad, not universal.
