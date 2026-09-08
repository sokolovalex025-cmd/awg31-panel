#!/usr/bin/env bash
set -euo pipefail

BASE=/opt/awg31-panel
CONF=/etc/amnezia/amneziawg/awg0.conf
[ -f "$CONF" ] || CONF=/etc/wireguard/awg0.conf
SRC="$(cd "$(dirname "$0")" && pwd)"
TS="$(date +%Y%m%d-%H%M%S)"

if [ "${EUID:-$(id -u)}" -ne 0 ]; then echo "Запусти от root: sudo ./install.sh"; exit 1; fi
if [ -r /etc/os-release ]; then . /etc/os-release; else echo "Не удалось определить ОС"; exit 1; fi
case "$ID" in ubuntu|debian) ;; *) echo "Поддерживается Ubuntu/Debian"; exit 1;; esac

apt-get update
apt-get install -y curl ca-certificates git python3 python3-venv python3-pip unzip iptables

if ! command -v awg >/dev/null 2>&1 || ! command -v awg-quick >/dev/null 2>&1; then
  TMP=$(mktemp -d)
  trap 'rm -rf "$TMP"' EXIT
  curl -fsSL https://raw.githubusercontent.com/wiresock/amneziawg-install/main/amneziawg-install.sh -o "$TMP/amneziawg-install.sh"
  chmod +x "$TMP/amneziawg-install.sh"
  AUTO_INSTALL=y ENABLE_IPV6=n SERVER_AWG_NIC=awg0 SERVER_AWG_IPV4=10.66.66.1 SERVER_PORT=1234 CREATE_INITIAL_CLIENT=no "$TMP/amneziawg-install.sh"
fi

TMP2=$(mktemp -d)
curl -fsSL https://raw.githubusercontent.com/wiresock/amneziawg-install/main/amneziawg-install.sh -o "$TMP2/amneziawg-install.sh"
chmod +x "$TMP2/amneziawg-install.sh"
if [ -f "$CONF" ]; then
  "$TMP2/amneziawg-install.sh" --enable-awg31 || true
fi
rm -rf "$TMP2"

CONF=/etc/amnezia/amneziawg/awg0.conf
[ -f "$CONF" ] || CONF=/etc/wireguard/awg0.conf
if [ ! -f "$CONF" ]; then echo "AWG config was not created: $CONF"; exit 1; fi

mkdir -p "$BASE"
[ -f "$BASE/app.py" ] && cp -a "$BASE/app.py" "$BASE/app.py.bak.$TS"
[ -f "$BASE/background.jpg" ] && cp -a "$BASE/background.jpg" "$BASE/background.jpg.bak.$TS"
[ -f "$BASE/panel.db" ] && cp -a "$BASE/panel.db" "$BASE/panel.db.bak.$TS"
cp -a "$CONF" "$CONF.bak-panel7.1-$TS"
cp "$SRC/app.py" "$BASE/app.py"
cp "$SRC/background.jpg" "$BASE/background.jpg"
chmod 755 "$BASE/app.py"; chmod 644 "$BASE/background.jpg"

python3 - "$CONF" <<'PY'
import sys, re, subprocess
p=sys.argv[1]
s=open(p,encoding='utf-8').read()
vals={
 'ListenPort':'1234','MTU':'1380','Jc':'4','Jmin':'40','Jmax':'120',
 'S1':'16','S2':'24','S3':'16','S4':'32','H1':'1','H2':'2','H3':'3','H4':'4',
 'ContentPaddingAddition':'0-64','RandomTrailers':'on','DisableCookies':'on',
 'RekeyAfterTime':'120-180','RekeyTimeout':'3-8','RejectAfterTime':'150-210',
 'KeepaliveTimeout':'8-15','MaxHandshakeAttempts':'8-15'
}
parts=s.split('[Peer]',1); head=parts[0]; tail=('\n[Peer]'+parts[1]) if len(parts)>1 else ''
lines=[]
for line in head.splitlines():
    k=line.split('=',1)[0].strip() if '=' in line else ''
    if k in vals or k=='HeaderProtectionKey': continue
    lines.append(line)
hpk=''
old=re.search(r'^HeaderProtectionKey\s*=\s*(\S+)', head, re.M)
if old: hpk=old.group(1)
if not hpk:
    r=subprocess.run(['awg','genkey'],capture_output=True,text=True,check=True); hpk=r.stdout.strip()
lines.append('HeaderProtectionKey = '+hpk)
for k,v in vals.items(): lines.append(f'{k} = {v}')
open(p,'w',encoding='utf-8').write('\n'.join(lines).rstrip()+tail+'\n')
PY

if ! ip link add awg0 type amneziawg 2>/dev/null; then
  echo "Не удалось создать amneziawg-интерфейс. Проверь модуль/поддержку AWG 3.1."; exit 1
fi
ip link del awg0 2>/dev/null || true

python3 - "$BASE/panel.db" <<'PY'
import sqlite3,sys
p=sys.argv[1]; c=sqlite3.connect(p)
c.execute('CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, address TEXT NOT NULL, private_key TEXT NOT NULL, public_key TEXT NOT NULL, psk TEXT NOT NULL, created INTEGER NOT NULL)')
for k,v in [('login','admin'),('password','change-me'),('endpoint','')]: c.execute('INSERT OR IGNORE INTO settings(k,v) VALUES(?,?)',(k,v))
c.commit();c.close()
PY

python3 -m venv "$BASE/venv"
"$BASE/venv/bin/pip" install --upgrade pip >/dev/null
"$BASE/venv/bin/pip" install 'Flask>=3,<4' 'qrcode[pil]>=7,<9' >/dev/null
python3 -m py_compile "$BASE/app.py"

cat > /etc/systemd/system/awgpanel.service <<EOF
[Unit]
Description=AWG Panel 7.1 Mobile Strong
After=network-online.target awg-quick@awg0.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$BASE
Environment=AWGPANEL_SECRET=change-this-secret-$TS
ExecStart=$BASE/venv/bin/python $BASE/app.py
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable awg-quick@awg0.service >/dev/null 2>&1 || true
systemctl restart awg-quick@awg0.service
sleep 2
if ! systemctl is-active --quiet awg-quick@awg0; then
  echo "AWG не запустился. Восстанавливаю предыдущую конфигурацию."
  cp -a "$CONF.bak-panel7.1-$TS" "$CONF"
  systemctl restart awg-quick@awg0 || true
  exit 1
fi
systemctl enable --now awgpanel >/dev/null
sleep 2

cat <<EOF

============================================
 AWG PANEL 7.1 — COMPLETE INSTALL
============================================
AWG:   $(systemctl is-active awg-quick@awg0)
Panel: $(systemctl is-active awgpanel)
Port:  1234/UDP
MTU:   1380
S1-S4: 16 / 24 / 16 / 32
H1-H4: 1 / 2 / 3 / 4
Mode:  AWG 3.1 Strong Mobile
Panel: http://SERVER-IP:8080/login

Existing panel.db and AWG config were backed up.
Default panel login: admin
Default panel password: change-me
Change it immediately in Settings.
============================================
EOF
