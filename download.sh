#!/usr/bin/env bash
set -euo pipefail

# ===== CONFIG =====
REPO="WildKernels/GKI_KernelSU_SUSFS"
RUN_ID="20671082108"
PATTERN="(Normal|Bypass)-AnyKernel3$"
OUT_DIR="$HOME/gki_anykernel3"
# ==================

mkdir -p "$OUT_DIR"

echo "Fetching AnyKernel3 artifacts from run $RUN_ID..."

gh api \
  repos/$REPO/actions/runs/$RUN_ID/artifacts \
  --paginate |
jq -r --arg pattern "$PATTERN" '
  .artifacts[]
  | select(.name | test($pattern))
  | "\(.id) \(.name)"
' |
while read -r ID NAME; do
  FILE="$OUT_DIR/$NAME.zip"
  echo "Downloading: $NAME"
  gh api \
    repos/$REPO/actions/artifacts/$ID/zip \
    > "$FILE"
done

echo "Done. Files saved to: $OUT_DIR"
