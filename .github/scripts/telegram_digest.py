#!/usr/bin/env python3
"""Build per-family Telegram digest messages from a workflow run's jobs.

Input : the run's jobs JSON (actions API, all pages merged) on stdin.
Output: one line per kernel family, TAB-separated:
        <topic_id>\t<html>
        The caller posts each line to that topic via sendMessage.

CARD FORMAT (rich): when a local Bot API server (Bot API 10.x) is
available the caller posts the rich-markdown variant via sendRichMessage
- real tables, styled button rows, expandable quotes. The cloud HTML
variant + inline keyboard JSON always ride along as the fallback.

  Rich-card idea and markup vocabulary (sendRichMessage, <table
  bordered>, <tg-button-row>/<tg-button>, <blockquote expandable>)
  adapted from nullptr-t-oss/Dragonw1nd-Kernels (.github/telegram/).
  Every card carries a footer credit to them.

Routing (topic IDs in the Wild Kernels Testing forum, editable in place):
  build-android12-5-10 -> 3   (5.10.x-android12)
  build-android13-5-10 -> 5   (5.10.x-android13)
  build-android13-5-15 -> 7   (5.15.x-android13; shares the 5.15 topic)
  build-android14-5-15 -> 7   (5.15.x-android14)
  build-android14-6-1  -> 9   (6.1.x-android14)
  build-android15-6-6  -> 13  (6.6.x-android15)
  build-android16-6-12 -> 15  (6.12.x-android16, incl. the lts sublevel)
  build-android17-6-18 -> 17  (6.18.x-android17, placeholder family)
Unmapped families fall back to topic 3 so nothing is silently dropped.

Job names for callable-workflow runs look like:
  build-android15-6-6 (next, KernelSU-Next, 956ea0f5...) / build (...) / 6.6.82-android15-2025-04 (KernelSU-Next)
The first segment identifies the family job; the last carries the
sublevel/os tag and the root flavor.

Usage: telegram_digest.py --run-id ID --branch BR --event EV
                          --run-url URL --nightly-url URL < jobs.json
"""
import argparse
import fnmatch
import html
import json
import os
import re
import sys

TOPICS = {
    "build-android12-5-10": "3",
    "build-android13-5-10": "5",
    "build-android13-5-15": "7",
    "build-android14-5-15": "9",
    "build-android14-6-1": "11",
    "build-android15-6-6": "13",
    "build-android16-6-12": "15",
    "build-android17-6-18": "17",
}

# build job id -> SUSFS branch variant (release-notes naming), used to pick
# the family's SUSFS pin from the SUSFS_* env vars.
VARIANT_OF_FAM = {
    "build-android12-5-10": "android12-5.10",
    "build-android13-5-10": "android13-5.10",
    "build-android13-5-15": "android13-5.15",
    "build-android14-5-15": "android14-5.15",
    "build-android14-6-1": "android14-6.1",
    "build-android15-6-6": "android15-6.6",
    "build-android16-6-12": "android16-6.12",
}
FALLBACK_TOPIC = "3"

# Excluded helper jobs that share the build- prefix
EXCLUDED = {"build-nomount-module"}

FAMILY_NAMES = {
    "build-android12-5-10": "5.10.x-android12",
    "build-android13-5-10": "5.10.x-android13",
    "build-android13-5-15": "5.15.x-android13",
    "build-android14-5-15": "5.15.x-android14",
    "build-android14-6-1": "6.1.x-android14",
    "build-android15-6-6": "6.6.x-android15",
    "build-android16-6-12": "6.12.x-android16",
    "build-android17-6-18": "6.18.x-android17",
}

MARKS = {"success": "✅", "failure": "❌", "cancelled": "⛔",
         "skipped": "⏭️", "startup_failure": "❌"}

MAX_LEN = 4000  # Telegram cap is 4096; leave headroom for entities
RICH_MAX_LEN = 32000  # Bot API 10.x rich message cap is ~32768

# Root repo -> commit URL base (shared by the HTML and rich cards).
ROOT_URLS = {
    "next": "https://github.com/pershoot/KernelSU-Next/commit/",
    "kernelsu": "https://github.com/tiann/KernelSU/commit/",
    "bakasu": "https://github.com/Baka-SU/BakaSU/commit/",
    "sukisu-ultra": "https://github.com/SukiSU-Ultra/SukiSU-Ultra/commit/",
    "kowsu": "https://github.com/KOWX712/KernelSU/commit/",
}

# Flavor -> manager APK artifact patterns (fnmatch against the run's
# uploaded artifact names; first non-excluded match wins per entry).
# BakaSU (formerly ReSukiSU) ships its manager as BakaSU_v*. KernelSU-Next ships a spoofed
# variant: the stock manager links the flavor name, the spoofed one gets
# a suffix link.
FLAVOR_MANAGERS = {
    "KernelSU": [("KernelSU_v*", None)],
    "KernelSU-Next": [("KernelSU_Next_v*", "spoofed"),
                      ("KernelSU_Next_v*spoofed*", None)],
    # BakaSU ships a spoofed manager too (Spoofed-Manager-release in
    # their Build Manager CI; our publish filter keeps the universal
    # pair) - link it like KernelSU-Next's.
    "BakaSU": [("BakaSU_v*", "spoofed"),
               ("BakaSU_v*spoofed*", None)],
}


def load_json_any(stream) -> list:
    """Accept a single JSON object/array OR gh api --paginate's
    concatenated pages; merge every list found under common keys
    ('jobs', 'artifacts') or a bare top-level array."""
    text = stream.read()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for key in ("jobs", "artifacts"):
                if isinstance(data.get(key), list):
                    return data[key]
            return []
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        pass
    dec = json.JSONDecoder()
    items, idx, n = [], 0, len(text)
    while idx < n:
        while idx < n and text[idx] in " \t\r\n":
            idx += 1
        if idx >= n:
            break
        obj, end = dec.raw_decode(text, idx)
        idx = end
        if isinstance(obj, dict):
            for key in ("jobs", "artifacts"):
                if isinstance(obj.get(key), list):
                    items.extend(obj[key])
        elif isinstance(obj, list):
            items.extend(obj)
    return items


def family_of(job_name: str) -> str:
    return job_name.split(" / ")[0].split(" (")[0].strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--event", required=True)
    ap.add_argument("--run-url", required=True)
    ap.add_argument("--nightly-url", required=True)
    ap.add_argument("--artifacts-file", default="",
                    help="JSON (single object or concatenated pages) of the "
                         "run's artifacts; enables per-flavor manager links")
    ap.add_argument("--test-chat", default="",
                    help="second chat (testing release group) that gets one "
                         "combined 'new testing release' card")
    ap.add_argument("--test-topic", default="",
                    help="forum topic inside --test-chat for that card")
    ap.add_argument("--chat-id", required=True,
                    help="main announcements chat (per-family digests)")
    args = ap.parse_args()

    artifacts = []
    if args.artifacts_file:
        try:
            with open(args.artifacts_file) as fh:
                artifacts = load_json_any(fh)
        except (OSError, ValueError) as exc:
            print(f"telegram-digest: artifacts parse failed ({exc}); "
                  f"flavor links disabled", file=sys.stderr)
            artifacts = []

    def manager_links(flavor: str) -> list:
        """nightly.link deep links to this flavor's manager APK artifacts.

        Links go by artifact ID (/{repo}/actions/artifacts/{id}.zip) - the
        by-name route can't match names containing dots (every .apk artifact
        404s there), and manager artifacts keep their versioned names.
        """
        import fnmatch
        by_name = {}
        for a in artifacts:
            if "name" in a and "id" in a:
                by_name.setdefault(a["name"], a["id"])
        names = sorted(by_name)
        urls = []
        for pat, excl in FLAVOR_MANAGERS.get(flavor, []):
            for n in names:
                if fnmatch.fnmatch(n, pat) and (not excl or excl not in n):
                    urls.append(
                        f"{args.nightly_url.rsplit('/actions/runs/', 1)[0]}"
                        f"/actions/artifacts/{by_name[n]}.zip")
                    break
        return urls

    data = load_json_any(sys.stdin)
    jobs = data if isinstance(data, list) else []
    if not jobs:
        print("telegram-digest: no jobs in input", file=sys.stderr)
        return 1

    fams = {}
    for j in jobs:
        name = j.get("name") or ""
        fam = family_of(name)
        if not fam.startswith("build-android") or fam in EXCLUDED:
            continue  # resolve-sources, nomount, rej, release, ...
        e = fams.setdefault(fam, {"sublevels": [], "flavors": [],
                                  "counts": {}, "sub_jobs": {}, "root": None})
        # The matrix parent part embeds the root: "build-android15-6-6
        # (next, KernelSU-Next, <40-hex-sha>) / <sublevel> (<flavor>)".
        if e["root"] is None:
            parent = name.split(" / ")[0]
            if "(" in parent:
                inner = parent[parent.index("(") + 1:parent.rindex(")")]
                bits = [b.strip() for b in inner.split(",")]
                if len(bits) >= 3 and len(bits[2]) == 40:
                    e["root"] = (bits[0], bits[1], bits[2])
        last = name.split(" / ")[-1]
        if " / " in name and "(" in last:
            tag = last.rsplit(" (", 1)[0]
            flavor = last.rsplit(" (", 1)[1].rstrip(")")
            if tag and tag not in e["sublevels"]:
                e["sublevels"].append(tag)
            if flavor and flavor not in e["flavors"]:
                e["flavors"].append(flavor)
            sj = e["sub_jobs"].setdefault(tag, {})
            c = j.get("conclusion") or j.get("status") or "unknown"
            sj[c] = sj.get(c, 0) + 1
        c = j.get("conclusion") or j.get("status") or "unknown"
        e["counts"][c] = e["counts"].get(c, 0) + 1

    # A family whose every job was skipped (single-family dispatch gates
    # the rest off) carries no information - drop it instead of posting
    # an empty card into its topic.
    fams = {f: e for f, e in fams.items()
            if any(k != "skipped" for k in e["counts"])}

    icon = "🌙" if args.event == "schedule" else "🔨"
    for fam, e in sorted(fams.items()):
        topic = TOPICS.get(fam, FALLBACK_TOPIC)
        fname = FAMILY_NAMES.get(fam, fam)
        esc = html.escape

        counts = "  ".join(f"{MARKS.get(k, '•')} {v}"
                           for k, v in sorted(e["counts"].items()))

        # Numeric sort: sublevel then os date ("6.6.102-...-2025-10" AFTER
        # "6.6.118-...-2026-01"? No - 118 > 102, and 2026 > 2025). Lexicographic
        # puts 6.6.102 before 6.6.30 - wrong. X (lts) sorts last.
        def sub_key(tag: str):
            parts = tag.split("-")
            sub = parts[2] if len(parts) >= 3 else "0"
            sub_num = 10 ** 9 if sub.upper() == "X" else \
                int("".join(ch for ch in sub if ch.isdigit()) or 0)
            date_num = 0
            for p in parts[3:]:
                digits = "".join(ch for ch in p if ch.isdigit())
                date_num = date_num * 10000 + (int(digits) if digits else 0)
            return (sub_num, date_num, tag)

        subs = sorted(e["sublevels"], key=sub_key)

        # Per-sublevel lines: passing sublevels link their AnyKernel3
        # artifact (KernelSU-Next preferred, then KernelSU, then BakaSU);
        # sublevels with any failed/cancelled job get a ❌ mark and no link.
        art_base = args.nightly_url.rsplit("/actions/runs/", 1)[0]
        # Per-(sublevel, flavor) artifact links: every root flavor that
        # built a sublevel gets its own link (a KernelSU-Next + BakaSU
        # dispatch produces two kernels per version - both link).
        FLAVOR_ORDER = ["KernelSU-Next", "KernelSU", "BakaSU",
                        "SukiSU-Ultra", "KowSU"]
        flav_order = [f for f in FLAVOR_ORDER if f in e["flavors"]] + \
                     sorted(f for f in e["flavors"] if f not in FLAVOR_ORDER)
        sub_flav = {}  # (tag, flavor) -> nightly.link url
        for s in subs:
            for f in flav_order:
                art_name = f"{s}-{f}-AnyKernel3"
                # LTS runs build a REAL kernel version, so the artifact is
                # named e.g. 6.6.144-android15-lts-... while the job tag is
                # 6.6.X-android15-lts (run 38210657645 posted the lts line
                # with no link). Match exactly first, then glob the X away
                # (X sits before '-' in lts tags, so match on ".X" followed
                # by a '-' or '.' boundary, not the ".X." substring).
                pat = None
                if re.search(r"\.X(?=[.-])", art_name):
                    pat = re.sub(r"\.X(?=[.-])", ".*", art_name)
                for a in artifacts:
                    aname = a.get("name", "")
                    if "id" not in a:
                        continue
                    if aname == art_name or (pat and fnmatch.fnmatch(aname, pat)):
                        sub_flav[(s, f)] = f"{art_base}/actions/artifacts/{a['id']}.zip"
                        break

        # Per-sublevel lines: every built flavor links separately.
        sub_lines = []
        rich_subs_list = []
        for s in subs:
            links = [(f, sub_flav[(s, f)]) for f in flav_order
                     if (s, f) in sub_flav]
            if links:
                h = "  ·  ".join(
                    f"<a href=\"{html.escape(u, quote=True)}\">{esc(f)}</a>"
                    for f, u in links)
                sub_lines.append(f"- {esc(s)} — {h}")
                r = " · ".join(f"[{f}]({u})" for f, u in links)
                rich_subs_list.append(f"- {esc(s)} — {r}")
            else:
                sub_lines.append(f"- ❌ {esc(s)}")
                rich_subs_list.append(f"- ❌ {esc(s)}")
        sub_text = "\n".join(sub_lines) if sub_lines else "—"
        rich_subs = "\n".join(rich_subs_list) if rich_subs_list else "—"

        # Family gate: zero linked kernels means nothing built for this
        # family (every sublevel failed) - skip the card entirely instead
        # of posting an all-❌ notice. Families with at least one built
        # kernel still post, failures shown per-sublevel.
        if not sub_flav:
            print(f"telegram-digest: {fname}: no AnyKernel3 artifacts "
                  f"(no kernels built); skipping card", file=sys.stderr)
            continue

        # Flavors, each linking its manager APK when the run uploaded one.
        # The flavor name links the stock manager; KernelSU-Next gets a
        # trailing "spoofed" link for its second variant.
        flines = []
        rich_fl = []
        for f in sorted(e["flavors"]):
            links = manager_links(f)
            if not links:
                flines.append(esc(f))
                rich_fl.append(esc(f))
                continue
            line = f"<a href=\"{html.escape(links[0], quote=True)}\">" \
                   f"{esc(f)}</a>"
            rf = f"[{esc(f)}]({links[0]})"
            if len(links) > 1:
                line += "  ·  " + "  ·  ".join(
                    f"<a href=\"{html.escape(u, quote=True)}\">spoofed</a>"
                    for u in links[1:])
                rf += " · " + " · ".join(f"[spoofed]({u})" for u in links[1:])
            flines.append(line)
            rich_fl.append(rf)
        flavors = "\n".join(flines) if flines else "—"
        rich_flavors = "\n".join(rich_fl) if rich_fl else "—"

        # Root + Features + SUSFS commit info, mirroring the release notes
        # (main.yml notes-preview job). The root comes from the job names;
        # component commits + the SUSFS pin per family arrive via env vars
        # fed from resolve-sources outputs. Empty env = the line is skipped,
        # so a failed resolve-sources degrades gracefully.
        root_line = ""
        if e.get("root"):
            rid, rlabel, rsha = e["root"]
            rurl = ROOT_URLS.get(rid)
            if rurl:
                root_line = (f"<b>Root</b>: {esc(rlabel)} "
                             f"<a href=\"{rurl}{rsha}\">{esc(rsha[:7])}</a>")
            else:
                root_line = (f"<b>Root</b>: {esc(rlabel)} "
                             f"<code>{esc(rsha[:7])}</code>")

        # Features: exactly what THIS run's feature_set carried (the
        # resolve-sources output feeds DIGEST_FEATURES, "+"-separated;
        # the old comma form is accepted too). One line per feature -
        # NTSync/Ptrace/Unicode are their own features, not a group.
        feats_on = {s.strip().lower()
                    for s in re.split(r"[+,]", os.environ.get("DIGEST_FEATURES", ""))
                    if s.strip()}
        variant = VARIANT_OF_FAM.get(fam, "")
        susfs_sha = os.environ.get(
            "SUSFS_" + variant.replace(".", "_").replace("-", "_").upper(), "")
        flines2 = []
        rlines2 = []
        susfs_url = "https://gitlab.com/simonpunk/susfs4ksu/-/commit/"
        nomount_url = "https://github.com/maxsteeel/nomount/commit/"
        bbg_url = "https://github.com/WildKernels/kernel_patches/commit/"
        ds_url = "https://github.com/ravindu644/Droidspaces-OSS/commit/"
        if "susfs" in feats_on:
            if susfs_sha:
                flines2.append(f"- SUSFS <a href=\"{susfs_url}{susfs_sha}\">"
                               f"{esc(susfs_sha[:7])}</a>")
                rlines2.append(f"- **SUSFS**: [{susfs_sha[:7]}]({susfs_url}{susfs_sha})")
            else:
                flines2.append("- SUSFS")
                rlines2.append("- **SUSFS**")
        if "nomount" in feats_on and (c := os.environ.get("NOMOUNT_COMMIT", "")):
            flines2.append(f"- NoMount <a href=\"{nomount_url}{c}\">{esc(c[:7])}</a>")
            rlines2.append(f"- **NoMount**: [{c[:7]}]({nomount_url}{c})")
        if "bbg" in feats_on and (c := os.environ.get("KERNEL_PATCHES_COMMIT", "")):
            flines2.append(f"- Baseband Guard <a href=\"{bbg_url}{c}\">{esc(c[:7])}</a>")
            rlines2.append(f"- **Baseband Guard**: [{c[:7]}]({bbg_url}{c})")
        if "ds" in feats_on and (c := os.environ.get("DROIDSPACES_COMMIT", "")):
            flines2.append(f"- DroidSpaces-OSS <a href=\"{ds_url}{c}\">{esc(c[:7])}</a>")
            rlines2.append(f"- **DroidSpaces-OSS**: [{c[:7]}]({ds_url}{c})")
        if "net" in feats_on:
            flines2.append("- Networking")
            rlines2.append("- **Networking**")
        if "ntsync" in feats_on:
            flines2.append("- NTSync")
            rlines2.append("- **NTSync**")
        if "ptrace" in feats_on:
            flines2.append("- Ptrace Leak Fix")
            rlines2.append("- **Ptrace Leak Fix**")
        if "unicode" in feats_on:
            flines2.append("- Unicode Fix")
            rlines2.append("- **Unicode Fix**")
        if "bpf" in feats_on:
            flines2.append("- BTF / eBPF / FUSE-BPF")
            rlines2.append("- **BTF / eBPF / FUSE-BPF**")
        if "perf" in feats_on:
            flines2.append("- Performance patches")
            rlines2.append("- **Performance patches**")
        feat_text = "\n".join(flines2)
        feat_rich = "\n".join(rlines2)

        # Buttons (URL only - no backend needed), one source for both the
        # JSON inline keyboard (cloud fallback) and the rich card:
        #   - one download button per BUILT kernel, full kernel string as
        #     the label (6.1.157-android14-2025-12); sublevels built by
        #     MULTIPLE flavors get one button per flavor (suffixed), on
        #     their own row. Single-flavor sublevels pack 2 per row.
        #   - manager APK buttons, one row per flavor (name + spoofed)
        #   - all-artifacts row
        btn_rows = []  # list of rows; each row = list[(text, url)]
        pool = []
        for s in reversed(subs):
            ls = [(f, sub_flav[(s, f)]) for f in flav_order
                  if (s, f) in sub_flav]
            if not ls:
                continue
            if len(ls) == 1:
                pool.append((f"⬇️ {s}", ls[0][1]))
                if len(pool) == 2:
                    btn_rows.append(pool)
                    pool = []
            else:
                if pool:
                    btn_rows.append(pool)
                    pool = []
                for f, u in ls:  # one button per row: full string + flavor
                    btn_rows.append([(f"⬇️ {s} · {f}", u)])
        if pool:
            btn_rows.append(pool)
        mgr_rows = []
        for f in sorted(e["flavors"]):
            links = manager_links(f)
            if not links:
                continue
            row = [(f"🧩 {f}", links[0])]
            row += [("spoofed", u) for u in links[1:]]
            mgr_rows.append(row)

        kb_rows = [[{"text": t, "url": u} for t, u in row]
                   for row in btn_rows + mgr_rows]
        kb_rows.append([{"text": "📦 All artifacts", "url": args.nightly_url}])
        buttons = json.dumps({"inline_keyboard": kb_rows},
                             separators=(",", ":"), ensure_ascii=False)

        # ---- Rich-markdown variant (Bot API 10.x sendRichMessage) ----
        # Table / button-row / expandable-quote vocabulary adapted from
        # nullptr-t-oss/Dragonw1nd-Kernels (.github/telegram/telegram.py).
        # Only proven-rendering constructs are used: links live in plain
        # markdown positions (list items, standalone lines) - never inside
        # table cells; table cells carry plain text only. No credit footer
        # in the message (attribution lives in this header).
        rich_parts = [f"# {icon} Wild Kernels"]
        trows = [
            ("Branch", esc(args.branch)),
            ("Trigger", esc(args.event)),
            ("Jobs", esc(counts)),
        ]
        tbody = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in trows)
        rich_parts.append(
            f'<table bordered><tr><th colspan="2" align="center">'
            f"{esc(fname)}</th></tr>{tbody}</table>")
        rich_parts.append(f"Run: [#{args.run_id}]({args.run_url})")
        if e.get("root"):
            rid, rlabel, rsha = e["root"]
            rurl = ROOT_URLS.get(rid)
            if rurl:
                rich_parts.append(f"Root: [{esc(rlabel)} {rsha[:7]}]({rurl}{rsha})")
            else:
                rich_parts.append(f"Root: {esc(rlabel)} {rsha[:7]}")
        if feat_text:
            rich_parts.append(f"**Features**\n{feat_rich}")
        # No Sublevels/Flavors sections here: the button rows below carry
        # the same info (one download button per kernel, manager buttons
        # per flavor) - the user asked for the leaner card.
        # Buttons: per-kernel downloads (success; multi-flavor sublevels
        # get flavor-suffixed rows), managers (primary).
        for row in btn_rows:
            cells = "".join(
                f'<tg-button type="url" style="success" url="{u}">{t}</tg-button>'
                for t, u in row)
            rich_parts.append(f"<tg-button-row>{cells}</tg-button-row>")
        for row in mgr_rows:
            cells = "".join(
                f'<tg-button type="url" style="primary" url="{u}">{t}</tg-button>'
                for t, u in row)
            rich_parts.append(f"<tg-button-row>{cells}</tg-button-row>")
        rich = "\n\n".join(rich_parts)
        if len(rich) > RICH_MAX_LEN:
            rich = rich[:RICH_MAX_LEN - 1] + "…"

        root_block = f"{root_line}\n\n" if root_line else ""
        feat_block = f"<b>Features</b>:\n{feat_text}\n\n" if feat_text else ""
        msg = (
            f"<b>{icon} Wild Kernels</b>\n"
            f"\n"
            f"<b>{esc(fname)}</b>\n"
            f"\n"
            f"<b>Branch</b>: <code>{esc(args.branch)}</code>\n"
            f"<b>Trigger</b>: {esc(args.event)}\n"
            f"<b>Run</b>: <a href=\"{esc(args.run_url)}\">#{args.run_id}</a>\n"
            f"\n"
            f"{root_block}"
            f"{feat_block}"
            f"<b>Sublevels</b>:\n"
            f"{sub_text}\n"
            f"\n"
            f"<b>Flavors</b>:\n"
            f"{flavors}\n"
            f"\n"
            f"<b>Jobs</b>: {counts}\n"
            f"\n"
            f"<b>Download</b>:\n"
            f"<a href=\"{esc(args.nightly_url)}\">nightly.link — all artifacts</a>"
        )
        if len(msg) > MAX_LEN:
            msg = msg[:MAX_LEN - 1] + "…"
        # Records: CHAT \t TOPIC \t FAMILY \t RICH_MD \t HTML \t BUTTONS_JSON,
        # separated by ASCII RS (\x1e). The caller prefers sendRichMessage on
        # a local Bot API 10.x server (rich tables + styled buttons) and falls
        # back to cloud sendMessage with HTML + reply_markup. It then builds
        # the combined testing-group card from the returned t.me links.
        print(f"{args.chat_id}\t{topic}\t{fname}\t{rich}\t{msg}\t{buttons}", end="\x1e")

    return 0


if __name__ == "__main__":
    sys.exit(main())
