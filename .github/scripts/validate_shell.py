#!/usr/bin/env python3

import concurrent.futures
import pathlib
import subprocess
import sys

EXCLUDE_DIRS = {".git"}


def find_shell_files(root="."):
    for path in pathlib.Path(root).rglob("*.sh"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        yield path


def check_file(path):
    result = subprocess.run(
        ["bash", "-n", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return path, result.stderr.strip()
    return path, None


def main():
    files = sorted(find_shell_files())
    if not files:
        print("No shell scripts found.")
        return 0

    status = 0
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = executor.map(check_file, files)
        for path, error in results:
            if error:
                print(f"Syntax error in: {path}")
                print(f"  {error}")
                status = 1

    print(f"Checked {len(files)} shell script(s).")
    return status


if __name__ == "__main__":
    sys.exit(main())
