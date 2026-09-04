#!/usr/bin/env python3
"""Promote latest-built commits to the verified PIN_* block in main.yml.

Update mode: builds happen at latest tips. After the build, if the components
built this run all passed, their used SHAs overwrite the audited pins. Previous
audited pins are recorded in .github/pins/history/<date>.json before being
replaced. Only components that were enabled AND passed are promoted; unrelated
pins are left untouched.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from uuid import uuid4

REPO = os.environ.get("GITHUB_WORKSPACE", ".")
MAIN = os.path.join(REPO, ".github/workflows/main.yml")

# (pin-var, resolved-sha-env, approval-env)
# approval env is "1"/"true" when the component was enabled and all its builds passed.
PINS = [
    ("PIN_NOMOUNT", "NOMOUNT_SHA", "APPROVE_NOMOUNT"),
    ("PIN_KERNELSU", "KERNELSU_SHA", "APPROVE_KERNELSU"),
    ("PIN_RESUKISU", "RESUKISU_SHA", "APPROVE_RESUKISU"),
    # SUSFS is intentionally excluded: it is always resolved at latest so it
    # stays API-matched to the always-latest KernelSU-Next tree.
]

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def approved(env):
    return os.environ.get(env, "").strip() in ("1", "true", "True")


def read_pins():
    """Return dict {var_name: sha} from the current PIN_* block in main.yml."""
    with open(MAIN, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    pins = {}
    for var, _, _ in PINS:
        pattern = re.compile(
            rf'^[ \t]*{re.escape(var)}(?P<assignment>[ \t]*=[^\r\n]*)?[ \t]*(?=\r?$)',
            re.MULTILINE,
        )
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            raise ValueError(f"expected exactly one {var} assignment, found {len(matches)}")
        value = re.fullmatch(r'="([0-9a-f]{40})"[ \t]*', matches[0].group("assignment") or "")
        if value is None:
            raise ValueError(f"invalid {var} assignment")
        pins[var] = value.group(1)
    return pins


def build_changes():
    changes = []          # (var, old_sha, new_sha)
    promoted = {}         # key -> sha for pins being set
    for var, sha_env, approve_env in PINS:
        new_sha = os.environ.get(sha_env, "").strip().lower()
        if not SHA_RE.match(new_sha):
            print(f"  skip {var}: resolved SHA invalid ({new_sha})", file=sys.stderr)
            continue
        if not approved(approve_env):
            print(f"  skip {var}: not approved to promote (disabled or a build failed)", file=sys.stderr)
            continue
        old_sha = read_pins().get(var)
        if old_sha == new_sha:
            print(f"  unchanged {var} ({new_sha[:8]})")
            continue
        promoted[var] = new_sha
        changes.append((var, old_sha, new_sha))
    return changes, promoted


def history_path():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    d = os.path.join(REPO, ".github/pins/history")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{ts}-{uuid4().hex[:8]}.json")


def write_history(changes, path):
    record = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "previous_verified": {key: (old or "") for key, old, _ in changes},
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
        fh.write("\n")
    print(f"  history written: {os.path.relpath(path, REPO)}")


def apply_pins(promoted):
    with open(MAIN, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    replacements = []
    for key, sha in promoted.items():
        pattern = re.compile(
            rf'^[ \t]*{re.escape(key)}(?P<assignment>[ \t]*=[^\r\n]*)?[ \t]*(?=\r?$)',
            re.MULTILINE,
        )
        matches = list(pattern.finditer(text))
        if len(matches) != 1:
            raise ValueError(f"expected exactly one {key} assignment, found {len(matches)}")
        match = matches[0]
        value = re.fullmatch(r'="([0-9a-f]{40})"[ \t]*', match.group("assignment") or "")
        if value is None:
            raise ValueError(f"invalid {key} assignment")
        line = match.group(0)
        indentation = line[: len(line) - len(line.lstrip(" \t"))]
        trailing = line[len(line.rstrip(" \t")) :]
        replacements.append((match.start(), match.end(), f'{indentation}{key}="{sha}"{trailing}'))

    for start, end, replacement in reversed(replacements):
        text = text[:start] + replacement + text[end:]

    with open(MAIN, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return True


def main():
    changes, promoted = build_changes()
    if not changes:
        print("No pins to promote (nothing changed or nothing approved).")
        return 0
    hist = history_path()
    write_history(changes, hist)
    if not apply_pins(promoted):
        return 1
    print("Promoted pins:")
    for key, old, new in changes:
        print(f"  {key}: {old[:8] if old else 'none'} -> {new[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())