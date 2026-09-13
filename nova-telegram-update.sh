#!/usr/bin/env bash
set -euo pipefail

BASE=/opt/awg31-panel
REPO=https://github.com/sokolovalex025-cmd/awg31-panel.git
BACKUP="$BASE/backups/telegram-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"

log(){ printf '[NOVA-TG] %s\n' "$*"; }

log 'Creating Telegram safety backup'
for f in panel.db; do
  [ -f "$BASE/$f" ] && cp -a "$BASE/$f" "$BACKUP/$f"
done
[ -f /etc/awg31-panel/telegram.env ] && cp -a /etc/awg31-panel/telegram.env "$BACKUP/telegram.env"
chmod 600 "$BACKUP"/* 2>/dev/null || true

log 'Updating Telegram components from main'
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git clone --depth 1 "$REPO" "$tmp/repo" >/dev/null 2>&1

for f in telegram_bot.py telegram_runner.py telegram_delete.py telegram_ui.py nova-migrate.sh; do
  [ -f "$tmp/repo/$f" ] && install -m 644 "$tmp/repo/$f" "$BASE/$f"
done
chmod 700 "$BASE/nova-migrate.sh" 2>/dev/null || true

log 'Checking Python syntax'
python3 -m py_compile "$BASE/telegram_bot.py" "$BASE/telegram_runner.py" "$BASE/telegram_delete.py" "$BASE/telegram_ui.py"

log 'Checking Telegram environment'
if [ -f /etc/awg31-panel/telegram.env ]; then
  chmod 600 /etc/awg31-panel/telegram.env
  grep -q '^TELEGRAM_BOT_TOKEN=' /etc/awg31-panel/telegram.env || { echo '[FAIL] TELEGRAM_BOT_TOKEN missing'; exit 1; }
else
  echo '[WARN] /etc/awg31-panel/telegram.env not found; configure the bot in the panel first.'
fi

log 'Restarting Telegram service'
systemctl daemon-reload
systemctl enable awgpanel-telegram.service >/dev/null 2>&1 || true
systemctl restart awgpanel-telegram.service
sleep 2

if systemctl is-active --quiet awgpanel-telegram.service; then
  log 'Telegram service: OK'
else
  echo '[FAIL] Telegram service is not active'
  systemctl --no-pager -l status awgpanel-telegram.service || true
  exit 1
fi

log 'Checking migration helper'
[ -x "$BASE/nova-migrate.sh" ] || { chmod 700 "$BASE/nova-migrate.sh"; }
[ -x "$BASE/nova-migrate.sh" ] && log 'Migration helper: OK'

log 'Done. AWG0 configuration was not changed.'
echo "Backup: $BACKUP"
