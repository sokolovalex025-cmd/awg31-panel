#!/usr/bin/env bash
set -Eeuo pipefail

# Unified updater for NOVA 11 + Telegram runtime.
# Safe on an existing VPS: preserves production awg0 and does not reinstall Keenetic.
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
REPO_DIR="${REPO_DIR:-/root/awg31-panel}"
cd "$REPO_DIR"

[ -d .git ] || { echo "Git repository not found: $REPO_DIR"; exit 1; }
git pull --ff-only origin main
chmod +x install-nova11.sh
./install-nova11.sh

# Existing Keenetic bridge is restarted only if already installed; it is never reinstalled here.
if systemctl list-unit-files --type=service 2>/dev/null | grep -q '^keenetic-awg2.service'; then
  systemctl restart keenetic-awg2.service
fi

systemctl is-active --quiet awgpanel
systemctl is-active --quiet awg-quick@awg0
systemctl is-active --quiet awgpanel-telegram || true

printf '\nNOVA 11 update completed.\n'
printf 'Panel: active.\n'
printf 'Telegram runtime: installed.\n'
printf 'Primary awg0: preserved and active.\n'
printf 'Keenetic bridge: not reinstalled automatically.\n'
printf 'Keenetic menu: native NOVA 11.\n'
