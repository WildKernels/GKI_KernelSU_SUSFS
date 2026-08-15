# Pinned GKI Root Variants

`Build pinned root variants` is a manual, artifact-only workflow. It produces
three separate source trees and never combines root implementations:

| Variant | Upstream | Pinned commit |
| --- | --- | --- |
| Classic KernelSU | `tiann/KernelSU` | `da9abf498a77d438989fea0f5f4e348b9a540c07` |
| KernelSU Next | `KernelSU-Next/KernelSU-Next` `dev` | `234f6e040fcbca18b16d2398e1aa225712ec99ad` |
| ReSukiSU | `ReSukiSU/ReSukiSU` | `3ef06b0fcb0960dc9563256fe26a58e892663387` |
| NoMount | `maxsteeel/nomount` `dev` | `c52936b229c25a4b0e41b6627f7d3bc5eaaaf2b5` |

The workflow resolves the selected target to its immutable SUSFS pin:

| GKI target | SUSFS branch tip pinned for this workflow |
| --- | --- |
| android12-5.10 | `3c14ad549f826b1f53878ec8c12253efebeed75a` |
| android13-5.10 | `f81aaf10e9560282052bb61dd931315c2ca3e617` |
| android13-5.15 | `ccb1918684b27644d17a6c842f57b60ae5966025` |
| android14-5.15 | `0463ac089308014e8c22cc6a4558e0d6d2a53e08` |
| android14-6.1 | `e287d59066380bf6de4396532d4a42edf4408701` |
| android15-6.6 | `be7b7ef49a1e1b189c3abf00eacaa7ebdb4168c1` |
| android16-6.12 | `f37930f374ef88de990d6abea0c67d0ea28c1edc` |

All pins were resolved on 2026-08-13 from the named upstream branches. A pin
is re-verified after checkout; a mismatch, missing upstream `fs/nomount`
integration, or existing root integration fails the build.

The workflow snapshots ABI/KMI controls before root integration and verifies
them immediately afterward. It then snapshots the approved, target-specific
SUSFS and device-patch ABI updates before NoMount integration and requires
NoMount to leave that baseline unchanged. The guard covers legacy ABI symbol
lists and the Android 16 Bazel ABI/staging/symbol definitions. It does not
remove protected exports, bypass ABI checks, build a bypass image, create
releases, or claim device compatibility.

## Build-verified only artifact metadata

Successful builds upload a `<target>-Metadata` artifact containing
machine-readable JSON. Its `status` is **`Build-verified only`** only after the
corresponding AnyKernel3 and NoMount metamodule artifacts are uploaded and their
GitHub Actions API URLs and GitHub-issued `sha256` digests are recorded. Each
record also includes the build method, root implementation/manager/version and
commit, SUSFS and NoMount revisions, Android branch/KMI, kernel source commit,
and provenance run URL.

NoMount integration invokes the upstream `kernel/setup.sh` by its full immutable
commit URL and passes that same SHA as the script argument. Each kernel artifact
also receives a separately uploaded NoMount metamodule archive built from the
same SHA; its artifact URL and SHA-256 digest are included in the metadata
record. Kernel and metamodule revisions must match exactly.

The metadata `catalog` object makes publication eligibility explicit:

| Field | Required value |
| --- | --- |
| `availability` | `eligible-with-provenance-and-checksums` |
| `device_compatibility` | `not-validated` |
| `flashability` | `not-guaranteed` |
| `boot` | `not-guaranteed` |

This status means that CI completed the source build and artifact integrity
metadata is available. It is not device validation and does not claim device
compatibility, flashability, or a successful boot. A catalog or release
publisher may expose a successful build artifact only with its provenance URL
and both kernel and matching NoMount metamodule checksums. It must mark an
unbuilt, failed, or metadata-incomplete entry unavailable and provide no
download.

This workflow remains artifact-only: it does not create releases or publish a
catalog. Any separate publisher must enforce this metadata contract.

Runs dispatched before this metadata contract was added cannot retroactively
contain these metadata artifacts. Their artifact digests remain available from
the GitHub Actions artifact API, but they must not be represented as complete
metadata-contract records.
