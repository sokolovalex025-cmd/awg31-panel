#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
REPO_URL="${REPO_URL:-https://github.com/sokolovalex025-cmd/awg31-panel.git}"
REPO_DIR="${REPO_DIR:-/root/awg31-panel}"
BASE="/opt/awg31-panel"
PANEL_SERVICE="/etc/systemd/system/awgpanel.service"
TG_SERVICE="/etc/systemd/system/awgpanel-telegram.service"
NET_SERVICE="/etc/systemd/system/awg31-network.service"
command -v awg >/dev/null 2>&1 || { echo 'AmneziaWG tool "awg" was not found.'; exit 2; }
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y git python3 python3-venv python3-pip curl qrencode iptables nginx
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
for f in app.py nova11.py panel_bootstrap.py nova12_theme.py nova13_theme.py nova14_theme.py telegram_ui.py telegram_bot.py telegram_runner.py telegram_delete.py keenetic.py balancer.py balancer_provision.py keenetic-routing-guide.txt background.svg nova-network-fix.sh nova_mobile_diagnostics.py; do
  [ -f "$REPO_DIR/$f" ] && install -m 644 "$REPO_DIR/$f" "$BASE/$f"
done
chmod 755 "$BASE/nova11.py" "$BASE/panel_bootstrap.py" "$BASE/telegram_bot.py" "$BASE/telegram_runner.py" "$BASE/telegram_delete.py" "$BASE/nova-network-fix.sh"
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
cat > "$NET_SERVICE" <<EOF
[Unit]
Description=NOVA AWG client NAT and mobile network fix
After=network-online.target awg-quick@awg0.service
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=$BASE/nova-network-fix.sh
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
EOF
cat > "$PANEL_SERVICE" <<EOF
[Unit]
Description=NOVA 11 Network Control Center - AmneziaWG 3.1
After=network-online.target awg-quick@awg0.service awg31-network.service
Wants=network-online.target awg31-network.service
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
cat > /etc/nginx/sites-available/awg31-panel <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    client_max_body_size 20m;
    proxy_read_timeout 120s;
    proxy_send_timeout 120s;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF
ln -sfn /etc/nginx/sites-available/awg31-panel /etc/nginx/sites-enabled/awg31-panel
rm -f /etc/nginx/sites-enabled/default
nginx -t
"$REPO_DIR/venv/bin/python" -m py_compile "$BASE/app.py" "$BASE/nova11.py" "$BASE/panel_bootstrap.py" "$BASE/telegram_ui.py" "$BASE/telegram_bot.py" "$BASE/telegram_runner.py" "$BASE/telegram_delete.py" "$BASE/keenetic.py" "$BASE/balancer.py" "$BASE/nova_mobile_diagnostics.py" "$BASE/nova14_theme.py"
systemctl daemon-reload
systemctl enable awg31-network >/dev/null
systemctl restart awg31-network
systemctl is-active --quiet awg31-network
systemctl enable awgpanel >/dev/null
systemctl restart awgpanel
sleep 2
systemctl is-active --quiet awgpanel
curl -fsS --max-time 5 http://127.0.0.1:8080/login >/dev/null
systemctl enable awgpanel-telegram >/dev/null
systemctl restart awgpanel-telegram || true
systemctl enable nginx >/dev/null
systemctl restart nginx
systemctl is-active --quiet nginx
printf '\nNOVA 11 installed successfully.\n'
printf 'Panel: active (awgpanel)\n'
printf 'Telegram: runtime installed (awgpanel-telegram)\n'
printf 'Network: persistent AWG client NAT + IPv4 forwarding\n'
printf 'Client DNS: 1.1.1.1,8.8.8.8 (old 10.66.66.1 default migrated)\n'
printf 'Mobile diagnostics: /mobile-diagnostics and /api/mobile-diagnostics\n'
printf 'Sidebar: NOVA14 scrollbar + status card flow fix\n'
printf 'Nginx: reverse proxy :80 -> 127.0.0.1:8080\n'
printf 'AWG interface/config: preserved\n'
printf 'Keenetic: native NOVA menu + /keenetic\n'
printf 'Health: /api/nova/health\n'
