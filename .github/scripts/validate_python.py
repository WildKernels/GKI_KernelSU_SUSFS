#!/usr/bin/env python3

import ast
import concurrent.futures
import pathlib
import sys

EXCLUDE_DIRS = {".git", "venv", ".venv"}


def find_python_files(root="."):
    for path in pathlib.Path(root).rglob("*.py"):
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        yield path


def check_file(path):
    try:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))
        return path, None
    except SyntaxError as error:
        location = f"line {error.lineno}, col {error.offset}"
        return path, f"{location}: {error.msg}"
    except UnicodeDecodeError as error:
        return path, f"encoding error: {error}"


def main():
    files = sorted(find_python_files())
    if not files:
        print("No Python files found.")
        return 0

    status = 0
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = executor.map(check_file, files)
        for path, error in results:
            if error:
                print(f"Syntax error in: {path}")
                print(f"  {error}")
                status = 1

    print(f"Checked {len(files)} Python file(s).")
    return status


if __name__ == "__main__":
    sys.exit(main())
