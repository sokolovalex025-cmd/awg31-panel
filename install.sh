#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive

[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root: sudo ./install.sh'; exit 1; }
[ -r /etc/os-release ] || { echo 'ОШИБКА: /etc/os-release не найден.'; exit 1; }
. /etc/os-release
case "${ID:-}:${VERSION_ID:-}" in
  ubuntu:22.04|ubuntu:24.04|debian:12|debian:13) ;;
  *) echo "ОШИБКА: поддерживаются Ubuntu 22.04/24.04 и Debian 12/13."; exit 1;;
esac
command -v systemctl >/dev/null 2>&1 || { echo 'ОШИБКА: требуется systemd.'; exit 1; }
ARCH=$(dpkg --print-architecture 2>/dev/null || true)
[ "$ARCH" = amd64 ] || { echo "ОШИБКА: требуется amd64/x86_64, получено ${ARCH:-unknown}."; exit 1; }

BASE=/opt/awg31-panel
SRC=$(cd "$(dirname "$0")" && pwd)
TS=$(date +%Y%m%d-%H%M%S)
AWG_DIR=/etc/amnezia/amneziawg
CONF="$AWG_DIR/awg0.conf"
mkdir -p "$BASE/backups" "$AWG_DIR/clients" /etc/awg31-panel
[ -f "$BASE/app.py" ] && cp -a "$BASE/app.py" "$BASE/backups/app-before-install-$TS.py"
[ -f "$BASE/panel.db" ] && cp -a "$BASE/panel.db" "$BASE/backups/panel-before-install-$TS.db"
[ -f "$CONF" ] && cp -a "$CONF" "$BASE/backups/awg0-before-install-$TS.conf"

apt-get update
apt-get install -y ca-certificates curl gnupg2 iproute2 iptables python3 python3-venv python3-pip qrencode openssl

install_awg_ubuntu(){
  apt-get install -y software-properties-common python3-launchpadlib
  if ! apt-cache policy amneziawg 2>/dev/null | grep -q '^  Candidate:'; then
    add-apt-repository -y ppa:amnezia/ppa
    apt-get update
  fi
  apt-get install -y amneziawg
}

install_awg_debian(){
  apt-get install -y linux-headers-amd64 || apt-get install -y "linux-headers-$(uname -r)" || true
  install -d -m 0755 /etc/apt/keyrings
  tmp=$(mktemp)
  curl -fsSL 'https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x57290828&output=armor' -o "$tmp"
  gpg --batch --yes --dearmor -o /etc/apt/keyrings/amnezia-archive-keyring.gpg "$tmp"
  rm -f "$tmp"
  cat >/etc/apt/sources.list.d/amneziawg.list <<'EOF'
deb [signed-by=/etc/apt/keyrings/amnezia-archive-keyring.gpg] https://ppa.launchpadcontent.net/amnezia/ppa/ubuntu focal main
EOF
  apt-get update
  apt-get install -y amneziawg
}

if ! command -v awg >/dev/null 2>&1 || ! command -v awg-quick >/dev/null 2>&1; then
  case "$ID" in
    ubuntu) install_awg_ubuntu ;;
    debian) install_awg_debian ;;
  esac
fi
command -v awg >/dev/null 2>&1 || { echo 'ОШИБКА: awg не найден.'; exit 1; }
command -v awg-quick >/dev/null 2>&1 || { echo 'ОШИБКА: awg-quick не найден.'; exit 1; }
modprobe amneziawg >/dev/null 2>&1 || true
TOOLS_VERSION=$(awg --version 2>/dev/null || true)
MODULE_VERSION=$(cat /sys/module/amneziawg/version 2>/dev/null || true)
echo "AmneziaWG tools: ${TOOLS_VERSION:-unknown}"
echo "AmneziaWG kernel: ${MODULE_VERSION:-unknown}"
grep -q '3\.1' <<<"$TOOLS_VERSION" || { echo 'ОШИБКА: tools не подтверждены как AWG 3.1.'; exit 1; }
grep -q '3\.1' <<<"$MODULE_VERSION" || { echo 'ОШИБКА: kernel module не подтверждён как AWG 3.1.'; exit 1; }

if [ ! -s "$CONF" ]; then
  SERVER_PRIVATE_KEY=$(awg genkey)
  SERVER_PUBLIC_KEY=$(printf '%s' "$SERVER_PRIVATE_KEY" | awg pubkey)
  HEADER_KEY=$(awg genkey)
  WAN_IF=$(ip -4 route show default 2>/dev/null | awk 'NR==1{print $5}')
  [ -n "${WAN_IF:-}" ] || WAN_IF=eth0
  cat >"$CONF" <<EOF
[Interface]
Address = 10.66.66.1/24
ListenPort = 443
PrivateKey = $SERVER_PRIVATE_KEY
MTU = 1280
Jc = 4
Jmin = 40
Jmax = 120
S1 = 16
S2 = 24
S3 = 16
S4 = 32
H1 = 1
H2 = 2
H3 = 3
H4 = 4
HeaderProtectionKey = $HEADER_KEY
RandomTrailers = on
DisableCookies = on
PostUp = iptables -A FORWARD -i awg0 -j ACCEPT; iptables -A FORWARD -o awg0 -j ACCEPT; iptables -t nat -A POSTROUTING -s 10.66.66.0/24 -o $WAN_IF -j MASQUERADE
PostDown = iptables -D FORWARD -i awg0 -j ACCEPT; iptables -D FORWARD -o awg0 -j ACCEPT; iptables -t nat -D POSTROUTING -s 10.66.66.0/24 -o $WAN_IF -j MASQUERADE
EOF
  printf '%s\n' "$SERVER_PUBLIC_KEY" >/etc/awg31-panel/server_public.key
  chmod 600 /etc/awg31-panel/server_public.key
fi

chmod 600 "$CONF"

# Normalize only known AWG 3.1 interface options; preserve keys, peers and custom options.
python3 - "$CONF" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); text=p.read_text(errors='replace')
updates={'ListenPort':'443','MTU':'1280','Jc':'4','Jmin':'40','Jmax':'120','S1':'16','S2':'24','S3':'16','S4':'32','H1':'1','H2':'2','H3':'3','H4':'4','RandomTrailers':'on','DisableCookies':'on'}
lines=text.splitlines(); out=[]; seen=set(); in_iface=False
for line in lines:
    st=line.strip()
    if st.startswith('['): in_iface=(st=='[Interface]')
    if in_iface and '=' in st and not st.startswith('#'):
        k=st.split('=',1)[0].strip()
        if k in updates:
            out.append(f'{k} = {updates[k]}'); seen.add(k); continue
    out.append(line)
idx=next((i for i,x in enumerate(out) if x.strip()=='[Peer]'),len(out))
missing=[f'{k} = {v}' for k,v in updates.items() if k not in seen]
out[idx:idx]=missing
p.write_text('\n'.join(out).rstrip()+'\n'); p.chmod(0o600)
PY

sysctl -w net.ipv4.ip_forward=1 >/dev/null
printf '%s\n' 'net.ipv4.ip_forward=1' >/etc/sysctl.d/99-awg31-panel.conf
sysctl --system >/dev/null 2>&1 || true

WAN_IF=$(ip -4 route show default 2>/dev/null | awk 'NR==1{print $5}')
if [ -n "${WAN_IF:-}" ]; then
  iptables -C INPUT -p udp --dport 443 -j ACCEPT 2>/dev/null || iptables -A INPUT -p udp --dport 443 -j ACCEPT
  iptables -C FORWARD -i awg0 -j ACCEPT 2>/dev/null || iptables -A FORWARD -i awg0 -j ACCEPT
  iptables -C FORWARD -o awg0 -j ACCEPT 2>/dev/null || iptables -A FORWARD -o awg0 -j ACCEPT
  iptables -t nat -C POSTROUTING -s 10.66.66.0/24 -o "$WAN_IF" -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -s 10.66.66.0/24 -o "$WAN_IF" -j MASQUERADE
fi

cp "$SRC/app.py" "$BASE/app.py"; chmod 600 "$BASE/app.py"
[ -f "$SRC/background.svg" ] && cp "$SRC/background.svg" "$BASE/background.svg"
for mod in naiveproxy_panel.py telegram_bot.py system_panel.py advanced_panel.py; do [ -f "$SRC/$mod" ] && cp "$SRC/$mod" "$BASE/$mod" && chmod 600 "$BASE/$mod"; done

python3 - "$BASE/panel.db" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]); c.execute('CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL)'); c.execute('CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,address TEXT NOT NULL,private_key TEXT NOT NULL,public_key TEXT NOT NULL,psk TEXT NOT NULL,created INTEGER NOT NULL)'); c.execute("INSERT OR IGNORE INTO settings(k,v) VALUES('login','admin')"); c.execute("INSERT OR IGNORE INTO settings(k,v) VALUES('endpoint','')"); c.commit(); c.close()
PY

if [ ! -f "$BASE/.initial_password" ]; then
  ADMIN_PASS=$(openssl rand -hex 12)
  python3 - "$BASE/panel.db" "$ADMIN_PASS" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]); c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('password',?)",(sys.argv[2],)); c.commit(); c.close()
PY
  printf '%s\n' "$ADMIN_PASS">"$BASE/.initial_password"; chmod 600 "$BASE/.initial_password"
fi

python3 -m venv "$BASE/venv"
"$BASE/venv/bin/pip" install -q 'Flask>=3,<4' 'qrcode[pil]>=7,<9'
"$BASE/venv/bin/python" -m py_compile "$BASE/app.py" "$BASE/naiveproxy_panel.py" "$BASE/telegram_bot.py" "$BASE/system_panel.py" "$BASE/advanced_panel.py"

awg-quick strip awg0 >/dev/null 2>&1 || { echo 'ОШИБКА: awg-quick strip awg0 не прошёл.'; awg-quick strip awg0 || true; exit 1; }

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
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now awg-quick@awg0.service
sleep 2
systemctl is-active --quiet awg-quick@awg0.service || { systemctl status awg-quick@awg0.service --no-pager -l || true; journalctl -u awg-quick@awg0.service -n 80 --no-pager || true; exit 1; }
BOT_CONFIGURED=0; [ -s /etc/awg31-panel/telegram.env ] && BOT_CONFIGURED=1
systemctl enable --now awgpanel
if [ "$BOT_CONFIGURED" = 1 ]; then systemctl enable --now awgpanel-telegram.service; else systemctl disable --now awgpanel-telegram.service >/dev/null 2>&1 || true; fi
sleep 2
systemctl is-active --quiet awgpanel || { journalctl -u awgpanel -n 80 --no-pager; exit 1; }
IP=$(curl -4 -fsS --max-time 5 https://api.ipify.org || true)
echo "AWG Panel 8.1: http://${IP:-SERVER_IP}:8080/login"
echo 'Login: admin'
if [ -f "$BASE/.initial_password" ]; then echo "Password: $(cat "$BASE/.initial_password")"; else echo 'Password: existing password preserved'; fi
echo "AWG interface: $(ip -br link show awg0 2>/dev/null || true)"
