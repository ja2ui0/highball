#!/usr/bin/env bash
set -euo pipefail
FILES=("Dockerfile.base" "requirements.txt")
STAMP=".base.hash"

curr="$(cat "${FILES[@]}" 2>/dev/null | sha256sum | awk '{print $1}')"
prev="$(cat "$STAMP" 2>/dev/null || true)"

if [[ "$curr" != "$prev" ]]; then
  echo "[base] Changes detected → rebuilding backup-manager-base:latest ..."
  docker build -f Dockerfile.base -t backup-manager-base:latest .
  echo "$curr" > "$STAMP"
else
  echo "[base] No changes in Dockerfile.base/requirements.txt → skipping base build."
fi

