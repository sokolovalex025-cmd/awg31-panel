#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root: sudo ./install.sh'; exit 1; }
. /etc/os-release
[ "${ID:-}" = ubuntu ] || { echo 'Требуется Ubuntu'; exit 1; }
BASE=/opt/awg31-panel; SRC="$(cd "$(dirname "$0")" && pwd)"; TS=$(date +%Y%m%d-%H%M%S)
mkdir -p "$BASE/backups" /etc/amnezia/amneziawg/clients /etc/awg31-panel
[ -f "$BASE/app.py" ] && cp -a "$BASE/app.py" "$BASE/backups/app-before-8.1-$TS.py"
[ -f "$BASE/panel.db" ] && cp -a "$BASE/panel.db" "$BASE/backups/panel-before-8.1-$TS.db"
[ -f /etc/amnezia/amneziawg/awg0.conf ] && cp -a /etc/amnezia/amneziawg/awg0.conf "$BASE/backups/awg0-before-8.1-$TS.conf"
apt-get update
apt-get install -y python3 python3-venv python3-pip curl iproute2 qrencode openssl iptables software-properties-common python3-launchpadlib gnupg2 "linux-headers-$(uname -r)"

# Install the official AmneziaWG package automatically when AWG is missing.
# Ubuntu 24.04 is supported by the official Amnezia PPA. Current PPA builds
# provide the AmneziaWG 3.1 userspace tools and kernel module on supported kernels.
if ! command -v awg >/dev/null 2>&1 || ! command -v awg-quick >/dev/null 2>&1; then
  add-apt-repository -y ppa:amnezia/ppa
  apt-get update
  apt-get install -y amneziawg
fi

# If AWG exists but is incomplete, repair it from the official PPA.
if ! command -v awg >/dev/null 2>&1 || ! command -v awg-quick >/dev/null 2>&1; then
  add-apt-repository -y ppa:amnezia/ppa
  apt-get update
  apt-get install -y --reinstall amneziawg
fi

# Load the kernel module when possible and verify the actual AWG userspace.
modprobe amneziawg >/dev/null 2>&1 || true
AWG_VERSION=$(awg --version 2>/dev/null || true)
KERNEL_VERSION=$(cat /sys/module/amneziawg/version 2>/dev/null || true)
if ! command -v awg >/dev/null 2>&1 || ! command -v awg-quick >/dev/null 2>&1; then
  echo 'ОШИБКА: AmneziaWG не установился (awg/awg-quick не найдены).'
  echo 'Проверьте: apt-cache policy amneziawg'
  exit 1
fi
if [[ "$AWG_VERSION" != *"3.1"* ]] && [[ "$KERNEL_VERSION" != 3.1* ]]; then
  echo 'ОШИБКА: установлен AWG, но версия 3.1 не обнаружена.'
  echo "awg: ${AWG_VERSION:-неизвестно}"
  echo "kernel: ${KERNEL_VERSION:-не загружен}"
  echo 'Проверьте: awg --version; cat /sys/module/amneziawg/version'
  exit 1
fi
echo "AmneziaWG найден: ${AWG_VERSION:-userspace неизвестен}; kernel=${KERNEL_VERSION:-не загружен}"

cp "$SRC/app.py" "$BASE/app.py"; chmod 600 "$BASE/app.py"
[ -f "$SRC/background.svg" ] && cp "$SRC/background.svg" "$BASE/background.svg"
for mod in naiveproxy_panel.py telegram_bot.py system_panel.py advanced_panel.py; do [ -f "$SRC/$mod" ] && cp "$SRC/$mod" "$BASE/$mod" && chmod 600 "$BASE/$mod"; done

# app.py is already the native AWG Panel 8.1 implementation.
# No runtime version patching is performed here.

python3 - "$BASE/panel.db" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);c.execute('CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL)');c.execute('CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,address TEXT NOT NULL,private_key TEXT NOT NULL,public_key TEXT NOT NULL,psk TEXT NOT NULL,created INTEGER NOT NULL)');c.execute("INSERT OR IGNORE INTO settings(k,v) VALUES('login','admin')");c.execute("INSERT OR IGNORE INTO settings(k,v) VALUES('endpoint','')");c.commit();c.close()
PY
NEW_DB=0;[ -f "$BASE/.initial_password" ]||NEW_DB=1
if [ "$NEW_DB" = 1 ];then ADMIN_PASS=$(openssl rand -hex 12);python3 - "$BASE/panel.db" "$ADMIN_PASS" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('password',?)",(sys.argv[2],));c.commit();c.close();open('/opt/awg31-panel/.initial_password','w').write(sys.argv[2]+'\n')
PY
chmod 600 "$BASE/.initial_password";else ADMIN_PASS=$(python3 - "$BASE/panel.db" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]);r=c.execute("SELECT v FROM settings WHERE k='password'").fetchone();print(r[0] if r else 'change-me');c.close()
PY
);fi
python3 -m venv "$BASE/venv"
"$BASE/venv/bin/pip" install -q 'Flask>=3,<4' 'qrcode[pil]>=7,<9'
"$BASE/venv/bin/python" -m py_compile "$BASE/app.py" "$BASE/naiveproxy_panel.py" "$BASE/telegram_bot.py" "$BASE/system_panel.py" "$BASE/advanced_panel.py"
SECRET=$(openssl rand -hex 32)
cat >/etc/systemd/system/awgpanel.service <<EOF
[Unit]
Description=AWG Panel 8.1 Mobile Strong + NaiveProxy + Telegram + Monitoring
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
BOT_CONFIGURED=0;[ -s /etc/awg31-panel/telegram.env ]&&BOT_CONFIGURED=1
systemctl daemon-reload;systemctl enable --now awgpanel
if [ "$BOT_CONFIGURED" = 1 ];then systemctl enable --now awgpanel-telegram.service;else systemctl disable --now awgpanel-telegram.service >/dev/null 2>&1||true;fi
sleep 2;systemctl is-active --quiet awgpanel||{ journalctl -u awgpanel -n 80 --no-pager;exit 1; }
IP=$(curl -4 -fsS --max-time 5 https://api.ipify.org||true)
echo "AWG Panel 8.1: http://${IP}:8080/login";echo "Login: admin";if [ -f "$BASE/.initial_password" ];then echo "Password: $(cat "$BASE/.initial_password")";else echo 'Password: existing password preserved';fi
