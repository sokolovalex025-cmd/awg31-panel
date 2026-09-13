#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
REPO_URL="${REPO_URL:-https://github.com/sokolovalex025-cmd/awg31-panel.git}"
REPO_DIR="${REPO_DIR:-/root/awg31-panel}"
BASE="/opt/awg31-panel"
PANEL_SERVICE="/etc/systemd/system/awgpanel.service"
TG_SERVICE="/etc/systemd/system/awgpanel-telegram.service"
command -v awg >/dev/null 2>&1 || { echo 'AmneziaWG tool "awg" was not found.'; exit 2; }
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y git python3 python3-venv python3-pip curl qrencode
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" fetch origin main
  git -C "$REPO_DIR" reset --hard origin/main
else
  rm -rf "$REPO_DIR"
  git clone --depth 1 "$REPO_URL" "$REPO_DIR"
fi
python3 -m venv "$REPO_DIR/venv"
"$REPO_DIR/venv/bin/pip" install --upgrade pip
"$REPO_DIR/venv/bin/pip" install Flask 'qrcode[pil]'
mkdir -p "$BASE/backups"
for f in app.py nova11.py panel_bootstrap.py nova12_theme.py nova13_theme.py telegram_ui.py telegram_bot.py telegram_runner.py telegram_delete.py keenetic.py balancer.py balancer_provision.py keenetic-routing-guide.txt background.svg; do
  [ -f "$REPO_DIR/$f" ] && install -m 644 "$REPO_DIR/$f" "$BASE/$f"
done
chmod 755 "$BASE/nova11.py" "$BASE/panel_bootstrap.py" "$BASE/telegram_bot.py" "$BASE/telegram_runner.py" "$BASE/telegram_delete.py"
SECRET_DIR=/etc/awg31-panel
SECRET_FILE="$SECRET_DIR/panel-secret"
mkdir -p "$SECRET_DIR"
chmod 700 "$SECRET_DIR"
if [ ! -s "$SECRET_FILE" ]; then
  umask 077
  "$REPO_DIR/venv/bin/python" -c 'import secrets;print(secrets.token_hex(32))' > "$SECRET_FILE"
fi
chmod 600 "$SECRET_FILE"
SECRET=$(cat "$SECRET_FILE")
cat > "$PANEL_SERVICE" <<EOF
[Unit]
Description=NOVA 11 Network Control Center - AmneziaWG 3.1
After=network-online.target awg-quick@awg0.service
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=$BASE
Environment=AWGPANEL_SECRET=$SECRET
ExecStart=$REPO_DIR/venv/bin/python $BASE/panel_bootstrap.py
Restart=on-failure
RestartSec=2
NoNewPrivileges=false
[Install]
WantedBy=multi-user.target
EOF
cat > "$TG_SERVICE" <<EOF
[Unit]
Description=NOVA Telegram VPN Bot
After=network-online.target awgpanel.service awg-quick@awg0.service
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=$BASE
Environment=PYTHONUNBUFFERED=1
ExecStart=$REPO_DIR/venv/bin/python $BASE/telegram_runner.py
Restart=always
RestartSec=5
NoNewPrivileges=false
[Install]
WantedBy=multi-user.target
EOF
"$REPO_DIR/venv/bin/python" -m py_compile "$BASE/app.py" "$BASE/nova11.py" "$BASE/panel_bootstrap.py" "$BASE/telegram_ui.py" "$BASE/telegram_bot.py" "$BASE/telegram_runner.py" "$BASE/telegram_delete.py" "$BASE/keenetic.py" "$BASE/balancer.py"
systemctl daemon-reload
systemctl enable awgpanel >/dev/null
systemctl restart awgpanel
sleep 2
systemctl is-active --quiet awgpanel
curl -fsS --max-time 5 http://127.0.0.1:8080/login >/dev/null
systemctl enable awgpanel-telegram >/dev/null
systemctl restart awgpanel-telegram || true
printf '\nNOVA 11 installed successfully.\n'
printf 'Panel: active (awgpanel)\n'
printf 'Telegram: runtime installed (awgpanel-telegram)\n'
printf 'AWG interface/config: preserved\n'
printf 'Keenetic: native NOVA menu + /keenetic\n'
printf 'Health: /api/nova/health\n'
