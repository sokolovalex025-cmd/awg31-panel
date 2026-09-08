#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root: sudo ./install.sh'; exit 1; }
. /etc/os-release
[ "${ID:-}" = ubuntu ] || { echo 'Требуется Ubuntu'; exit 1; }
BASE=/opt/awg31-panel
SRC="$(cd "$(dirname "$0")" && pwd)"
TS=$(date +%Y%m%d-%H%M%S)
AWG_DIR=/etc/amnezia/amneziawg
CONF="$AWG_DIR/awg0.conf"
mkdir -p "$BASE/backups" "$AWG_DIR/clients" /etc/awg31-panel
[ -f "$BASE/app.py" ] && cp -a "$BASE/app.py" "$BASE/backups/app-before-8.1-$TS.py"
[ -f "$BASE/panel.db" ] && cp -a "$BASE/panel.db" "$BASE/backups/panel-before-8.1-$TS.db"
[ -f "$CONF" ] && cp -a "$CONF" "$BASE/backups/awg0-before-8.1-$TS.conf"

apt-get update
apt-get install -y python3 python3-venv python3-pip curl iproute2 qrencode openssl iptables software-properties-common python3-launchpadlib gnupg2 "linux-headers-$(uname -r)"

if ! command -v awg >/dev/null 2>&1 || ! command -v awg-quick >/dev/null 2>&1; then
  add-apt-repository -y ppa:amnezia/ppa
  apt-get update
  apt-get install -y amneziawg
fi
if ! command -v awg >/dev/null 2>&1 || ! command -v awg-quick >/dev/null 2>&1; then
  add-apt-repository -y ppa:amnezia/ppa
  apt-get update
  apt-get install -y --reinstall amneziawg
fi

modprobe amneziawg >/dev/null 2>&1 || true
command -v awg >/dev/null 2>&1 || { echo 'ОШИБКА: awg не найден'; exit 1; }
command -v awg-quick >/dev/null 2>&1 || { echo 'ОШИБКА: awg-quick не найден'; exit 1; }
AWG_VERSION=$(awg --version 2>/dev/null || true)
KERNEL_VERSION=$(cat /sys/module/amneziawg/version 2>/dev/null || true)
echo "AmneziaWG: ${AWG_VERSION:-unknown}; kernel=${KERNEL_VERSION:-unknown}"

# Create a valid server interface on a fresh install.
# Existing user configuration is preserved.
if [ ! -s "$CONF" ]; then
  SERVER_PRIVATE_KEY=$(awg genkey)
  SERVER_PUBLIC_KEY=$(printf '%s' "$SERVER_PRIVATE_KEY" | awg pubkey)
  HEADER_KEY=$(awg genkey)
  WAN_IF=$(ip -4 route show default 2>/dev/null | awk 'NR==1{print $5}')
  [ -n "${WAN_IF:-}" ] || WAN_IF=eth0
  cat >"$CONF" <<EOF
[Interface]
Address = 10.66.66.1/24
ListenPort = 51820
PrivateKey = $SERVER_PRIVATE_KEY
MTU = 1280
Jc = 4
Jmin = 50
Jmax = 200
S1 = 30
S2 = 70
S3 = 25
S4 = 15
H1 = 1
H2 = 2
H3 = 3
H4 = 4
HeaderProtectionKey = $HEADER_KEY
RandomTrailers = true
DisableCookies = true
PostUp = iptables -A FORWARD -i awg0 -j ACCEPT; iptables -A FORWARD -o awg0 -j ACCEPT; iptables -t nat -A POSTROUTING -s 10.66.66.0/24 -o $WAN_IF -j MASQUERADE
PostDown = iptables -D FORWARD -i awg0 -j ACCEPT; iptables -D FORWARD -o awg0 -j ACCEPT; iptables -t nat -D POSTROUTING -s 10.66.66.0/24 -o $WAN_IF -j MASQUERADE
EOF
  chmod 600 "$CONF"
  printf '%s\n' "$SERVER_PUBLIC_KEY" > /etc/awg31-panel/server_public.key
  chmod 600 /etc/awg31-panel/server_public.key
fi
chmod 600 "$CONF"

# Enable forwarding for VPN clients.
sysctl -w net.ipv4.ip_forward=1 >/dev/null
cat >/etc/sysctl.d/99-awg31-panel.conf <<EOF
net.ipv4.ip_forward=1
EOF
sysctl --system >/dev/null 2>&1 || true

# Keep a NAT rule outside the config as a fallback.
WAN_IF=$(ip -4 route show default 2>/dev/null | awk 'NR==1{print $5}')
if [ -n "${WAN_IF:-}" ]; then
  iptables -t nat -C POSTROUTING -s 10.66.66.0/24 -o "$WAN_IF" -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.66.66.0/24 -o "$WAN_IF" -j MASQUERADE
fi

cp "$SRC/app.py" "$BASE/app.py"; chmod 600 "$BASE/app.py"
[ -f "$SRC/background.svg" ] && cp "$SRC/background.svg" "$BASE/background.svg"
for mod in naiveproxy_panel.py telegram_bot.py system_panel.py advanced_panel.py; do
  [ -f "$SRC/$mod" ] && cp "$SRC/$mod" "$BASE/$mod" && chmod 600 "$BASE/$mod"
done

python3 - "$BASE/panel.db" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1])
c.execute('CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL)')
c.execute('CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,address TEXT NOT NULL,private_key TEXT NOT NULL,public_key TEXT NOT NULL,psk TEXT NOT NULL,created INTEGER NOT NULL)')
c.execute("INSERT OR IGNORE INTO settings(k,v) VALUES('login','admin')")
c.execute("INSERT OR IGNORE INTO settings(k,v) VALUES('endpoint','')")
c.commit();c.close()
PY
NEW_DB=0; [ -f "$BASE/.initial_password" ] || NEW_DB=1
if [ "$NEW_DB" = 1 ]; then
  ADMIN_PASS=$(openssl rand -hex 12)
  python3 - "$BASE/panel.db" "$ADMIN_PASS" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('password',?)",(sys.argv[2],));c.commit();c.close()
open('/opt/awg31-panel/.initial_password','w').write(sys.argv[2]+'\n')
PY
  chmod 600 "$BASE/.initial_password"
fi

python3 -m venv "$BASE/venv"
"$BASE/venv/bin/pip" install -q 'Flask>=3,<4' 'qrcode[pil]>=7,<9'
"$BASE/venv/bin/python" -m py_compile "$BASE/app.py" "$BASE/naiveproxy_panel.py" "$BASE/telegram_bot.py" "$BASE/system_panel.py" "$BASE/advanced_panel.py"

# Validate the config before enabling the service.
if ! awg-quick strip awg0 >/dev/null 2>&1; then
  echo 'ОШИБКА: конфигурация awg0 не проходит awg-quick.'
  awg-quick strip awg0 || true
  exit 1
fi

SECRET=$(openssl rand -hex 32)
cat >/etc/systemd/system/awgpanel.service <<EOF
[Unit]
Description=AWG Panel 8.1 Mobile Strong + AmneziaWG 3.1
After=network-online.target awg-quick@awg0.service
Wants=network-online.target
[Service]
WorkingDirectory=$BASE
Environment=AWGPANEL_SECRET=$SECRET
ExecStart=$BASE/venv/bin/python $BASE/app.py
Restart=on-failure
RestartSec=2
[Install]
WantedBy=multi-user.target
EOF
cat >/etc/systemd/system/awgpanel-telegram.service <<EOF
[Unit]
Description=AWG Panel 8.1 Telegram Bot
After=network-online.target awgpanel.service
Wants=network-online.target
[Service]
WorkingDirectory=$BASE
EnvironmentFile=-/etc/awg31-panel/telegram.env
ExecStart=$BASE/venv/bin/python $BASE/telegram_bot.py
Restart=on-failure
RestartSec=3
NoNewPrivileges=false
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now awg-quick@awg0.service
sleep 2
if ! systemctl is-active --quiet awg-quick@awg0.service; then
  echo 'ОШИБКА: awg0 не запустился.'
  systemctl status awg-quick@awg0.service --no-pager -l || true
  journalctl -u awg-quick@awg0.service -n 80 --no-pager || true
  exit 1
fi

BOT_CONFIGURED=0; [ -s /etc/awg31-panel/telegram.env ] && BOT_CONFIGURED=1
systemctl enable --now awgpanel
if [ "$BOT_CONFIGURED" = 1 ]; then systemctl enable --now awgpanel-telegram.service; else systemctl disable --now awgpanel-telegram.service >/dev/null 2>&1 || true; fi
sleep 2
systemctl is-active --quiet awgpanel || { journalctl -u awgpanel -n 80 --no-pager; exit 1; }
IP=$(curl -4 -fsS --max-time 5 https://api.ipify.org || true)
echo "AWG Panel 8.1: http://${IP}:8080/login"
echo 'Login: admin'
if [ -f "$BASE/.initial_password" ]; then echo "Password: $(cat "$BASE/.initial_password")"; else echo 'Password: existing password preserved'; fi
echo "AWG interface: $(ip -br link show awg0 2>/dev/null || true)"
