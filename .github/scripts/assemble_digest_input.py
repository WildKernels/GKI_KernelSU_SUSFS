#!/usr/bin/env python3
"""Assemble the Telegram digest input from the BuildInfo artifacts builds
already upload - zero new artifacts.

Every successful build leg uploads a `<file_name>-BuildInfo` artifact (build
summary markdown with an embedded verified-metadata JSON block carrying kmi,
root implementation, root commit, page size, and the kernel artifact's URL,
which contains its artifact ID). The announce downloads those with
actions/download-artifact (the runtime artifact service, not the REST jobs
listing, which 502/504s on 600+ job runs under platform stress) and this
script synthesizes the exact shapes telegram_digest.py already consumes:

  jobs-out:      [{"name": ..., "conclusion": ...}, ...]
  artifacts-out: [{"name": ..., "id": ...}, ...]

Synthesized job names reproduce the format the digest parser expects, e.g.:

  build-android14-6-1 (bakasu, BakaSU, <40-hex>) / 6.1.141-android14-2025-07 (BakaSU)

so telegram_digest.py runs unchanged. Only successful legs have BuildInfo,
so the caller passes the per-family job results (--family-results
"job=result,job=result"): any family that did not finish 'success' (or
'skipped' = not requested) means failures the BuildInfo records cannot
show, and the script exits 3 so the caller falls back to the REST jobs
fetch for the full picture with per-leg failure marks.
"""
import argparse
import json
import os
import re
import sys

# Display label -> root id (inverse of ROOT_MATRIX in main.yml).
RID_BY_LABEL = {
    "KernelSU-Next": "next",
    "KernelSU": "kernelsu",
    "BakaSU": "bakasu",
    "SukiSU-Ultra": "sukisu-ultra",
    "KowSU": "kowsu",
}
# Longest-first so 'KernelSU' doesn't shadow 'KernelSU-Next'.
LABELS = sorted(RID_BY_LABEL, key=len, reverse=True)

BUILDINFO_SUFFIX = "-BuildInfo"
JSON_FENCE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
ARTIFACT_ID = re.compile(r"/actions/artifacts/(\d+)")


def family_of(kmi: str) -> str:
    """'android14-6.1' -> 'build-android14-6-1' (the digest's family key)."""
    return "build-" + kmi.replace(".", "-")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--buildinfo-dir", required=True,
                    help="directory holding downloaded *-BuildInfo artifacts "
                         "(each in its own subdirectory named after the "
                         "artifact)")
    ap.add_argument("--family-results", default="",
                    help="comma-separated job=result pairs, e.g. "
                         "'build-android14-6-1=success,...'")
    ap.add_argument("--jobs-out", required=True)
    ap.add_argument("--artifacts-out", required=True)
    args = ap.parse_args()

    # 1) A family that failed or was cancelled means BuildInfo alone cannot
    # show the failures - signal the caller to use the REST fallback.
    for pair in filter(None, args.family_results.split(",")):
        job, _, result = pair.partition("=")
        result = result.strip()
        if result not in ("success", "skipped", ""):
            print(f"assemble-digest: {job} result={result!r}; "
                  f"BuildInfo records can't show failures - "
                  f"falling back to the jobs API", file=sys.stderr)
            return 3

    root = args.buildinfo_dir
    if not os.path.isdir(root):
        print(f"assemble-digest: BuildInfo dir {root} missing",
              file=sys.stderr)
        return 3

    jobs, artifacts = [], []
    seen = set()
    legs = bad = 0
    for entry in sorted(os.listdir(root)):
        subdir = os.path.join(root, entry)
        if not os.path.isdir(subdir) or not entry.endswith(BUILDINFO_SUFFIX):
            continue
        file_name = entry[: -len(BUILDINFO_SUFFIX)]
        md_path = None
        for fn in os.listdir(subdir):
            if fn.endswith(".md"):
                md_path = os.path.join(subdir, fn)
                break
        if md_path is None:
            bad += 1
            continue
        try:
            with open(md_path) as fh:
                text = fh.read()
            m = JSON_FENCE.search(text)
            meta = json.loads(m.group(1)) if m else {}
        except (OSError, ValueError) as exc:
            bad += 1
            print(f"assemble-digest: unparseable BuildInfo {entry}: {exc}",
                  file=sys.stderr)
            continue

        flavor = ""
        for label in LABELS:
            if file_name.endswith("-" + label):
                flavor = label
                break
        if not flavor:
            bad += 1
            print(f"assemble-digest: can't find flavor label in {entry}",
                  file=sys.stderr)
            continue
        tag = file_name[: -(len(flavor) + 1)]
        if tag.endswith("-16k"):
            tag = tag[: -len("-16k")]  # display tag matches the job-name form

        rid = RID_BY_LABEL[flavor]
        kmi = str(meta.get("kmi", ""))
        commit = str(meta.get("root", {}).get("commit", "none"))
        name = (f"{family_of(kmi)} ({rid}, {flavor}, {commit}) / "
                f"{tag} ({flavor})")
        if name in seen:
            continue
        seen.add(name)
        jobs.append({"name": name, "conclusion": "success"})
        legs += 1

        art_id_m = ARTIFACT_ID.search(str(meta.get("artifact_url", "")))
        if art_id_m:
            artifacts.append({"name": file_name + "-AnyKernel3",
                              "id": art_id_m.group(1)})

    print(f"assemble-digest: {legs} BuildInfo legs, {bad} unparseable -> "
          f"{len(jobs)} jobs, {len(artifacts)} kernel artifacts")

    if not jobs:
        print("assemble-digest: no BuildInfo records at all; "
              "falling back to the jobs API", file=sys.stderr)
        return 3

    with open(args.jobs_out, "w") as fh:
        json.dump(jobs, fh)
    with open(args.artifacts_out, "w") as fh:
        json.dump(artifacts, fh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
