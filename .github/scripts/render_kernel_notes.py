import sys
import json, os, re, time
def env(n,d=""): return os.environ.get(n,d).strip() or d
def parse_managers(raw):
    try: return json.loads(raw) if raw.strip() else []
    except: return []
root = env("ROOT_FLAVOR","All")
if root.startswith("All"): root = "All"
feats=[]
if env("USE_SUSFS","true")=="true": feats.append("SUSFS")
if env("USE_NOMOUNT","true")=="true": feats.append("NoMount")
if env("USE_BBG","true")=="true": feats.append("Baseband Guard")
if env("USE_DS","true")=="true": feats.append("DroidSpaces-OSS")
if env("USE_NET","true")=="true": feats.append("Networking")
if env("USE_NTSYNC","true")=="true": feats.append("NTSync")
if env("USE_PTRACE","true")=="true": feats.append("Ptrace Leak Fix")
if env("USE_UNICODE","true")=="true": feats.append("Unicode Fix")
if env("USE_BPF","true")=="true": feats.append("BTF / eBPF / FUSE-BPF - **disabled**, open an issue if you require it")
if env("USE_USBA","true")=="true": feats.append("USB Arsenal")
if env("USE_PERF","false")=="true": feats.append("Performance Tuning")
if env("PAGE_SIZE","4k")=="16k": feats.append("16 KB page size (ARM64)")
lines=[]
lines.append("# Wild Kernels for GKI2 Devices")
lines.append("")
# 6.18 is the newest LTS GKI branch and the least exercised: its SUSFS support
# is a 6.12->6.18 port rather than an upstream branch, DroidSpaces ships without
# SysV IPC there, and nothing has been verified on a device. Say so in the notes
# whenever a 6.18 build is part of the release, rather than letting an artifact
# that only passed CI read like the long-established families.
_kbv = env("KERNEL_BUILD_VERSION", "All")
if _kbv == "All" or "6.18" in _kbv:
    lines.append("> [!WARNING]")
    lines.append("> **android17-6.18 is experimental and needs testing.** It builds and holds the stock ABI (9,829 symbols compared, 0 differ), but it is the newest GKI branch we ship and the least exercised: SUSFS there is a 6.12 to 6.18 port rather than an upstream branch, DroidSpaces runs without SysV IPC, and no on-device boot, root or SUSFS behaviour has been verified. Back up your boot image before flashing and report what breaks: https://github.com/WildKernels/GKI_KernelSU_SUSFS/issues")
    lines.append("")
lines.append("## Root")
lines.append("")
ksun_branch=env("KSUN_BRANCH","dev-susfs")
ksun_commit=env("KSUN_COMMIT","")
ksu_commit=env("KSU_COMMIT","")
bakasu_commit=env("BAKASU_COMMIT","")
sukisu_ultra_commit=env("SUKISU_ULTRA_COMMIT","")
finasu_commit=env("FINASU_COMMIT","")
kowsu_commit=env("KOWSU_COMMIT","")
kernelsu_commit=env("KERNELSU_COMMIT","")
nm=env("NOMOUNT_COMMIT","")
kp=env("KERNEL_PATCHES_COMMIT","")
ak=env("ANYKERNEL3_COMMIT","")
ds=env("DROIDSPACES_COMMIT","")
usba=env("USBA_COMMIT","")
_rmatrix={}
try: _rmatrix={m.get("root_flavor",""):m.get("root_commit","") for m in json.loads(env("ROOT_MATRIX","[]")) if isinstance(m,dict)}
except: pass
if env("USE_SUSFS","true")=="true":
    _next_url="https://github.com/pershoot/KernelSU-Next/commit/"
else:
    _next_url="https://github.com/KernelSU-Next/KernelSU-Next/commit/"
_root_urls={"next":_next_url,"kernelsu":"https://github.com/tiann/KernelSU/commit/","bakasu":"https://github.com/Baka-SU/BakaSU/commit/","sukisu-ultra":"https://github.com/SukiSU-Ultra/SukiSU-Ultra/commit/","finasu":"https://github.com/LyraVoid/FinaSU/commit/","kowsu":"https://github.com/KOWX712/KernelSU/commit/"}
_root_commits={"next":_rmatrix.get("next","") or kernelsu_commit,"kernelsu":_rmatrix.get("kernelsu","") or ksu_commit,"bakasu":_rmatrix.get("bakasu","") or bakasu_commit,"sukisu-ultra":_rmatrix.get("sukisu-ultra","") or sukisu_ultra_commit,"finasu":_rmatrix.get("finasu","") or finasu_commit,"kowsu":_rmatrix.get("kowsu","") or kowsu_commit}
_flavors0=[m.get("flavor","") for m in parse_managers(env("MANAGER_LIST","")) if m.get("flavor","")]
if not _flavors0:
    _flavors0={"KernelSU-Next":["next"],"KernelSU":["kernelsu"],"BakaSU":["bakasu"],"SukiSU-Ultra":["sukisu-ultra"],"FinaSU":["finasu"],"KowSU":["kowsu"],"No Root":[],"All":["next","kernelsu","bakasu"]}.get(root,["next","kernelsu","bakasu"])
_labels0={"next":"KernelSU-Next","kernelsu":"KernelSU","bakasu":"BakaSU","sukisu-ultra":"SukiSU-Ultra","finasu":"FinaSU","kowsu":"KowSU"}
# Manager version numbers. tiann/KernelSU and its descendants (KernelSU-Next,
# BakaSU) do not store a version string: the manager computes
#   version = 30000 + <commits in the repo>
# and shows that number in the app, so the notes derive it the same way to match
# what a user sees on the device.
#
# GitHub exposes no commit *count*, but the commits endpoint paginates and the
# Link header's rel="last" page number is the commit count when per_page=1.
#
# KernelSU-Next is counted on the official repo's dev branch: our kernel runs a
# fork (pershoot dev-susfs) whose own history carries extra commits, and the
# manager number is anchored to the point the fork syncs from - the same
# merge-base the release job uses. Forks whose formula is not this one (SukiSU,
# FinaSU, KowSU) are left commit-only rather than showing a number we cannot
# stand behind.
_mgr_ver_cache = {}
def manager_version(flavour, sha):
    if flavour in _mgr_ver_cache:
        return _mgr_ver_cache[flavour]
    repo, ref = {
        "next":          ("KernelSU-Next/KernelSU-Next", "dev"),
        "kernelsu":      ("tiann/KernelSU", sha or "main"),
        "bakasu":        ("Baka-SU/BakaSU", sha or "main"),
    }.get(flavour, ("", ""))
    ver = ""
    if repo and ref:
        import urllib.request, urllib.error
        url = "https://api.github.com/repos/%s/commits?sha=%s&per_page=1" % (repo, ref)
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        if not token:
            sys.stderr.write(
                "warning: GITHUB_TOKEN is not set; the version probe is "
                "unauthenticated and may be rate limited\n")
        for _ in range(2):
            try:
                req = urllib.request.Request(url, method="HEAD")
                req.add_header("Accept", "application/vnd.github+json")
                if token:
                    req.add_header("Authorization", "Bearer %s" % token)
                resp = urllib.request.urlopen(req, timeout=25)
                link = resp.headers.get("Link", "") or ""
                m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
                count = int(m.group(1)) if m else 1
                ver = str(30000 + count)
                break
            except Exception as exc:
                # Never fall back silently: an empty version is indistinguishable
                # from a rate-limited probe, which is exactly how every manager
                # lost its number in run 43959326934.
                code = getattr(exc, "code", "")
                sys.stderr.write(
                    "warning: %s version probe failed (%s%s); showing a dash\n"
                    % (flavour, type(exc).__name__, " %s" % code if code else ""))
                break
    _mgr_ver_cache[flavour] = ver
    return ver

_rc=[]
for _fl0 in _flavors0:
    _c=_root_commits.get(_fl0,"")
    _v=manager_version(_fl0,_c)
    if _c and len(_c)==40: _commit=f"[`{_c[:7]}`]({_root_urls[_fl0]}{_c})"
    elif _c: _commit=f"`{_c}`"
    else: _commit="_n/a_"
    # Deliberately NOT _n/a_: that string is the release job's sentinel for an
    # unresolved workflow output, so reusing it here made a missing version look
    # like a broken pipeline and failed the release (#43959326934).
    _vcell = _v if _v else "\u2014"
    _rc.append("| %s | %s | %s |" % (_labels0.get(_fl0,_fl0), _vcell, _commit))
if _rc:
    lines.append("| Root | Version | Commit |")
    lines.append("|---|---|---|")
    lines.extend(_rc)
lines.append("")
lines.append("## Features")
lines.append("")
_kp_url="https://github.com/WildKernels/kernel_patches/commit/"
_feat_commit={"NoMount":("https://github.com/maxsteeel/nomount/commit/",nm),"Baseband Guard":(_kp_url,kp),"DroidSpaces-OSS":("https://github.com/ravindu644/Droidspaces-OSS/commit/",ds),"USB Arsenal":("https://github.com/ravindu644/USB-Arsenal/commit/",usba)}
for f in feats:
    _u,_c=_feat_commit.get(f,("",""))
    if _c and len(_c)==40: lines.append(f"- {f} [`{_c[:7]}`]({_u}{_c})")
    elif _c: lines.append(f"- {f} `{_c}`")
    else: lines.append(f"- {f}")
if not feats: lines.append("- (none)")
kp=env("KERNEL_PATCHES_COMMIT","")
ak=env("ANYKERNEL3_COMMIT","")
ds=env("DROIDSPACES_COMMIT","")
lines.append("")
lines.append("## SUSFS commits")
lines.append("")
all_variants=["android12-5.10","android13-5.10","android13-5.15","android14-5.15","android14-6.1","android15-6.6","android16-6.12"]
def kbv_to_variant(kbv):
    if ".x-android" in kbv:
        kv, av = kbv.split(".x-android", 1)
        v = f"android{av}-{kv}"
        return v if v in all_variants else ""
    return ""
kbv=env("KERNEL_BUILD_VERSION","All")
_sel=kbv_to_variant(kbv)
variants=[_sel] if _sel else list(all_variants)
sus_map={"android12-5.10":env("SUSFS_ANDROID12_5_10",""),"android13-5.10":env("SUSFS_ANDROID13_5_10",""),"android13-5.15":env("SUSFS_ANDROID13_5_15",""),"android14-5.15":env("SUSFS_ANDROID14_5_15",""),"android14-6.1":env("SUSFS_ANDROID14_6_1",""),"android15-6.6":env("SUSFS_ANDROID15_6_6",""),"android16-6.12":env("SUSFS_ANDROID16_6_12","")}
sus_map_bakasu={"android12-5.10":env("SUSFS_ANDROID12_5_10_BAKASU",""),"android13-5.10":env("SUSFS_ANDROID13_5_10_BAKASU",""),"android13-5.15":env("SUSFS_ANDROID13_5_15_BAKASU",""),"android14-5.15":env("SUSFS_ANDROID14_5_15_BAKASU",""),"android14-6.1":env("SUSFS_ANDROID14_6_1_BAKASU",""),"android15-6.6":env("SUSFS_ANDROID15_6_6_BAKASU",""),"android16-6.12":env("SUSFS_ANDROID16_6_12_BAKASU","")}
sus_map_sukisu_ultra={"android12-5.10":env("SUSFS_ANDROID12_5_10_SUKISU_ULTRA",""),"android13-5.10":env("SUSFS_ANDROID13_5_10_SUKISU_ULTRA",""),"android13-5.15":env("SUSFS_ANDROID13_5_15_SUKISU_ULTRA",""),"android14-5.15":env("SUSFS_ANDROID14_5_15_SUKISU_ULTRA",""),"android14-6.1":env("SUSFS_ANDROID14_6_1_SUKISU_ULTRA",""),"android15-6.6":env("SUSFS_ANDROID15_6_6_SUKISU_ULTRA",""),"android16-6.12":env("SUSFS_ANDROID16_6_12_SUKISU_ULTRA","")}
_flavors=[m.get("flavor","") for m in parse_managers(env("MANAGER_LIST","")) if m.get("flavor","")]
if not _flavors:
    _flavors={"KernelSU-Next":["next"],"KernelSU":["kernelsu"],"BakaSU":["bakasu"],"SukiSU-Ultra":["sukisu-ultra"],"KowSU":["kowsu"],"No Root":[],"All":["next","kernelsu","bakasu"]}.get(root,["next","kernelsu","bakasu"])
_labels={"next":"KernelSU-Next","kernelsu":"KernelSU","bakasu":"BakaSU","sukisu-ultra":"SukiSU-Ultra","kowsu":"KowSU"}
_susfs_url="https://gitlab.com/simonpunk/susfs4ksu"
# SUSFS owns its own version string: kernel_patches/include/linux/susfs.h carries
#   #define SUSFS_VERSION "v2.4.0"
# and upstream bumps it when the feature set moves. Reading it at the resolved SHA
# means the notes quote the version actually built instead of a value someone has
# to remember to update. Cached per SHA (the three pin sets usually agree), and a
# failed fetch degrades to commit-only rather than breaking the notes.
_susfs_ver_cache = {}
def susfs_version_of(sha):
    if not sha:
        return ""
    if sha in _susfs_ver_cache:
        return _susfs_ver_cache[sha]
    ver = ""
    raw = "https://gitlab.com/simonpunk/susfs4ksu/-/raw/%s/kernel_patches/include/linux/susfs.h" % sha
    for attempt in range(3):
        try:
            import urllib.request
            req = urllib.request.Request(raw, headers={"User-Agent": "WildKernels-CI/1.0"})
            body = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
            m = re.search(r'#define\s+SUSFS_VERSION\s+"([^"]+)"', body)
            if m:
                ver = m.group(1)
                break
        except Exception:
            pass
        time.sleep(3)
    _susfs_ver_cache[sha] = ver
    return ver

lines.append("| SUSFS branch |" + "".join(f" {_labels.get(_fl,_fl)} |" for _fl in _flavors))
lines.append("|---" * (len(_flavors) + 1) + "|")
for v in variants:
    _row=f"| gki-{v} |"
    for _fl in _flavors:
        # KowSU never ships SUSFS: render n/a rather than shared pins.
        _sm={} if _fl=="kowsu" else (sus_map_sukisu_ultra if _fl=="sukisu-ultra" else (sus_map_bakasu if _fl=="bakasu" else sus_map))
        sha=_sm.get(v,"")
        if sha:
            _ver=susfs_version_of(sha)
            sha_s=f"[`{sha[:7]}`]({_susfs_url}/-/commit/{sha})"
            # "v2.4.0 (abc1234)" - version first, commit in brackets
            if _ver: sha_s=f"{_ver} ({sha_s})"
        else:
            sha_s="_n/a_"
        _row+=f" {sha_s} |"
    lines.append(_row)
lines.append("")
lines.append("")
# --- build availability -----------------------------------------------------
# Config rows carry "disabled": true when the same kernel version is also built
# from another month (temporary trim). Say so in the notes so a missing month
# does not look like a failed build, and give people a way to ask for it back.
_disabled={}
try:
    import glob as _glob
    _root=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for _p in sorted(_glob.glob(os.path.join(_root,".github","config","*.json")) or _glob.glob(".github/config/*.json")):
        try: _cfg=json.load(open(_p))
        except Exception: continue
        _rows=sorted(e.get("date","") for e in _cfg.get("include",[]) if e.get("disabled") is True)
        if _rows: _disabled[_cfg.get("version","")]=_rows
except Exception:
    _disabled={}
lines.append("## Build availability")
lines.append("")
if _disabled:
    _total=sum(len(v) for v in _disabled.values())
    lines.append(f"**{_total} matrix rows are currently switched off.** Each of them duplicates a kernel version that is also built from another month, so the version ships once — from the newest month whose upstream branch still exists — instead of once per month:")
    lines.append("")
    for _fam in sorted(_disabled):
        lines.append(f"- `{_fam}`: {', '.join(_disabled[_fam])}")
    lines.append("")
    lines.append("The list lives in `.github/config/*.json` as `\"disabled\": true`, so it is easy to restore. **If you need one of these month snapshots, open an issue and it will be re-enabled:** https://github.com/WildKernels/GKI_KernelSU_SUSFS/issues")
else:
    lines.append("Every configured matrix row is built in this release.")
lines.append("")
output="\n".join(lines)+"\n"
print(output,end="")
# The rendered body is also the run summary: it is what a reviewer reads on
# the run page. Artifacts carry it too, but the summary is deliberate here.
s=os.environ.get("GITHUB_STEP_SUMMARY")
if s: open(s,"a").write(output)
