#!/usr/bin/env python3
"""Keep .github/config/<group>.json one-row-per-sublevel.

When a monthly GKI release lands, the matrix gains a row. If that sublevel is
already present (same sublevel re-published, or an older row that was only
`disabled`), REPLACE it: the old row is removed and the new one appended, so a
numeric sublevel never resolves to two rows. This is what the target-card
pre-check needs ("numeric sublevel must occur once").

Usage:
  # add/replace one row
  python3 .github/scripts/update_kernel_matrix.py \
      --group android14-6.1 --sublevel 180 --date 2026-10

  # clean an existing file that already carries duplicates (keeps newest date)
  python3 .github/scripts/update_kernel_matrix.py --group android14-6.1 --dedupe

  # see what would change, write nothing
  ... --dry-run

PR note: with --pr-note <file> the script appends a markdown block describing
every row it replaced or dropped, ready to paste into the PR body.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
LTS_SUBLEVEL = "X"


def load(group: str) -> tuple[Path, dict]:
    path = CONFIG_DIR / f"{group}.json"
    if not path.exists():
        sys.exit(f"no such group config: {path}")
    return path, json.loads(path.read_text())


def sort_key(row: dict) -> tuple[int, str]:
    """LTS rows ('X' / date 'lts') sort last; everything else by date then sublevel."""
    date = str(row.get("date", ""))
    if row.get("sublevel") == LTS_SUBLEVEL or date.lower() == "lts":
        return (1, "")
    return (0, date)


def dedupe(rows: list[dict], notes: list[str], delete: bool = False) -> list[dict]:
    """One ACTIVE row per sublevel: the newest date wins.

    Older duplicates are kept in the file with "disabled": true so they can be
    re-enabled by deleting one word -- deletion only happens with --delete.
    """
    newest: dict[str, dict] = {}
    losers: list[dict] = []
    for row in rows:
        sub = str(row.get("sublevel"))
        if sub == LTS_SUBLEVEL:
            continue
        cur = newest.get(sub)
        if cur is None or str(row.get("date", "")) > str(cur.get("date", "")):
            if cur is not None:
                losers.append(cur)
                notes.append(
                    f"- {'removed' if delete else 'disabled'} duplicate `{sub}` @ {cur.get('date')} "
                    f"(superseded by {row.get('date')})"
                )
            newest[sub] = row
        else:
            losers.append(row)
            notes.append(
                f"- {'removed' if delete else 'disabled'} duplicate `{sub}` @ {row.get('date')} "
                f"(superseded by {cur.get('date')})"
            )
    lts = [r for r in rows if str(r.get("sublevel")) == LTS_SUBLEVEL]
    if delete:
        return sorted([*newest.values(), *lts], key=sort_key)
    for row in losers:
        row["disabled"] = True
    return sorted([*newest.values(), *losers, *lts], key=sort_key)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True, help="e.g. android14-6.1")
    ap.add_argument("--sublevel", help="numeric sublevel to add/replace")
    ap.add_argument("--date", help="YYYY-MM of the release (required with --sublevel)")
    ap.add_argument("--variant", help="optional variant marker carried on the new row")
    ap.add_argument("--dedupe", action="store_true", help="collapse existing duplicates")
    ap.add_argument("--delete", action="store_true", help="remove superseded rows instead of disabling them")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pr-note", help="append a markdown summary to this file")
    args = ap.parse_args()

    if not args.dedupe and not args.sublevel:
        sys.exit("pass --sublevel/--date, or --dedupe")

    path, doc = load(args.group)
    rows = list(doc.get("include", []))
    before = len(rows)
    notes: list[str] = []

    if args.sublevel:
        if not args.date:
            sys.exit("--date is required with --sublevel")
        sub = str(args.sublevel)
        kept = []
        existed_identical = False
        for row in rows:
            if str(row.get("sublevel")) == sub:
                if str(row.get("date")) == str(args.date) and not row.get("disabled"):
                    existed_identical = True
                if args.delete:
                    notes.append(
                        f"- removed `{sub}` @ {row.get('date')}"
                        + (" (was disabled)" if row.get("disabled") else "")
                        + f" (superseded by {args.date})"
                    )
                else:
                    # Keep the row, switch it off: re-enabling is deleting one word.
                    notes.append(
                        f"- disabled `{sub}` @ {row.get('date')}"
                        + (" (already disabled)" if row.get("disabled") else "")
                        + f" (superseded by {args.date})"
                    )
                    row["disabled"] = True
                    kept.append(row)
            else:
                kept.append(row)
        if existed_identical:
            notes = [n for n in notes if not n.startswith(f"- replaced `{sub}`")]
            notes.append(f"- `{sub}` @ {args.date} already present — unchanged")
        new_row: dict = {"sublevel": sub, "date": args.date}
        if args.variant:
            new_row["variant"] = args.variant
        kept.append(new_row)
        rows = kept

    if args.dedupe or args.sublevel:
        rows = dedupe(rows, notes, delete=args.delete)

    doc["include"] = rows
    replaced = before - len(rows) + (1 if args.sublevel else 0)

    summary = [
        f"### Kernel matrix: `{args.group}`",
        "",
        f"- rows before: {before} → after: {len(rows)}",
    ]
    summary += notes or ["- no duplicate sublevels found"]
    block = "\n".join(summary) + "\n"

    if args.dry_run:
        print(block)
        print("(dry run — nothing written)")
        return 0

    path.write_text(json.dumps(doc, indent=2) + "\n")
    print(block)
    print(f"wrote {path}")

    if args.pr_note:
        with open(args.pr_note, "a") as fh:
            fh.write("\n" + block)
        print(f"appended PR note to {args.pr_note}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
