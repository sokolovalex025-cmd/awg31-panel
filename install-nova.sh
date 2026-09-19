#!/usr/bin/env bash
set -Eeuo pipefail

# NOVA 12 / AmneziaWG 3.1 — clean server installer
# Ubuntu 24.04 LTS recommended. Run as root.
[ "$(id -u)" -eq 0 ] || { echo "Run as root."; exit 1; }

REPO_URL="https://github.com/sokolovalex025-cmd/awg31-panel.git"
REPO_DIR="/root/awg31-panel"
BASE="/opt/awg31-panel"
PORT="${NOVA_PORT:-1234}"

echo "=== NOVA 12 + AmneziaWG 3.1 installer ==="

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  software-properties-common python3-launchpadlib gnupg2 \
  linux-headers-"$(uname -r)" git python3 python3-venv python3-pip \
  curl qrencode iptables nftables nginx dnsutils iproute2 iputils-ping fail2ban

# Official AmneziaWG Ubuntu installation path: PPA + amneziawg package.
add-apt-repository -y ppa:amnezia/ppa
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y amneziawg

command -v awg >/dev/null || { echo "ERROR: awg was not installed."; exit 2; }
command -v awg-quick >/dev/null || { echo "ERROR: awg-quick was not installed."; exit 2; }

echo
echo "=== Panel administrator ==="
while :; do
  read -r -p "Введите имя пользователя [admin]: " NOVA_LOGIN
  NOVA_LOGIN="${NOVA_LOGIN:-admin}"
  [[ "$NOVA_LOGIN" =~ ^[A-Za-z0-9._-]{3,64}$ ]] && break
  echo "Недопустимое имя. Используйте 3-64 символа: A-Z a-z 0-9 . _ -"
done
while :; do
  read -r -s -p "Введите пароль: " NOVA_PASSWORD; echo
  [ "${#NOVA_PASSWORD}" -ge 8 ] || { echo "Пароль минимум 8 символов."; continue; }
  read -r -s -p "Повторите пароль: " NOVA_PASSWORD2; echo
  [ "$NOVA_PASSWORD" = "$NOVA_PASSWORD2" ] && break
  echo "Пароли не совпадают."
done
unset NOVA_PASSWORD2

echo
echo "=== Installing NOVA ==="
if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" fetch origin main
  git -C "$REPO_DIR" checkout -B main origin/main
  git -C "$REPO_DIR" reset --hard origin/main
else
  rm -rf "$REPO_DIR"
  git clone --depth 1 --branch main "$REPO_URL" "$REPO_DIR"
fi

python3 -m venv "$REPO_DIR/venv"
"$REPO_DIR/venv/bin/pip" install --upgrade pip
"$REPO_DIR/venv/bin/pip" install Flask 'qrcode[pil]' pytest

mkdir -p "$BASE/backups" /etc/amnezia/amneziawg
for f in app.py nova11.py panel_bootstrap.py nova12_theme.py nova13_theme.py nova14_theme.py nova15_theme.py nova16_server_card_fix.py nova_scroll_buttons.py nova_awg31_fix.py nova_toolza_center.py awg-toolz-daemon.py awg-toolz.service nova_mobile_diagnostics.py nova12_diagnostics.py nova_mobile_diagnostics3.py nova_mobile_monitor.py nova12_clients.py nova_client_center.py nova12_ui.py nova_diagnostics.py nova_doctor_ui.py nova_command_center.py nova_resilience.py nova_shield.py antiblock.py domain_manager.py security_hardening.py telegram_ui.py telegram_bot.py telegram_runner.py telegram_delete.py telegram_payments.py system_panel.py mobile_nav.py keenetic.py balancer.py balancer_provision.py naiveproxy_panel.py background.svg keenetic-routing-guide.txt nova-network-fix.sh nova-max-backup.sh nova-migrate.sh nova-verify.sh nova-watchdog.sh nova-watchdog.service nova-watchdog.timer update-panel.sh; do
  [ -f "$REPO_DIR/$f" ] && install -m 644 "$REPO_DIR/$f" "$BASE/$f"
done

# Generate a fresh AWG server config only when none exists.
CONF="/etc/amnezia/amneziawg/awg0.conf"
if [ ! -s "$CONF" ]; then
  SERVER_PRIVATE="$(awg genkey)"
  SERVER_PUBLIC="$(printf '%s' "$SERVER_PRIVATE" | awg pubkey)"
  umask 077
  cat > "$CONF" <<EOF
[Interface]
Address = 10.66.66.1/24
ListenPort = $PORT
PrivateKey = $SERVER_PRIVATE
Jc = 4
Jmin = 40
Jmax = 120
S1 = 16
S2 = 16
S3 = 16
S4 = 16
H1 = 1
H2 = 2
H3 = 3
H4 = 4
ContentPaddingAddition = 0-64
RekeyAfterTime = 120-180
RekeyTimeout = 3-8
RejectAfterTime = 150-210
KeepaliveTimeout = 8-15
MaxHandshakeAttempts = 8-15
RandomTrailers = on
DisableCookies = on
EOF
  printf '%s\n' "$SERVER_PUBLIC" > "$BASE/server-public.key"
  chmod 600 "$BASE/server-public.key" "$CONF"
fi

# NAT / forwarding for the AWG subnet.
cat > "$BASE/nova-network-fix.sh" <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail
sysctl -w net.ipv4.ip_forward=1 >/dev/null
WAN="$(ip -4 route show default | awk '{print $5; exit}')"
[ -n "$WAN" ] || exit 0
iptables -C FORWARD -i awg0 -o "$WAN" -j ACCEPT 2>/dev/null || iptables -A FORWARD -i awg0 -o "$WAN" -j ACCEPT
iptables -C FORWARD -i "$WAN" -o awg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || iptables -A FORWARD -i "$WAN" -o awg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
iptables -t nat -C POSTROUTING -s 10.66.66.0/24 -o "$WAN" -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.66.66.0/24 -o "$WAN" -j MASQUERADE
EOF
chmod 755 "$BASE/nova-network-fix.sh" "$BASE/nova_awg31_fix.py" "$BASE/nova-verify.sh" "$BASE/nova-max-backup.sh" "$BASE/nova-migrate.sh" "$BASE/nova-watchdog.sh"

SECRET_DIR=/etc/awg31-panel
mkdir -p "$SECRET_DIR"
chmod 700 "$SECRET_DIR"
if [ ! -s "$SECRET_DIR/panel-secret" ]; then
  umask 077
  "$REPO_DIR/venv/bin/python" -c 'import secrets; print(secrets.token_hex(32))' > "$SECRET_DIR/panel-secret"
fi
SECRET="$(cat "$SECRET_DIR/panel-secret")"

cat > /etc/systemd/system/awg31-network.service <<EOF
[Unit]
Description=NOVA AWG network and NAT
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
Description=NOVA 12 Network Control Center - AmneziaWG 3.1
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

# Install defaults, then replace the generated admin credentials with the values chosen above.
"$REPO_DIR/venv/bin/python" -m py_compile "$BASE"/*.py
mkdir -p /etc/awg-toolz
umask 077
[ -s /etc/awg-toolz/token ] || python3 -c "import secrets; print(secrets.token_urlsafe(48))" > /etc/awg-toolz/token
chmod 600 /etc/awg-toolz/token
install -m 644 "$BASE/awg-toolz.service" /etc/systemd/system/awg-toolz.service
chmod 755 "$BASE/awg-toolz-daemon.py"
systemctl daemon-reload
iptables -C INPUT -p udp --dport "$PORT" -j ACCEPT 2>/dev/null || iptables -I INPUT -p udp --dport "$PORT" -j ACCEPT
systemctl enable --now awg-quick@awg0.service
systemctl enable --now awg-toolz.service
"$REPO_DIR/venv/bin/python" "$BASE/nova_awg31_fix.py"
systemctl enable --now awg31-network.service
systemctl enable awgpanel.service
systemctl restart awgpanel.service
sleep 2
systemctl is-active --quiet awgpanel.service
curl -fsS --max-time 8 http://127.0.0.1:8080/login >/dev/null

"$REPO_DIR/venv/bin/python" - "$NOVA_LOGIN" "$NOVA_PASSWORD" <<'PY'
import sqlite3, sys
db="/opt/awg31-panel/panel.db"
login,password=sys.argv[1],sys.argv[2]
c=sqlite3.connect(db)
c.execute("CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT)")
c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('login',?)",(login,))
c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('password',?)",(password,))
c.commit(); c.close()
PY
unset NOVA_PASSWORD

systemctl enable --now nova-watchdog.timer 2>/dev/null || true
systemctl enable --now nginx
systemctl enable --now fail2ban

"$BASE/nova_awg31_fix.py" check
"$BASE/nova-verify.sh" || true

echo
echo "=============================================="
echo " NOVA 12 INSTALL: SUCCESS"
echo "=============================================="
echo "Panel: http://SERVER-IP/"
echo "Toolza Center: /awg-toolza"
echo "Mobile Diagnostics: /mobile-diagnostics-v3"
echo "Live Monitor: /live-monitor"
echo "Doctor: /doctor"
echo "AWG UDP port: $PORT"
echo "Admin user: $NOVA_LOGIN"
echo "=============================================="
