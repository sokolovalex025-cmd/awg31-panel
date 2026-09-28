#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP=/opt/bandju-telegram-bot
ENV_DIR=/etc/bandju-telegram-bot
DATA=/var/lib/bandju-telegram-bot

apt-get update
apt-get install -y python3 python3-venv curl

install -d -m 0750 "$APP" "$ENV_DIR" "$DATA"

cp -a "$SCRIPT_DIR"/. "$APP/"

python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install --upgrade pip
"$APP/venv/bin/pip" install -r "$APP/requirements.txt"

if [[ ! -f "$ENV_DIR/.env" ]]; then
  install -m 0600 "$APP/.env.example" "$ENV_DIR/.env"
fi

install -m 0755 "$APP/bandju-telegram-bot-api-check" /usr/local/bin/bandju-telegram-bot-api-check
install -m 0644 "$APP/bandju-telegram-bot.service" /etc/systemd/system/bandju-telegram-bot.service

systemctl daemon-reload

echo
echo "Installed."
echo "Edit: $ENV_DIR/.env"
echo "Then: systemctl enable --now bandju-telegram-bot"
