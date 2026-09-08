#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root: sudo ./install.sh'; exit 1; }
. /etc/os-release
[ "${ID:-}" = ubuntu ] || { echo 'Требуется Ubuntu'; exit 1; }
BASE=/opt/awg31-panel; SRC="$(cd "$(dirname "$0")" && pwd)"; TS=$(date +%Y%m%d-%H%M%S)
mkdir -p "$BASE/backups" /etc/amnezia/amneziawg/clients
[ -f "$BASE/app.py" ] && cp -a "$BASE/app.py" "$BASE/backups/app-before-7.2-$TS.py"
[ -f "$BASE/panel.db" ] && cp -a "$BASE/panel.db" "$BASE/backups/panel-before-7.2-$TS.db"
[ -f /etc/amnezia/amneziawg/awg0.conf ] && cp -a /etc/amnezia/amneziawg/awg0.conf "$BASE/backups/awg0-before-7.2-$TS.conf"
apt-get update
apt-get install -y python3 python3-venv python3-pip curl iproute2 qrencode openssl iptables
command -v awg >/dev/null 2>&1 || { echo 'AmneziaWG 3.1 не найден. Установите AWG и повторите.'; exit 1; }
cp "$SRC/app.py" "$BASE/app.py"; chmod 600 "$BASE/app.py"
[ -f "$SRC/background.svg" ] && cp "$SRC/background.svg" "$BASE/background.svg"
[ -f "$SRC/naiveproxy_panel.py" ] && cp "$SRC/naiveproxy_panel.py" "$BASE/naiveproxy_panel.py"; chmod 600 "$BASE/naiveproxy_panel.py"
python3 - "$BASE/app.py" <<'PY'
from pathlib import Path
p=Path(__import__('sys').argv[1]); s=p.read_text()
s=s.replace('AWG Panel 7.1','AWG Panel 7.2').replace('v=71','v=72')
if 'naiveproxy_panel.register(app)' not in s:
    marker='if __name__ == "__main__":'
    add='import naiveproxy_panel\nnaiveproxy_panel.register(app)\n'
    if marker in s:
        s=s.replace(marker,add+marker,1)
    else:
        i=s.rfind('app.run(')
        if i>=0:s=s[:i]+add+s[i:]
        else:s+='\n'+add
    p.write_text(s)
PY
NEW_DB=0; [ -f "$BASE/panel.db" ] || NEW_DB=1
python3 - "$BASE/panel.db" <<'PY'
import sqlite3,sys
p=sys.argv[1]; c=sqlite3.connect(p)
c.execute('CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL)')
c.execute('CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,address TEXT NOT NULL,private_key TEXT NOT NULL,public_key TEXT NOT NULL,psk TEXT NOT NULL,created INTEGER NOT NULL)')
c.execute("INSERT OR IGNORE INTO settings(k,v) VALUES('login','admin')"); c.execute("INSERT OR IGNORE INTO settings(k,v) VALUES('endpoint','')"); c.commit(); c.close()
PY
if [ "$NEW_DB" = 1 ]; then
 ADMIN_PASS=$(openssl rand -hex 12)
 python3 - "$BASE/panel.db" "$ADMIN_PASS" <<'PY'
import sqlite3,sys
p,pw=sys.argv[1:]; c=sqlite3.connect(p); c.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('password',?)",(pw,)); c.commit(); c.close(); open('/opt/awg31-panel/.initial_password','w').write(pw+'\n')
PY
 chmod 600 "$BASE/.initial_password"
else
 ADMIN_PASS=$(python3 - "$BASE/panel.db" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1]); r=c.execute("SELECT v FROM settings WHERE k='password'").fetchone(); print(r[0] if r else 'change-me'); c.close()
PY
)
fi
python3 -m venv "$BASE/venv"
"$BASE/venv/bin/pip" install -q 'Flask>=3,<4' 'qrcode[pil]>=7,<9'
"$BASE/venv/bin/python" -m py_compile "$BASE/app.py" "$BASE/naiveproxy_panel.py"
SECRET=$(openssl rand -hex 32)
cat >/etc/systemd/system/awgpanel.service <<EOF
[Unit]
Description=AWG Panel 7.2 Mobile Strong + NaiveProxy
After=network-online.target awg-quick@awg0.service
Wants=network-online.target
[Service]
WorkingDirectory=$BASE
Environment=AWGPANEL_SECRET=$SECRET
Environment=AWGPANEL_PASSWORD=$ADMIN_PASS
ExecStart=$BASE/venv/bin/python $BASE/app.py
Restart=on-failure
RestartSec=2
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload; systemctl enable --now awgpanel; sleep 2
systemctl is-active --quiet awgpanel || { journalctl -u awgpanel -n 80 --no-pager; exit 1; }
IP=$(curl -4 -fsS --max-time 5 https://api.ipify.org || true)
echo "AWG Panel 7.2: http://${IP}:8080/login"; echo "Login: admin"; if [ -f "$BASE/.initial_password" ]; then echo "Password: $(cat "$BASE/.initial_password")"; else echo 'Password: existing password preserved'; fi
echo 'NaiveProxy: откройте раздел «NaïveProxy» в панели для установки.'
