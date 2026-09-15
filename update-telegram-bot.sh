#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/opt/awg31-panel
SERVICE=awgpanel-telegram.service
BOT="$BASE/telegram_bot.py"\V2="$BASE/telegram_bot_v2.py"\ENV=/etc/awg31-panel/telegram.env
DROPIN="/etc/systemd/system/${SERVICE}.d/override.conf"
REPO_RAW="https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/telegram-v2"

[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
mkdir -p "$BASE" "$(dirname "$DROPIN")"

stamp=$(date +%Y%m%d-%H%M%S)
backup="$BASE/telegram-backup-$stamp"
mkdir -p "$backup"
[ -f "$BOT" ] && cp -a "$BOT" "$backup/telegram_bot.py"
[ -f "$V2" ] && cp -a "$V2" "$backup/telegram_bot_v2.py"

echo '[1/6] Downloading enhanced bot...'
curl -fsSL --retry 3 "$REPO_RAW/telegram_bot_v2.py" -o "$V2.new"
python3 -m py_compile "$V2.new"
mv "$V2.new" "$V2"
chmod 750 "$V2"

echo '[2/6] Preparing configuration...'
mkdir -p /etc/awg31-panel
if [ ! -f "$ENV" ]; then
  cat > "$ENV" <<'EOF'
# NOVA Telegram Bot configuration
# TELEGRAM_BOT_TOKEN=...
# TELEGRAM_ADMIN_IDS=123456789
# TELEGRAM_ALLOWED_IDS=123456789
# VPN_DEFAULT_DAYS=30
# NOVA_ROUTES_URL=https://example.invalid/routes.txt
# NOVA_ROUTES_FILE=/opt/awg31-panel/nova-routes.txt
# NOVA_ROUTES_INTERVAL=900
EOF
  chmod 600 "$ENV"
fi

# Never overwrite an existing secret/configuration.
chmod 600 "$ENV"

# If the installed feed can be identified from existing environment, keep it.
# Otherwise the bot will stay safe and report that NOVA_ROUTES_URL/FILE is not configured.

echo '[3/6] Installing systemd override...'
cat > "$DROPIN" <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/python3 $V2
Restart=always
RestartSec=3
EOF

systemctl daemon-reload

echo '[4/6] Checking Python files...'
python3 -m py_compile "$V2"
python3 -m py_compile "$BOT"

echo '[5/6] Restarting bot...'
systemctl enable "$SERVICE" >/dev/null 2>&1 || true
systemctl restart "$SERVICE"
sleep 2

echo '[6/6] Result:'
echo "Backup: $backup"
echo "Service: $(systemctl is-active "$SERVICE" || true)"
systemctl --no-pager --full status "$SERVICE" | sed -n '1,18p' || true

echo
echo 'Commands:'
echo '  /admin        — admin menu'
echo '  /status       — VPS/AWG/bot status'
echo '  /routes       — NOVA feed status'
echo '  /routes_check — force feed check'
echo
echo 'NOVA feed configuration:'
grep -E '^(NOVA_ROUTES_URL|NOVA_ROUTES_FILE|NOVA_ROUTES_INTERVAL)=' "$ENV" 2>/dev/null || true

echo
echo 'Update completed.'
