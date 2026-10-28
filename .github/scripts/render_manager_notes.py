import json, os
def env(k, d=""):
    return os.environ.get(k, d).strip()
root = env("ROOT_FLAVOR", "All")
src = env("BUILD_FROM_SOURCE", "false") == "true"
commits = {
    "KernelSU-Next": env("NEXT_COMMIT") or "latest dev tip",
    "KernelSU": env("KSU_COMMIT") or "latest main tip",
    "BakaSU": env("BAKASU_COMMIT") or "latest tip",
    "SukiSU-Ultra": env("SUKISU_ULTRA_COMMIT") or "latest tip",
    "FinaSU": env("FINASU_COMMIT") or "latest tip",
    "KowSU": "latest tip",
    "KernelSU-Next-SUSFS": env("NEXT_SUSFS_COMMIT") or "latest dev-susfs tip",
}
# enrich from fetch path manager_list (pure commit info, same style as prebuilt)
raw = env("MANAGER_LIST_FETCH")
if raw:
    try:
        for m in json.loads(raw):
            label = {"next":"KernelSU-Next","kernelsu":"KernelSU","bakasu":"BakaSU","sukisu-ultra":"SukiSU-Ultra","finasu":"FinaSU","kowsu":"KowSU","next-susfs":"KernelSU-Next-SUSFS"}.get(m.get("flavor",""), "")
            if label and m.get("stock"):
                commits[label] = m["stock"]
    except: pass
lines = []
lines.append("# Managers — Release Notes Preview")
lines.append("")
lines.append("## Features")
lines.append("")
if root == "All":
    lines.append("- All manager flavors (KernelSU-Next, KernelSU, BakaSU, SukiSU-Ultra, FinaSU, KernelSU-Next-SUSFS)")
else:
    lines.append(f"- {root}")
lines.append(f"- {'Built from source' if src else 'Fetched prebuilt (upstream CI)'}")
lines.append("")
lines.append("## Commits")
lines.append("")
for k, v in commits.items():
    if len(v) == 40:
        lines.append(f"- **{k}:** `{v[:12]}` `{v}`")
    else:
        lines.append(f"- **{k}:** `{v}`")
output = "\n".join(lines) + "\n"
print(output, end="")
s = os.environ.get("GITHUB_STEP_SUMMARY")
if s:
    open(s, "a").write(output)
