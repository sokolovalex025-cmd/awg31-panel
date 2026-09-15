#!/usr/bin/env bash
set -Eeuo pipefail
BASE=/opt/awg31-panel
SERVICE=awgpanel-telegram.service
BOT="$BASE/telegram_bot.py"
V2="$BASE/telegram_bot_v2.py"
WELCOME="$BASE/telegram_welcome.py"
ENV=/etc/awg31-panel/telegram.env
DROPIN="/etc/systemd/system/${SERVICE}.d/override.conf"
REPO_RAW="https://raw.githubusercontent.com/sokolovalex025-cmd/awg31-panel/telegram-v2"

[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
mkdir -p "$BASE" "$(dirname "$DROPIN")" /etc/awg31-panel
stamp=$(date +%Y%m%d-%H%M%S)
backup="$BASE/telegram-backup-$stamp"
mkdir -p "$backup"
[ -f "$BOT" ] && cp -a "$BOT" "$backup/telegram_bot.py"
[ -f "$V2" ] && cp -a "$V2" "$backup/telegram_bot_v2.py"
[ -f "$WELCOME" ] && cp -a "$WELCOME" "$backup/telegram_welcome.py"
[ -f "$ENV" ] && cp -a "$ENV" "$backup/telegram.env"

PYTHON=/root/awg31-panel/venv/bin/python
if [ ! -x "$PYTHON" ]; then PYTHON=/usr/bin/python3; fi

echo '[1/7] Checking Python dependencies...'
if ! "$PYTHON" -c 'import flask' >/dev/null 2>&1; then
  if [[ "$PYTHON" == /root/awg31-panel/venv/bin/python ]] && "$PYTHON" -m pip --version >/dev/null 2>&1; then
    "$PYTHON" -m pip install -q flask
  else
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3-flask
  fi
fi
"$PYTHON" -c 'import flask; print("Flask:", getattr(flask,"__version__","installed"))' 2>/dev/null || true

echo '[2/7] Downloading enhanced bot...'
curl -fsSL --retry 3 "$REPO_RAW/telegram_bot_v2.py" -o "$V2.new"
curl -fsSL --retry 3 "$REPO_RAW/telegram_welcome.py" -o "$WELCOME.new"
"$PYTHON" -m py_compile "$V2.new" "$WELCOME.new"
mv "$V2.new" "$V2"
mv "$WELCOME.new" "$WELCOME"
chmod 750 "$V2" "$WELCOME"

echo '[3/7] Preparing configuration (existing file is NEVER overwritten)...'
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
fi
chmod 600 "$ENV"

if ! grep -q '^TELEGRAM_BOT_TOKEN=.' "$ENV"; then
  echo '[WARN] TELEGRAM_BOT_TOKEN is not configured. Configure it in NOVA Panel -> Telegram Bot.'
fi

echo '[4/7] Installing systemd override...'
cat > "$DROPIN" <<EOF
[Service]
ExecStart=
EnvironmentFile=-$ENV
ExecStart=$PYTHON $WELCOME
Restart=always
RestartSec=3
EOF
systemctl daemon-reload

echo '[5/7] Checking Python files...'
"$PYTHON" -m py_compile "$V2" "$WELCOME" "$BOT"

echo '[6/7] Restarting bot...'
systemctl enable "$SERVICE" >/dev/null 2>&1 || true
systemctl reset-failed "$SERVICE" >/dev/null 2>&1 || true
systemctl restart "$SERVICE"
sleep 2

echo '[7/7] Result:'
echo "Backup: $backup"
echo "Python: $PYTHON"
echo "Service: $(systemctl is-active "$SERVICE" || true)"
systemctl --no-pager --full status "$SERVICE" | sed -n '1,18p' || true

echo
echo 'Telegram configuration:'
if grep -q '^TELEGRAM_BOT_TOKEN=.' "$ENV"; then echo '  Token: configured'; else echo '  Token: NOT configured'; fi
grep -E '^(TELEGRAM_ADMIN_IDS|TELEGRAM_ALLOWED_IDS|VPN_DEFAULT_DAYS|NOVA_ROUTES_URL|NOVA_ROUTES_FILE|NOVA_ROUTES_INTERVAL)=' "$ENV" 2>/dev/null || true

echo
echo 'Update completed.'
