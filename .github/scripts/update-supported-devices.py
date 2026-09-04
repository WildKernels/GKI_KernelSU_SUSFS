#!/usr/bin/env python3
"""Update docs/supported-devices.md from a device-support issue."""
import re, sys, datetime, pathlib

ISSUE_BODY = pathlib.Path(sys.argv[1]).read_text() if len(sys.argv) > 1 else sys.stdin.read()
MD = pathlib.Path("docs/supported-devices.md")

def validate_cell(name, value):
    if any(ch in value for ch in ('|', '\r', '\n')):
        print(f"invalid {name}: Markdown delimiters and line breaks are not allowed", file=sys.stderr)
        raise SystemExit(1)
    return value

def field(id):
    # issue form bodies render as "### <Label>\n\nvalue"
    # we match by id label text variations
    labels = {
        "manufacturer": "Manufacturer",
        "custom_manufacturer": "Custom manufacturer (if Other)",
        "device": "Device",
        "codename": "Codename",
        "gki_kernel": "GKI Kernel",
        "firmware": "Firmware",
        "status": "Status",
    }
    label = labels.get(id, id)
    m = re.search(rf"### {re.escape(label)}\s*\n+([^\n#]+)", ISSUE_BODY)
    if m:
        return m.group(1).strip()
    # fallback: try id
    m = re.search(rf"### {re.escape(id)}\s*\n+([^\n#]+)", ISSUE_BODY)
    return m.group(1).strip() if m else ""

heading_map = {
    "Google Pixel": "## Google Pixel",
    "Samsung": "## Samsung",
    "OnePlus": "## OnePlus",
    "OPPO": "## OPPO",
    "Realme": "## Realme",
    "Xiaomi": "## Xiaomi",
    "POCO": "## POCO",
    "Redmi": "## Redmi",
    "Nothing": "## Nothing",
    "Other": "## Other",
}

manufacturer = field("manufacturer") or "Other"
custom_oem = field("custom_manufacturer").strip()
if manufacturer == "Other":
    custom_oem = validate_cell("custom_oem", custom_oem)
device = validate_cell("device", field("device").strip())
codename = validate_cell("codename", field("codename").strip())
gki = validate_cell("gki", field("gki_kernel").strip())
firmware = validate_cell("firmware", field("firmware").strip() or "stock")
status = validate_cell("status", field("status").strip() or "Supported")
# handle custom OEM when Other is selected
if manufacturer == "Other" and custom_oem and custom_oem.lower() not in ("none", "_no response_", ""):
    manufacturer = custom_oem.strip().title()
    heading_map[manufacturer] = f"## {manufacturer}"

if not device or not codename or not gki:
    print("missing required fields", file=sys.stderr)
    sys.exit(0)

heading = heading_map.get(manufacturer, f"## {manufacturer}")
# Xiaomi/POCO/Redmi share same file section expansion if not present -> create heading
text = MD.read_text()
if heading not in text and manufacturer in ("Xiaomi", "POCO", "Redmi"):
    # ensure sections exist (already added as separate? current file has Xiaomi / POCO / Redmi combined? we split?)
    # if missing, append before end
    pass

today = datetime.date.today().isoformat()
status_cell = f"{status} · {today}"
row = f"| {device} | {codename} | {gki} | {firmware} | {status_cell} |"

if heading not in text:
    # append new section at end before source
    text = text.rstrip() + f"\n\n{heading}\n\n| Device | Codename | GKI Kernel | Firmware | Status |\n|--------|----------|------------|----------|--------|\n{row}\n"
    MD.write_text(text)
    print(f"added new heading {heading}")
    sys.exit(0)

# find table under heading
# split by headings
parts = re.split(r"(^## .+$)", text, flags=re.MULTILINE)
out = []
for i, part in enumerate(parts):
    if part.strip() == heading:
        # next part is body until next heading
        body = parts[i+1] if i+1 < len(parts) else ""
        # check duplicate codename
        if re.search(rf"\|\s*{re.escape(device)}\s*\|", body) or re.search(rf"\|\s*[^|]*\|\s*{re.escape(codename)}\s*\|", body):
            print("device already listed, updating not duplicating")
            # replace existing row's status/gki if needed? skip for now
            out.append(part)
            out.append(body)
            continue
        # replace placeholder row if present
        placeholder = "| — | — | — | — | Placeholder — add entries |"
        if placeholder in body:
            new_body = body.replace(placeholder, row, 1)
        else:
            # append row before next heading or at end of table (before blank line + ##)
            # find last table row line
            lines = body.splitlines()
            insert_idx = None
            for idx, line in enumerate(lines):
                if line.startswith("|") and "Device | Codename" in line:
                    # header, continue
                    continue
                if line.startswith("|") and "--------" in line:
                    continue
            # find last row that starts with |
            last = -1
            for idx, line in enumerate(lines):
                if line.startswith("| "):
                    last = idx
            if last >= 0:
                lines.insert(last+1, row)
            else:
                lines.append(row)
            new_body = "\n".join(lines)
        out.append(part)
        out.append(new_body)
    else:
        # already handled body as part of heading case? avoid double
        if i>0 and parts[i-1].strip() == heading:
            continue
        out.append(part)

MD.write_text("".join(out))
print(f"inserted {device} into {heading}")
