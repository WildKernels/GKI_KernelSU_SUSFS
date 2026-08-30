#!/usr/bin/env python3
"""Generate org-wide deduped contributors grid for WildKernels.

Fetches all repos in the org via GitHub API, then contributors per repo,
dedupes by login, aggregates contributions, and writes an HTML avatar wall
between markers in README.md:

  <!-- ORG_CONTRIBUTORS_START --> ... <!-- ORG_CONTRIBUTORS_END -->

Requires GITHUB_TOKEN env (uses default Actions token for public org data).
No external deps - uses urllib + stdlib only.
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

ORG = os.environ.get("ORG", "WildKernels")
README = os.environ.get("README_PATH", "README.md")
TOKEN = os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", "")

START = "<!-- ORG_CONTRIBUTORS_START -->"
END = "<!-- ORG_CONTRIBUTORS_END -->"

API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "wildkernels-org-contributors",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

def api_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 204:
                    return [], resp.headers
                body = resp.read().decode().strip()
                if not body:
                    return [], resp.headers
                data = json.loads(body)
                # honor rate limit
                remaining = resp.headers.get("X-RateLimit-Remaining")
                if remaining and int(remaining) < 10:
                    reset = int(resp.headers.get("X-RateLimit-Reset", "0"))
                    wait = max(0, reset - int(time.time())) + 2
                    print(f"  rate limit low ({remaining}), waiting {wait}s", file=sys.stderr)
                    time.sleep(min(wait, 60))
                return data, resp.headers
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < 2:
                retry = e.headers.get("Retry-After")
                wait = int(retry) if retry and retry.isdigit() else 2 ** attempt * 5
                print(f"  HTTP {e.code} on {url}, retry {attempt+1} in {wait}s: {e.read().decode()[:200]}", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"failed GET {url}")

def list_org_repos(org):
    repos = []
    page = 1
    # Exclude huge upstream forks that drown org stats (Magisk is topjohnwu upstream)
    EXCLUDE = {"Magisk"}
    while True:
        url = f"{API}/orgs/{org}/repos?per_page=100&page={page}&type=public&sort=updated"
        data, _ = api_get(url)
        if not data:
            break
        for r in data:
            if r.get("archived"):
                continue
            name = r["name"]
            if name in EXCLUDE:
                continue
            repos.append(name)
        if len(data) < 100:
            break
        page += 1
    return repos

def list_contributors(org, repo):
    contribs = []
    page = 1
    while True:
        url = f"{API}/repos/{org}/{repo}/contributors?per_page=100&page={page}&anon=false"
        try:
            data, _ = api_get(url)
        except urllib.error.HTTPError as e:
            if e.code == 204 or e.code == 404:
                return []
            # empty repos / no contributors
            body = e.read().decode() if hasattr(e, 'read') else str(e)
            print(f"  warn {org}/{repo} contributors: HTTP {e.code} {body[:200]}", file=sys.stderr)
            return []
        if not data or not isinstance(data, list):
            break
        for u in data:
            if u.get("type") == "Bot":
                continue
            login = u.get("login")
            if not login or login.endswith("[bot]"):
                continue
            contribs.append({
                "login": login,
                "avatar_url": u.get("avatar_url", f"https://github.com/{login}.png"),
                "html_url": u.get("html_url", f"https://github.com/{login}"),
                "contributions": int(u.get("contributions", 0)),
            })
        if len(data) < 100:
            break
        page += 1
        time.sleep(0.2)
    return contribs

def build_grid(contributors):
    # sort by total contributions desc, then login
    contributors.sort(key=lambda x: (-x["total"], x["login"].lower()))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = []
    lines.append('<p align="center">')
    for c in contributors:
        login = c["login"]
        # use github.com/{login}.png for stable size param
        img = f"https://github.com/{login}.png?size=80"
        lines.append(f'  <a href="https://github.com/{login}" title="{login} ({c["total"]} contributions across org)">')
        lines.append(f'    <img src="{img}" width="50" height="50" alt="{login}" style="border-radius:50%;" />')
        lines.append(f'  </a>')
    lines.append('</p>')
    lines.append(f'<p align="center"><sub>Total contributors: <b>{len(contributors)}</b> across WildKernels org &middot; updated {now}</sub></p>')
    # fallback text list for no-js / SEO
    logins = ", ".join(f"@{c['login']}" for c in contributors[:50])
    if logins:
        lines.append(f'<p align="center"><sub>{logins}{" &hellip;" if len(contributors) > 50 else ""}</sub></p>')
    return "\n".join(lines)

def main():
    print(f"Org: {ORG}", file=sys.stderr)
    repos = list_org_repos(ORG)
    print(f"Found {len(repos)} repos: {', '.join(repos[:20])}{' ...' if len(repos)>20 else ''}", file=sys.stderr)
    if not repos:
        print("No repos found, aborting", file=sys.stderr)
        return 1

    merged = {}  # login -> {login, avatar_url, html_url, total, repos: set}
    for repo in repos:
        print(f"Fetching contributors for {ORG}/{repo} ...", file=sys.stderr)
        contribs = list_contributors(ORG, repo)
        print(f"  {len(contribs)} contributors", file=sys.stderr)
        for c in contribs:
            login = c["login"]
            if login not in merged:
                merged[login] = {"login": login, "avatar_url": c["avatar_url"], "html_url": c["html_url"], "total": 0, "repos": set()}
            merged[login]["total"] += c["contributions"]
            merged[login]["repos"].add(repo)
        time.sleep(0.3)

    contributors = list(merged.values())
    print(f"Merged {len(contributors)} unique contributors org-wide", file=sys.stderr)

    grid = build_grid(contributors)

    # update README
    if not os.path.exists(README):
        print(f"README not found at {README}", file=sys.stderr)
        return 1
    with open(README, "r", encoding="utf-8") as f:
        text = f.read()

    if START not in text or END not in text:
        print(f"Markers {START} / {END} not found in {README} - inserting after Special Thanks heading", file=sys.stderr)
        # insert after ## Special Thanks block
        insert = f"\n{START}\n{grid}\n{END}\n"
        # find Special Thanks heading
        m = re.search(r"(## Special Thanks[^\n]*\n)", text)
        if m:
            pos = m.end()
            # find end of the intro line after heading
            m2 = re.search(r"\*\*These amazing[^\n]*\n", text[pos:])
            if m2:
                pos = pos + m2.end()
            text = text[:pos] + insert + text[pos:]
        else:
            text = text + "\n" + insert
    else:
        pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
        replacement = f"{START}\n{grid}\n{END}"
        text, n = pattern.subn(replacement, text, count=1)
        print(f"Replaced {n} marker block(s)", file=sys.stderr)

    with open(README, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Wrote {README}", file=sys.stderr)
    return 0

if __name__ == "__main__":
    sys.exit(main())
