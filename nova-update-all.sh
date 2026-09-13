#!/usr/bin/env bash
set -Eeuo pipefail

# Unified updater for NOVA 11.
# Safe on an existing VPS: keeps awg0 config and does not reinstall Keenetic.
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
REPO_DIR="${REPO_DIR:-/root/awg31-panel}"
cd "$REPO_DIR"

git pull --ff-only origin main
chmod +x install-nova11.sh add-telegram-keenetic-button.sh keenetic-route-updater.sh install-keenetic-route-updater.sh
./install-nova11.sh

# Telegram patch is intentionally isolated from the web-panel runtime.
./add-telegram-keenetic-button.sh || echo 'Telegram patch skipped; web panel is healthy.'

# Never reinstall the dedicated Keenetic bridge during a normal panel update.
if systemctl list-unit-files --type=service 2>/dev/null | grep -q '^keenetic-awg2.service'; then
  systemctl restart keenetic-awg2.service
fi

systemctl is-active --quiet awgpanel
systemctl is-active --quiet awg-quick@awg0

printf '\nNOVA 11 update completed.\n'
printf 'Panel: active.\n'
printf 'Primary awg0: preserved and active.\n'
printf 'Keenetic bridge: not reinstalled automatically.\n'
printf 'Keenetic menu: native NOVA 11.\n'
