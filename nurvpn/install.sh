#!/usr/bin/env bash
set -euo pipefail
APP_DIR=/opt/nova-vpn-bot
SERVICE=nova-vpn-bot
apt-get update
apt-get install -y python3 python3-venv python3-pip git
mkdir -p "$APP_DIR/data"
cp -a . "$APP_DIR/"
cd "$APP_DIR"
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
if [[ ! -f .env ]]; then cp .env.example .env; fi
cat >/etc/systemd/system/${SERVICE}.service <<UNIT
[Unit]
Description=NOVA VPN Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/python ${APP_DIR}/main.py
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now "$SERVICE"
echo "Installed. Edit $APP_DIR/.env then: systemctl restart $SERVICE"
