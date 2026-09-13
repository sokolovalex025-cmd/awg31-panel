#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/opt/awg31-panel
OUT=${1:-/root/nova-max-backups}
TS=$(date +%Y%m%d-%H%M%S)
DEST="$OUT/nova-max-$TS"
mkdir -p "$DEST"
chmod 700 "$DEST"
for f in panel.db app.py nova11.py panel_bootstrap.py nova12_theme.py nova13_theme.py nova14_theme.py antiblock.py nova_shield.py nova_resilience.py domain_manager.py keenetic.py balancer.py balancer_provision.py nova_mobile_diagnostics.py telegram_ui.py telegram_bot.py telegram_runner.py telegram_delete.py background.svg; do
  [ -f "$BASE/$f" ] && install -m 600 "$BASE/$f" "$DEST/$f"
done
for pair in "/etc/awg31-panel/panel-secret panel-secret" "/etc/nginx/sites-available/awg31-panel nginx-awg31-panel"; do
  set -- $pair; [ -f "$1" ] && install -m 600 "$1" "$DEST/$2"
done
if command -v awg >/dev/null 2>&1; then awg showconf awg0 2>/dev/null | sed -E 's/^PrivateKey = .*/PrivateKey = [REDACTED]/; s/^PresharedKey = .*/PresharedKey = [REDACTED]/' > "$DEST/awg0-public-state.txt" || true; fi
systemctl status awgpanel --no-pager > "$DEST/awgpanel-status.txt" 2>&1 || true
systemctl status awg31-network --no-pager > "$DEST/network-status.txt" 2>&1 || true
sha256sum "$DEST"/* > "$DEST/SHA256SUMS" 2>/dev/null || true
printf '%s\n' "$DEST"
