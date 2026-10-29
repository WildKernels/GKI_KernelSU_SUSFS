#!/usr/bin/env python3
"""Resolve the cache key for the prebuilt/toolchain half of a GKI `repo sync`.

Why this exists
---------------
The prebuilt projects a GKI manifest pins are identical across long stretches of
months, and they are the bulk of the object store:

  * android12-5.10 pins one clang/gcc/build-tools set from 2021-08 through
    2023-01 (measured from the manifests, fingerprint b24849a5...);
  * android16-6.12 pins one set from 2025-07 through 2026-09;
  * android13-5.10 and android13-5.15 pin the same clang (4bb6424c...);
  * prebuilts are 1.5 GB of the 1.7 GB `.repo` on 5.10 and 6.2 GB of the 6.5 GB
    on 6.12.

Re-fetching those bytes in every leg (78-88% of the sync) is the redundancy this
key lets us skip: legs whose prebuilt pins match share one cache asset.

Fingerprint = sha256 over the sorted `name@revision` of the prebuilt-ish projects,
plus the manifest's `<default revision=...>` (newer manifests leave prebuilts on
a branch with no explicit revision, so the branch name is the only stable id).

Usage
-----
    prebuilt_cache_key.py <android-5.10> <2022-02>

Prints a 12-hex key on stdout. Prints nothing and exits 0 when the manifest
cannot be resolved (live or deprecated), so a caller can skip caching instead of
failing the leg.
"""

import base64
import hashlib
import re
import subprocess
import sys
import time

BASE = "https://android.googlesource.com/kernel/manifest/+/refs/heads"
# "platform/prebuilts/clang/...", "kernel/prebuilts/build-tools", "toolchain/..."
PREBUILT_MARKERS = ("prebuilts/", "toolchain/", "/jdk")
PROJECT_RE = re.compile(r"<project\s+([^>]*?)/?>", re.S)
DEFAULT_RE = re.compile(r'<default\b([^>]*)>', re.S)
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def fetch(url, attempts=3):
    for attempt in range(attempts):
        proc = subprocess.run(
            ["curl", "-sS", "--max-time", "25", "-A", "gki-ci-cache-key", url],
            capture_output=True,
        )
        body = proc.stdout
        # googlesource answers a missing ref with HTTP 200 + an HTML page, and
        # ?format=TEXT bodies are base64 -- anything starting with '<' is a miss.
        if body and not body.lstrip().startswith(b"<"):
            try:
                return base64.b64decode(body, validate=False).decode("utf-8", "replace")
            except Exception:
                pass
        time.sleep(1 + attempt)
    return None


def manifest(version, patch):
    branch = f"common-{version}-{patch}"
    for prefix in ("", "deprecated/"):
        text = fetch(f"{BASE}/{prefix}{branch}/default.xml?format=TEXT")
        if text:
            return text
        time.sleep(1)
    return None


def fingerprint(xml):
    default_attrs = {}
    m = DEFAULT_RE.search(xml)
    if m:
        default_attrs = dict(ATTR_RE.findall(m.group(1)))

    pins = {}
    for proj in PROJECT_RE.finditer(xml):
        attrs = dict(ATTR_RE.findall(proj.group(1)))
        name = attrs.get("name")
        if not name or not any(marker in name for marker in PREBUILT_MARKERS):
            continue
        # No explicit revision means "follow <default revision>" (a moving
        # branch on the newer manifests); record that so the key still moves
        # when the branch name changes.
        pins[name] = attrs.get("revision") or f"@{default_attrs.get('revision', '?')}"

    if not pins:
        return None, 0

    digest = hashlib.sha256()
    for name in sorted(pins):
        digest.update(f"{name}@{pins[name]}\n".encode())
    digest.update(f"default={default_attrs.get('revision', '?')}\n".encode())
    return digest.hexdigest()[:12], len(pins)


def main():
    if len(sys.argv) != 3:
        print("usage: prebuilt_cache_key.py <android-5.10> <2022-02>", file=sys.stderr)
        return 2
    version, patch = sys.argv[1], sys.argv[2]
    xml = manifest(version, patch)
    if not xml:
        print(f"prebuilt cache: no manifest for common-{version}-{patch}, skipping",
              file=sys.stderr)
        return 0
    key, count = fingerprint(xml)
    if not key:
        print(f"prebuilt cache: no prebuilt pins in common-{version}-{patch}, skipping",
              file=sys.stderr)
        return 0
    print(f"prebuilt cache: {count} pinned project(s) -> {key}", file=sys.stderr)
    print(key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
