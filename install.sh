#!/usr/bin/env bash
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
[ "$(id -u)" -eq 0 ] || { echo 'Запустите от root'; exit 1; }
. /etc/os-release
[ "${ID:-}" = ubuntu ] || { echo 'Требуется Ubuntu'; exit 1; }
BASE=/opt/awg31-panel
mkdir -p "$BASE" "$BASE/backups" /etc/amnezia/amneziawg/clients
[ -f "$BASE/app.py" ] && cp -a "$BASE/app.py" "$BASE/backups/app-before-6.7.2-$(date +%Y%m%d-%H%M%S).py"
[ -f /etc/amnezia/amneziawg/awg0.conf ] && cp -a /etc/amnezia/amneziawg/awg0.conf "$BASE/backups/awg0-before-6.7.2-$(date +%Y%m%d-%H%M%S).conf"
cp app.py "$BASE/app.py"
cp background.svg "$BASE/background.svg"
chmod 750 "$BASE"; chmod 644 "$BASE/background.svg"; chmod 600 "$BASE/app.py"
if [ ! -x "$BASE/venv/bin/python" ]; then apt-get update; apt-get install -y python3 python3-venv python3-pip curl iproute2 qrencode openssl; python3 -m venv "$BASE/venv"; "$BASE/venv/bin/pip" install -q Flask; fi
"$BASE/venv/bin/python" -m py_compile "$BASE/app.py"
SECRET=$(systemctl show awgpanel -p Environment --value 2>/dev/null | sed -n 's/.*AWG_PANEL_SECRET=\([^ ]*\).*/\1/p' || true); [ -n "$SECRET" ] || SECRET=$(openssl rand -hex 32)
cat >/etc/systemd/system/awgpanel.service <<EOF
[Unit]
Description=AWG Panel 6.7.2 Mobile Strong
After=network-online.target
Wants=network-online.target
[Service]
WorkingDirectory=$BASE
ExecStart=$BASE/venv/bin/python $BASE/app.py
Restart=on-failure
RestartSec=3
Environment=AWG_PANEL_SECRET=$SECRET
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload; systemctl enable awgpanel >/dev/null; systemctl restart awgpanel; sleep 2
systemctl is-active --quiet awgpanel || { journalctl -u awgpanel -n 80 --no-pager; exit 1; }
IP=$(curl -4 -fsS --max-time 5 https://api.ipify.org || true)
echo "AWG Panel 6.7.2 установлен/обновлён"; echo "http://${IP}:8080"; echo "DB и текущий awg0.conf сохранены."
