#!/usr/bin/env bash
set -Eeuo pipefail

# Install the external AWG Toolza CLI without replacing NOVA's AWG configuration.
# Pinned upstream commit: pumbaX/awg-multi-script @ ecccafa3094181a6962ff71e54527e4771657698
TOOLZA_URL="https://raw.githubusercontent.com/pumbaX/awg-multi-script/ecccafa3094181a6962ff71e54527e4771657698/awg2.sh"
DEST="/usr/local/bin/awg2"

[[ "$(id -u)" -eq 0 ]] || { echo "Run as root."; exit 1; }

if [[ -e "$DEST" && "${FORCE:-0}" != "1" ]]; then
  echo "AWG Toolza is already installed at $DEST."
  echo "To replace it with the pinned version: FORCE=1 bash $0"
  exit 0
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
curl -fsSL --retry 3 --connect-timeout 8 --max-time 60 "$TOOLZA_URL" -o "$tmp"
head -n 1 "$tmp" | grep -q '^#!/bin/bash' || { echo "Downloaded file is not awg2.sh."; exit 1; }
bash -n "$tmp"
install -m 755 "$tmp" "$DEST"

echo "AWG Toolza installed: $DEST"
echo "Pinned upstream commit: ecccafa3094181a6962ff71e54527e4771657698"
echo "NOVA awg0.conf was not modified."
echo "Run: sudo awg2"
