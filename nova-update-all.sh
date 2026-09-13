#!/usr/bin/env bash
set -Eeuo pipefail

# One-command NOVA update for an existing /root/awg31-panel checkout.
# Preserves the user's local Telegram installer change and never reinstalls
# the Keenetic bridge automatically.

[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
REPO_DIR="${REPO_DIR:-/root/awg31-panel}"
cd "$REPO_DIR"

if [ ! -d .git ]; then
  echo "Git repository not found: $REPO_DIR"
  exit 1
fi

STASHED=0
if ! git diff --quiet -- install-telegram-full-v2.sh; then
  git stash push -m "nova-update-preserve-telegram" -- install-telegram-full-v2.sh >/dev/null
  STASHED=1
fi

restore_stash() {
  if [ "$STASHED" -eq 1 ]; then
    git stash pop || true
  fi
}
trap restore_stash EXIT

git pull --ff-only origin main
chmod +x upgrade-panel9.sh keenetic-awg2.sh nova-update-all.sh
./upgrade-panel9.sh

# Restart only the dedicated Keenetic bridge if it already exists.
# Do not run keenetic-awg2.sh here: reinstalling it is intentionally manual.
if systemctl list-unit-files --type=service 2>/dev/null | grep -q '^keenetic-awg2.service'; then
  systemctl restart keenetic-awg2.service
fi

systemctl is-active --quiet awg-quick@awg0
systemctl is-active --quiet awgpanel

printf '\nNOVA update completed.\n'
printf 'Primary awg0: preserved and active.\n'
printf 'Panel: active.\n'
if systemctl list-unit-files --type=service 2>/dev/null | grep -q '^keenetic-awg2.service'; then
  printf 'Keenetic bridge: active.\n'
else
  printf 'Keenetic bridge: not installed (manual install available via ./keenetic-awg2.sh).\n'
fi
printf 'Telegram local changes: preserved if they existed before update.\n'
