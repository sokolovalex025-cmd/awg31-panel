#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root: sudo ./install.sh'; exit 1; }
. /etc/os-release
[ "${ID:-}" = ubuntu ] || { echo 'Требуется Ubuntu'; exit 1; }
BASE=/opt/awg31-panel; SRC="$(cd "$(dirname "$0")" && pwd)"; TS=$(date +%Y%m%d-%H%M%S)
mkdir -p "$BASE/backups" /etc/amnezia/amneziawg/clients /etc/awg31-panel
[ -f "$BASE/app.py" ] && cp -a "$BASE/app.py" "$BASE/backups/app-before-7.4-$TS.py"
[ -f "$BASE/panel.db" ] && cp -a "$BASE/panel.db" "$BASE/backups/panel-before-7.4-$TS.db"
[ -f /etc/amnezia/amneziawg/awg0.conf ] && cp -a /etc/amnezia/amneziawg/awg0.conf "$BASE/backups/awg0-before-7.4-$TS.conf"
apt-get update
apt-get install -y python3 python3-venv python3-pip curl iproute2 qrencode openssl iptables
command -v awg >/dev/null 2>&1 || { echo 'AmneziaWG 3.1 не найден. Установите AWG и повторите.'; exit 1; }
cp "$SRC/app.py" "$BASE/app.py"; chmod 600 "$BASE/app.py"
[ -f "$SRC/background.svg" ] && cp "$SRC/background.svg" "$BASE/background.svg"
[ -f "$SRC/naiveproxy_panel.py" ] && cp "$SRC/naiveproxy_panel.py" "$BASE/naiveproxy_panel.py"; chmod 600 "$BASE/naiveproxy_panel.py"
[ -f "$SRC/telegram_bot.py" ] && cp "$SRC/telegram_bot.py" "$BASE/telegram_bot.py"; chmod 600 "$BASE/telegram_bot.py"
[ -f "$SRC/system_panel.py" ] && cp "$SRC/system_panel.py" "$BASE/system_panel.py"; chmod 600 "$BASE/system_panel.py"
python3 - "$BASE/app.py" <<'PY'
from pathlib import Path
p=Path(__import__('sys').argv[1]); s=p.read_text()
s=s.replace('AWG Panel 7.1','AWG Panel 7.4').replace('AWG Panel 7.2','AWG Panel 7.4').replace('AWG Panel 7.3','AWG Panel 7.4').replace('v=71','v=74').replace('v=72','v=74').replace('v=73','v=74')
adds=[]
if 'naiveproxy_panel.register(app)' not in s: adds.append('import naiveproxy_panel\nnaiveproxy_panel.register(app)\n')
if 'telegram_bot.register(app)' not in s: adds.append('import telegram_bot\ntelegram_bot.register(app)\n')
if 'system_panel.register(app)' not in s: adds.append('import system_panel\nsystem_panel.register(app)\n')
if adds:
 marker='if __name__ == "__main__":'; add=''.join(adds)
 if marker in s:s=s.replace(marker,add+marker,1)
 else:
  i=s.rfind('app.run('); s=s[:i]+add+s[i:] if i>=0 else s+'\n'+add
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
"$BASE/venv/bin/python" -m py_compile "$BASE/app.py" "$BASE/naiveproxy_panel.py" "$BASE/telegram_bot.py" "$BASE/system_panel.py"
SECRET=$(openssl rand -hex 32)
cat >/etc/systemd/system/awgpanel.service <<EOF
[Unit]
Description=AWG Panel 7.4 Mobile Strong + NaiveProxy + Telegram + Monitoring
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
cat >/etc/systemd/system/awgpanel-telegram.service <<EOF
[Unit]
Description=AWG Panel Telegram Bot
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
BOT_CONFIGURED=0; [ -s /etc/awg31-panel/telegram.env ] && BOT_CONFIGURED=1
systemctl daemon-reload; systemctl enable --now awgpanel
if [ "$BOT_CONFIGURED" = 1 ]; then systemctl enable --now awgpanel-telegram.service; else systemctl disable --now awgpanel-telegram.service >/dev/null 2>&1 || true; fi
sleep 2
systemctl is-active --quiet awgpanel || { journalctl -u awgpanel -n 80 --no-pager; exit 1; }
IP=$(curl -4 -fsS --max-time 5 https://api.ipify.org || true)
echo "AWG Panel 7.4: http://${IP}:8080/login"; echo "Login: admin"; if [ -f "$BASE/.initial_password" ]; then echo "Password: $(cat "$BASE/.initial_password")"; else echo 'Password: existing password preserved'; fi
echo 'NaiveProxy: раздел «NaïveProxy» в панели.'
echo 'Telegram: раздел «Telegram Bot» в панели; бот запускается после сохранения token + Telegram ID.'
echo 'Monitoring: раздел «Система»; Health Check: раздел «Диагностика».'
