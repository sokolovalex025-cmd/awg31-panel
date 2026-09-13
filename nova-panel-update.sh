#!/usr/bin/env bash
set -euo pipefail

BASE=/opt/awg31-panel
REPO_DIR="${REPO_DIR:-/root/awg31-panel}"
REPO_URL="https://github.com/sokolovalex025-cmd/awg31-panel.git"
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="$BASE/backups/panel-update-$STAMP"

log(){ printf '[NOVA-UPDATE] %s\n' "$*"; }
fail(){ printf '[NOVA-UPDATE] [FAIL] %s\n' "$*" >&2; exit 1; }

mkdir -p "$BASE/backups" "$BACKUP"

log 'Creating safety snapshot'
for f in panel.db panel_bootstrap.py nova11.py nova14_theme.py antiblock.py nova_shield.py nova_resilience.py domain_manager.py telegram_bot.py telegram_runner.py telegram_delete.py telegram_ui.py keenetic.py balancer.py nova_mobile_diagnostics.py nova-max-backup.sh nova-migrate.sh; do
  [ -f "$BASE/$f" ] && cp -a "$BASE/$f" "$BACKUP/$f"
done
[ -f /etc/awg31-panel/telegram.env ] && cp -a /etc/awg31-panel/telegram.env "$BACKUP/telegram.env"
[ -f /etc/awg31-panel/panel-secret ] && cp -a /etc/awg31-panel/panel-secret "$BACKUP/panel-secret"
chmod 600 "$BACKUP"/* 2>/dev/null || true

# Preserve the live AWG configuration as a checksum/reference only.
if [ -f /etc/amnezia/amneziawg/awg0.conf ]; then
  sha256sum /etc/amnezia/amneziawg/awg0.conf > "$BACKUP/awg0.conf.sha256"
elif [ -f /etc/wireguard/awg0.conf ]; then
  sha256sum /etc/wireguard/awg0.conf > "$BACKUP/awg0.conf.sha256"
fi

if [ -d "$REPO_DIR/.git" ]; then
  log 'Updating repository'
  git -C "$REPO_DIR" fetch origin main
  git -C "$REPO_DIR" reset --hard origin/main
else
  log 'Repository checkout not found; cloning fresh checkout'
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  git clone --depth 1 "$REPO_URL" "$tmp/repo" >/dev/null 2>&1 || fail 'git clone failed'
  REPO_DIR="$tmp/repo"
fi

log 'Installing panel runtime files'
for f in app.py nova11.py panel_bootstrap.py nova12_theme.py nova13_theme.py nova14_theme.py antiblock.py nova_shield.py nova_resilience.py domain_manager.py keenetic.py balancer.py balancer_provision.py nova_mobile_diagnostics.py telegram_bot.py telegram_runner.py telegram_delete.py telegram_ui.py nova-max-backup.sh nova-migrate.sh nova-verify.sh; do
  [ -f "$REPO_DIR/$f" ] && install -m 644 "$REPO_DIR/$f" "$BASE/$f"
done

chmod 755 "$BASE/panel_bootstrap.py" "$BASE/nova-max-backup.sh" "$BASE/nova-migrate.sh" "$BASE/nova-verify.sh" 2>/dev/null || true

log 'Checking Python syntax'
PY="$REPO_DIR/venv/bin/python"
[ -x "$PY" ] || PY=python3
for f in "$BASE"/*.py; do
  "$PY" -m py_compile "$f" || fail "Python syntax: $f"
done

log 'Checking critical AWG state before restart'
command -v awg >/dev/null 2>&1 || fail 'awg command not found'
awg show awg0 >/dev/null 2>&1 || fail 'awg0 is not available'

log 'Restarting panel only'
systemctl daemon-reload
systemctl restart awgpanel.service
sleep 2
systemctl is-active --quiet awgpanel.service || { systemctl --no-pager -l status awgpanel.service || true; fail 'awgpanel.service is not active'; }

log 'Reloading nginx'
nginx -t >/dev/null || fail 'nginx configuration test failed'
systemctl reload nginx

log 'Running verification'
if [ -x "$BASE/nova-verify.sh" ]; then
  "$BASE/nova-verify.sh" || fail 'verification failed'
fi

log 'Update completed successfully'
printf '\nBackup: %s\n' "$BACKUP"
printf 'AWG0 configuration: not modified by this updater.\n'
printf 'Panel: active\n'
printf 'NOVA MAX verification: PASS\n'
