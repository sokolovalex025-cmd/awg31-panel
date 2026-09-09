#!/usr/bin/env bash
set -Eeuo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root.'; exit 1; }
BASE=/opt/awg31-panel
SRC=$(cd "$(dirname "$0")" && pwd)
[ -f "$SRC/app.py" ] || { echo 'app.py не найден.'; exit 1; }
[ -f "$SRC/app9.py" ] || { echo 'app9.py не найден.'; exit 1; }
mkdir -p "$BASE/backups"
TS=$(date +%Y%m%d-%H%M%S)
[ -f "$BASE/app.py" ] && cp -a "$BASE/app.py" "$BASE/backups/app-before-9-$TS.py"
cp "$SRC/app.py" "$BASE/app.py"
cp "$SRC/app9.py" "$BASE/app9.py"
for mod in naiveproxy_panel.py telegram_bot.py system_panel.py advanced_panel.py background.svg; do
  [ -f "$SRC/$mod" ] && cp "$SRC/$mod" "$BASE/$mod"
done
chmod 600 "$BASE/app.py" "$BASE/app9.py" 2>/dev/null || true
"$BASE/venv/bin/python" -m py_compile "$BASE/app.py" "$BASE/app9.py" "$BASE/naiveproxy_panel.py" "$BASE/telegram_bot.py" "$BASE/system_panel.py" "$BASE/advanced_panel.py"
if [ -f /etc/systemd/system/awgpanel.service ]; then
  sed -i "s#^ExecStart=.*#ExecStart=$BASE/venv/bin/python $BASE/app9.py#" /etc/systemd/system/awgpanel.service
else
  cat >/etc/systemd/system/awgpanel.service <<EOF
[Unit]
Description=AWG Panel 9.0
After=network-online.target awg-quick@awg0.service
Wants=network-online.target
[Service]
WorkingDirectory=$BASE
Environment=AWGPANEL_SECRET=change-this-secret
ExecStart=$BASE/venv/bin/python $BASE/app9.py
Restart=on-failure
RestartSec=2
[Install]
WantedBy=multi-user.target
EOF
fi
systemctl daemon-reload
systemctl enable awgpanel >/dev/null
systemctl restart awgpanel
sleep 2
systemctl is-active --quiet awgpanel || { journalctl -u awgpanel -n 80 --no-pager; exit 1; }
curl -fsS --max-time 5 http://127.0.0.1:8080/login >/dev/null
printf '\nAWG Panel 9.0 установлен и отвечает на HTTP.\n'
