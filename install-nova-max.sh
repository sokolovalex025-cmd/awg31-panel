#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root.'; exit 1; }
REPO_URL="${REPO_URL:-https://github.com/sokolovalex025-cmd/awg31-panel.git}"
REPO_DIR="${REPO_DIR:-/root/awg31-panel}"
BASE=/opt/awg31-panel
BACKUP_ROOT=/root/nova-max-backups

if [ -r /etc/os-release ]; then . /etc/os-release; else echo 'Unsupported Linux: /etc/os-release missing.'; exit 2; fi
case "${ID:-}" in ubuntu|debian) ;; *) echo "NOVA MAX installer supports Debian/Ubuntu. Detected: ${ID:-unknown}"; exit 2;; esac

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y git python3 python3-venv python3-pip curl qrencode iptables nginx dnsutils iproute2 iputils-ping

if ! command -v awg >/dev/null 2>&1; then
  cat >&2 <<'EOF'
AmneziaWG (awg) is not installed on this VPS.

For a clean server, install AmneziaWG first with the official installer, enable
AWG 3.1 if desired, then run this NOVA MAX installer again. The installer will
NOT silently replace an existing AWG interface or generate a new server key.

Official installer:
https://github.com/wiresock/amneziawg-install
EOF
  exit 3
fi

mkdir -p "$BACKUP_ROOT" "$BASE/backups"
if [ -f "$BASE/panel.db" ] || [ -f /etc/systemd/system/awgpanel.service ]; then
  TS=$(date +%Y%m%d-%H%M%S); DEST="$BACKUP_ROOT/pre-install-$TS"; mkdir -p "$DEST"
  [ -f "$BASE/panel.db" ] && cp -a "$BASE/panel.db" "$DEST/"
  [ -f /etc/awg31-panel/panel-secret ] && cp -a /etc/awg31-panel/panel-secret "$DEST/"
  [ -f /etc/nginx/sites-available/awg31-panel ] && cp -a /etc/nginx/sites-available/awg31-panel "$DEST/"
  if command -v awg >/dev/null 2>&1; then awg show awg0 > "$DEST/awg0-show.txt" 2>&1 || true; fi
  echo "Pre-install backup: $DEST"
fi

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

for f in app.py nova11.py panel_bootstrap.py nova12_theme.py nova13_theme.py nova14_theme.py antiblock.py nova_shield.py nova_resilience.py domain_manager.py telegram_ui.py telegram_bot.py telegram_runner.py telegram_delete.py keenetic.py balancer.py balancer_provision.py keenetic-routing-guide.txt background.svg nova-network-fix.sh nova_mobile_diagnostics.py nova-max-backup.sh; do
  [ -f "$REPO_DIR/$f" ] && install -m 644 "$REPO_DIR/$f" "$BASE/$f"
done
chmod 755 "$BASE/nova11.py" "$BASE/panel_bootstrap.py" "$BASE/telegram_bot.py" "$BASE/telegram_runner.py" "$BASE/telegram_delete.py" "$BASE/nova-network-fix.sh" "$BASE/antiblock.py" "$BASE/nova_shield.py" "$BASE/nova_resilience.py" "$BASE/nova-max-backup.sh"

SECRET_DIR=/etc/awg31-panel; SECRET_FILE="$SECRET_DIR/panel-secret"; mkdir -p "$SECRET_DIR"; chmod 700 "$SECRET_DIR"
if [ ! -s "$SECRET_FILE" ]; then umask 077; "$REPO_DIR/venv/bin/python" -c 'import secrets;print(secrets.token_hex(32))' > "$SECRET_FILE"; fi
chmod 600 "$SECRET_FILE"; SECRET=$(cat "$SECRET_FILE")

cat > /etc/systemd/system/awg31-network.service <<EOF
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
NoNewPrivileges=false
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
NoNewPrivileges=false
[Install]
WantedBy=multi-user.target
EOF

cat > /etc/nginx/sites-available/awg31-panel <<'EOF'
server { listen 80 default_server; listen [::]:80 default_server; server_name _; client_max_body_size 20m; proxy_read_timeout 120s; proxy_send_timeout 120s; location / { proxy_pass http://127.0.0.1:8080; proxy_http_version 1.1; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; proxy_set_header X-Forwarded-Proto $scheme; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; } }
EOF
ln -sfn /etc/nginx/sites-available/awg31-panel /etc/nginx/sites-enabled/awg31-panel
rm -f /etc/nginx/sites-enabled/default
nginx -t

"$REPO_DIR/venv/bin/python" -m py_compile "$BASE/app.py" "$BASE/nova11.py" "$BASE/panel_bootstrap.py" "$BASE/antiblock.py" "$BASE/nova_shield.py" "$BASE/nova_resilience.py" "$BASE/domain_manager.py" "$BASE/telegram_ui.py" "$BASE/telegram_bot.py" "$BASE/telegram_runner.py" "$BASE/telegram_delete.py" "$BASE/keenetic.py" "$BASE/balancer.py" "$BASE/nova_mobile_diagnostics.py" "$BASE/nova14_theme.py"

systemctl daemon-reload
systemctl enable awg31-network >/dev/null
systemctl restart awg31-network
systemctl enable awgpanel >/dev/null
systemctl restart awgpanel
sleep 2
systemctl is-active --quiet awgpanel
curl -fsS --max-time 8 http://127.0.0.1:8080/login >/dev/null
systemctl enable awgpanel-telegram >/dev/null
systemctl restart awgpanel-telegram || true
systemctl enable nginx >/dev/null
systemctl restart nginx
systemctl is-active --quiet nginx

printf '\nNOVA MAX installed successfully.\n'
printf 'Panel:       /\n'
printf 'Resilience:  /resilience\n'
printf 'Shield:      /shield\n'
printf 'AntiBlock:   /antiblock\n'
printf 'Mobile:      /mobile-diagnostics\n'
printf 'Keenetic:    /keenetic\n'
printf 'Domains:     /domains\n'
printf 'Health API:  /api/nova/health\n'
printf 'Backup:      %s/nova-max-backup.sh\n' "$BASE"
printf 'AWG0:        existing interface preserved\n'
