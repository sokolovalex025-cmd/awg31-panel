#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
REPO_URL="${REPO_URL:-https://github.com/sokolovalex025-cmd/awg31-panel.git}"; REPO_DIR="${REPO_DIR:-/root/awg31-panel}"; BASE=/opt/awg31-panel
[ -r /etc/os-release ] && . /etc/os-release || exit 2
case "${ID:-}" in ubuntu|debian) ;; *) echo "NOVA MAX supports Debian/Ubuntu"; exit 2;; esac
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y git python3 python3-venv python3-pip curl qrencode iptables nginx dnsutils iproute2 iputils-ping openssl fail2ban
command -v awg >/dev/null 2>&1 || { echo 'AmneziaWG tool "awg" was not found. Install AWG 3.1 first.'; exit 3; }
mkdir -p "$BASE/backups"
if [ -d "$REPO_DIR/.git" ]; then git -C "$REPO_DIR" fetch origin main; git -C "$REPO_DIR" reset --hard origin/main; else rm -rf "$REPO_DIR"; git clone --depth 1 "$REPO_URL" "$REPO_DIR"; fi
python3 -m venv "$REPO_DIR/venv"; "$REPO_DIR/venv/bin/pip" install --upgrade pip; "$REPO_DIR/venv/bin/pip" install Flask 'qrcode[pil]' pytest
for f in app.py nova11.py panel_bootstrap.py nova12_theme.py nova13_theme.py nova14_theme.py nova15_theme.py nova16_server_card_fix.py nova_awg31_fix.py antiblock.py nova_shield.py nova_resilience.py domain_manager.py telegram_ui.py telegram_bot.py telegram_runner.py telegram_delete.py keenetic.py balancer.py balancer_provision.py keenetic-routing-guide.txt background.svg nova-network-fix.sh nova_mobile_diagnostics.py nova-max-backup.sh nova-migrate.sh nova-verify.sh nova-watchdog.sh nova-watchdog.service nova-watchdog.timer; do [ -f "$REPO_DIR/$f" ] && install -m 644 "$REPO_DIR/$f" "$BASE/$f"; done
chmod 755 "$BASE"/*.sh "$BASE"/nova_awg31_fix.py "$BASE"/panel_bootstrap.py "$BASE"/nova-watchdog.sh 2>/dev/null || true
SECRET_DIR=/etc/awg31-panel; SECRET_FILE="$SECRET_DIR/panel-secret"; mkdir -p "$SECRET_DIR"; chmod 700 "$SECRET_DIR"
if [ ! -s "$SECRET_FILE" ]; then umask 077; "$REPO_DIR/venv/bin/python" -c 'import secrets;print(secrets.token_hex(32))' > "$SECRET_FILE"; fi
chmod 600 "$SECRET_FILE"; SECRET=$(cat "$SECRET_FILE")
cat > /etc/systemd/system/awg31-network.service <<EOF
[Unit]
Description=NOVA AWG network fix
After=network-online.target awg-quick@awg0.service
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=$BASE/nova-network-fix.sh
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
EOF
cat > /etc/systemd/system/awgpanel.service <<EOF
[Unit]
Description=NOVA MAX Network Control Center - AmneziaWG 3.1
After=network-online.target awg-quick@awg0.service awg31-network.service
Wants=network-online.target awg31-network.service
[Service]
Type=simple
WorkingDirectory=$BASE
Environment=AWGPANEL_SECRET=$SECRET
ExecStart=$REPO_DIR/venv/bin/python $BASE/panel_bootstrap.py
Restart=on-failure
RestartSec=2
[Install]
WantedBy=multi-user.target
EOF
cat > /etc/systemd/system/awgpanel-telegram.service <<EOF
[Unit]
Description=NOVA MAX Telegram VPN Bot
After=network-online.target awgpanel.service awg-quick@awg0.service
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=$BASE
Environment=PYTHONUNBUFFERED=1
ExecStart=$REPO_DIR/venv/bin/python $BASE/telegram_runner.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF
cat > /etc/nginx/sites-available/awg31-panel <<'EOF'
server { listen 80 default_server; listen [::]:80 default_server; server_name _; client_max_body_size 20m; proxy_read_timeout 120s; proxy_send_timeout 120s; location / { proxy_pass http://127.0.0.1:8080; proxy_http_version 1.1; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; proxy_set_header X-Forwarded-Proto $scheme; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; } }
EOF
ln -sfn /etc/nginx/sites-available/awg31-panel /etc/nginx/sites-enabled/awg31-panel; rm -f /etc/nginx/sites-enabled/default; nginx -t
"$REPO_DIR/venv/bin/python" -m py_compile "$BASE"/*.py
"$REPO_DIR/venv/bin/python" "$BASE/nova_awg31_fix.py"
systemctl daemon-reload; systemctl enable --now awg31-network; systemctl enable --now awgpanel; sleep 2; curl -fsS --max-time 8 http://127.0.0.1:8080/login >/dev/null
systemctl enable --now nova-watchdog.timer; systemctl enable --now fail2ban; systemctl enable nginx; systemctl restart nginx; "$BASE/nova-verify.sh"
